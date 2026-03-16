import os
import re
import time
import json
import random
import logging
import json_repair
import asyncio
from urllib.parse import urljoin
from typing import Any, Dict, List, Optional, Union, Tuple, Generator, AsyncGenerator
from copy import deepcopy
from abc import ABC, abstractmethod

from strenum import StrEnum
from openai import OpenAI, AsyncOpenAI
from common.utils_token import num_tokens_from_string, total_token_count_from_response, is_chinese, is_english

logger = logging.getLogger(__name__)

# Constants
THINKING_START_TAG = "<thinking>"
THINKING_END_TAG = "</thinking>"
ERROR_PREFIX = "**ERROR**"
LENGTH_NOTIFICATION_CN = "······\n由于大模型的上下文窗口大小限制，回答已经被大模型截断。"
LENGTH_NOTIFICATION_EN = "...\nThe answer is truncated by your chosen LLM due to its limitation on context length."


class LLMErrorCode(StrEnum):
    """Error codes for LLM operations."""
    ERROR_RATE_LIMIT = "RATE_LIMIT_EXCEEDED"
    ERROR_AUTHENTICATION = "AUTH_ERROR"
    ERROR_INVALID_REQUEST = "INVALID_REQUEST"
    ERROR_SERVER = "SERVER_ERROR"
    ERROR_TIMEOUT = "TIMEOUT"
    ERROR_CONNECTION = "CONNECTION_ERROR"
    ERROR_MODEL = "MODEL_ERROR"
    ERROR_MAX_ROUNDS = "ERROR_MAX_ROUNDS"
    ERROR_CONTENT_FILTER = "CONTENT_FILTERED"
    ERROR_QUOTA = "QUOTA_EXCEEDED"
    ERROR_MAX_RETRIES = "MAX_RETRIES_EXCEEDED"
    ERROR_GENERIC = "GENERIC_ERROR"

class BaseLLM(ABC):
    """Base class for all LLMs."""
    
    def __init__(self, model_name: str, api_key: str, api_base_url: str, **kwargs) -> None:
        """Initialize LLM with the given configuration.

        Args:
            model_name: The model name.
            api_key: The API key.
            api_base_url: The base URL for the API.
            **kwargs: Additional configuration options.
        """
        timeout = int(os.environ.get("LLM_TIMEOUT_SECONDS", 600))
        self.client = OpenAI(
            api_key=api_key,
            base_url=api_base_url,
            timeout=timeout,
        )

        self.async_client = AsyncOpenAI(
            api_key=api_key,
            base_url=api_base_url,
            timeout=timeout,
        )

        self.model_name = model_name

        # Configure retry parameters
        self.max_retries = kwargs.get("max_retries", int(os.environ.get("LLM_MAX_RETRIES", 5)))
        self.base_delay = kwargs.get("retry_interval", float(os.environ.get("LLM_BASE_DELAY", 2.0)))
        self.max_rounds = kwargs.get("max_rounds", 5)
        self.is_tools = False
        self.tools = []
        self.toolcall_session = None  # Renamed from toolcall_sessions to toolcall_session
    
    

    def chat(self, history: List[Dict[str, str]], gen_conf: Dict[str, Any], **kwargs) -> Tuple[str, int]:
        """Chat with the LLM."""
        request_kwargs = {"model": self.model_name, "messages": history, "stream": False, **gen_conf}
        stop = kwargs.get("stop")
        if stop:
            request_kwargs["stop"] = stop
        
        response = self.client.chat.completions.create(**request_kwargs)
        ans = ""
        if hasattr(response.choices[0].message, "reasoning_content"):
            ans = "<think>" + response.choices[0].message.reasoning_content + "</think>"
        
        ans += response.choices[0].message.content
        total_tokens = total_token_count_from_response(response)
        return ans, total_tokens
    
    def chat_stream(self, history: List[Dict[str, str]], gen_conf: Dict[str, Any], **kwargs) -> Generator[Tuple[str, int], None, None]:
        """Stream chat with the LLM."""
        request_kwargs = {"model": self.model_name, "messages": history, "stream": True, **gen_conf}
        stop = kwargs.get("stop")
        if stop:
            request_kwargs["stop"] = stop
            
        response = self.client.chat.completions.create(**request_kwargs)
        reasoning_start = False
        
        for resp in response:
            if not resp.choices:
                continue
            
            delta = resp.choices[0].delta
            if not delta.content:
                delta.content = ""
                
            if kwargs.get("with_reasoning", True) and hasattr(delta, "reasoning_content") and delta.reasoning_content:
                ans = ""
                if not reasoning_start:
                    reasoning_start = True
                    ans = "<think>"
                ans += delta.reasoning_content + "</think>"
            else:
                reasoning_start = False
                ans = delta.content
                
            total_tokens = total_token_count_from_response(resp)
            if not total_tokens:
                total_tokens = num_tokens_from_string(delta.content)

            finish_reason = resp.choices[0].finish_reason if hasattr(resp.choices[0], "finish_reason") else ""
            if finish_reason == "length":
                if is_chinese(ans):
                    ans += LENGTH_NOTIFICATION_CN
                else:
                    ans += LENGTH_NOTIFICATION_EN
            yield ans, total_tokens
    
    async def _async_chat_streamly(self, history: List[Dict[str, str]], gen_conf: Dict[str, Any], **kwargs) -> AsyncGenerator[Tuple[str, int], None]:
        """Async stream chat with the LLM."""
        request_kwargs = {"model": self.model_name, "messages": history, "stream": True, **gen_conf}
        stop = kwargs.get("stop")
        if stop:
            request_kwargs["stop"] = stop

        response = await self.async_client.chat.completions.create(**request_kwargs)
        reasoning_start = False
        
        async for resp in response:
            if not resp.choices:
                continue
            
            delta = resp.choices[0].delta
            if not delta.content:
                delta.content = ""
                
            if kwargs.get("with_reasoning", True) and hasattr(delta, "reasoning_content") and delta.reasoning_content:
                ans = ""
                if not reasoning_start:
                    reasoning_start = True
                    ans = "<think>"
                ans += delta.reasoning_content + "</think>"
            else:
                reasoning_start = False
                ans = delta.content
                
            total_tokens = total_token_count_from_response(resp)
            if not total_tokens:
                total_tokens = num_tokens_from_string(delta.content)

            finish_reason = resp.choices[0].finish_reason if hasattr(resp.choices[0], "finish_reason") else ""
            if finish_reason == "length":
                if is_chinese(ans):
                    ans += LENGTH_NOTIFICATION_CN
                else:
                    ans += LENGTH_NOTIFICATION_EN
            yield ans, total_tokens

    async def async_chat_streamly(self, system_prompt: str, history: List[Dict[str, str]], gen_conf: Dict[str, Any] = {}, **kwargs) -> AsyncGenerator[Union[str, int], None]:
        """Async stream chat with the LLM."""
        if system_prompt and history and history[0].get("role") != "system":
            history.insert(0, {"role": "system", "content": system_prompt})
        gen_conf = self._clean_conf(gen_conf)
        ans = ""
        total_tokens = 0

        for attempt in range(self.max_retries + 1):
            try:
                async for delta_ans, tol_token in self._async_chat_streamly(history, gen_conf, **kwargs):
                    ans = delta_ans
                    total_tokens += tol_token
                    yield ans

                yield total_tokens
                return
            except Exception as e:
                e = await self._exceptions_async(e, attempt)
                if e:
                    yield e
                    yield total_tokens
                    return


    async def async_chat_with_tools(self, system_prompt: str, history: List[Dict[str, str]], gen_conf: Dict[str, Any] = {}) -> Tuple[str, int]:
        """Async chat with tools."""
        gen_conf = self._clean_conf(gen_conf)
        if system_prompt and history and history[0].get("role") != "system":
            history.insert(0, {"role": "system", "content": system_prompt})

        ans = ""
        total_tokens = 0
        hist = deepcopy(history)
        
        for attempt in range(self.max_retries + 1):
            history = deepcopy(hist)
            try:
                for _ in range(self.max_rounds + 1):
                    response = await self.async_client.chat.completions.create(
                        model=self.model_name, 
                        messages=history, 
                        tools=self.tools, 
                        tool_choice="auto", 
                        **gen_conf
                    )
                    
                    total_tokens += total_token_count_from_response(response)
                    
                    if not response.choices or not response.choices[0].message:
                        raise Exception(f"Invalid response structure: {response}")

                    if not hasattr(response.choices[0].message, "tool_calls") or not response.choices[0].message.tool_calls:
                        if hasattr(response.choices[0].message, "reasoning_content") and response.choices[0].message.reasoning_content:
                            ans += "<think>" + response.choices[0].message.reasoning_content + "</think>"

                        ans += response.choices[0].message.content
                        if response.choices[0].finish_reason == "length":
                            ans = self._length_stop(ans)

                        return ans, total_tokens

                    for tool_call in response.choices[0].message.tool_calls:
                        name = tool_call.function.name
                        try:
                            args = json_repair.loads(tool_call.function.arguments)
                            tool_response = await asyncio.to_thread(self.toolcall_session.tool_call, name, args)
                            history = self._append_history(history, tool_call, tool_response)
                            ans += self._verbose_tool_use(name, args, tool_response)
                        except Exception as e:
                            logging.exception(f"Error in tool call {name}: {e}")
                            history.append({"role": "tool", "tool_call_id": tool_call.id, "content": f"Tool call error: \n{tool_call}\nException:\n" + str(e)})
                            ans += self._verbose_tool_use(name, {}, str(e))

                logging.warning(f"Exceed max rounds: {self.max_rounds}")
                history.append({"role": "user", "content": f"Exceed max rounds: {self.max_rounds}"})
                response, token_count = await self._async_chat(history, gen_conf)
                ans += response
                total_tokens += token_count
                return ans, total_tokens
                
            except Exception as e:
                e = await self._exceptions_async(e, attempt)
                if e:
                    return e, total_tokens

        raise RuntimeError("Shouldn't be here.")

    async def async_chat_streamly_with_tools(self, system_prompt: str, history: List[Dict[str, str]], gen_conf: Dict[str, Any] = {}) -> AsyncGenerator[Union[str, int], None]:
        """Async stream chat with tools."""
        gen_conf = self._clean_conf(gen_conf)
        tools = self.tools
        if system_prompt and history and history[0].get("role") != "system":
            history.insert(0, {"role": "system", "content": system_prompt})

        total_tokens = 0
        hist = deepcopy(history)

        for attempt in range(self.max_retries + 1):
            history = deepcopy(hist)
            try:
                for _ in range(self.max_rounds + 1):
                    reasoning_start = False

                    response = await self.async_client.chat.completions.create(
                        model=self.model_name, 
                        messages=history, 
                        stream=True, 
                        tools=tools, 
                        tool_choice="auto", 
                        **gen_conf
                    )

                    final_tool_calls = {}
                    answer = ""

                    async for resp in response:
                        if not hasattr(resp, "choices") or not resp.choices:
                            continue

                        delta = resp.choices[0].delta

                        if hasattr(delta, "tool_calls") and delta.tool_calls:
                            for tool_call in delta.tool_calls:
                                index = tool_call.index
                                if index not in final_tool_calls:
                                    if not tool_call.function.arguments:
                                        tool_call.function.arguments = ""
                                    final_tool_calls[index] = tool_call
                                else:
                                    final_tool_calls[index].function.arguments += tool_call.function.arguments or ""
                            continue

                        if not hasattr(delta, "content") or delta.content is None:
                            delta.content = ""

                        if hasattr(delta, "reasoning_content") and delta.reasoning_content:
                            ans = ""
                            if not reasoning_start:
                                reasoning_start = True
                                ans = "<think>"
                            ans += delta.reasoning_content + "</think>"
                            yield ans
                        else:
                            reasoning_start = False
                            answer += delta.content
                            yield delta.content

                        tol_token = total_token_count_from_response(resp)
                        if not tol_token:
                            total_tokens += num_tokens_from_string(delta.content)
                        else:
                            total_tokens = tol_token

                        finish_reason = getattr(resp.choices[0], "finish_reason", "")
                        if finish_reason == "length":
                            yield self._length_stop("")

                    if answer:
                        yield total_tokens
                        return

                    for tool_call in final_tool_calls.values():
                        name = tool_call.function.name
                        try:
                            args = json_repair.loads(tool_call.function.arguments)
                            yield self._verbose_tool_use(name, args, "Begin to call...")
                            tool_response = await asyncio.to_thread(self.toolcall_session.tool_call, name, args)
                            history = self._append_history(history, tool_call, tool_response)
                            yield self._verbose_tool_use(name, args, tool_response)
                        except Exception as e:
                            logging.exception(f"Error in tool call {name}: {e}")
                            history.append({"role": "tool", "tool_call_id": tool_call.id, "content": f"Tool call error: \n{tool_call}\nException:\n" + str(e)})
                            yield self._verbose_tool_use(name, {}, str(e))

                logging.warning(f"Exceed max rounds: {self.max_rounds}")
                history.append({"role": "user", "content": f"Exceed max rounds: {self.max_rounds}"})

                response = await self.async_client.chat.completions.create(
                    model=self.model_name, 
                    messages=history, 
                    stream=True, 
                    tools=tools, 
                    tool_choice="auto", 
                    **gen_conf
                )

                async for resp in response:
                    if not hasattr(resp, "choices") or not resp.choices:
                        continue
                    delta = resp.choices[0].delta
                    if not hasattr(delta, "content") or delta.content is None:
                        continue
                    tol_token = total_token_count_from_response(resp)
                    if not tol_token:
                        total_tokens += num_tokens_from_string(delta.content)
                    else:
                        total_tokens = tol_token
                    yield delta.content

                yield total_tokens
                return

            except Exception as e:
                e = await self._exceptions_async(e, attempt)
                if e:
                    logging.error(f"async_chat_streamly failed: {e}")
                    yield e
                    yield total_tokens
                    return

        raise RuntimeError("Shouldn't be here.")

    async def _async_chat(self, history: List[Dict[str, str]], gen_conf: Dict[str, Any], **kwargs) -> Tuple[str, int]:
        """Async chat with the LLM."""
        if self.model_name.lower().find("qwq") >= 0:
            logger.info(f"{self.model_name} detected as reasoning model, using async_chat_streamly")

            final_ans = ""
            total_tokens = 0
            async for delta, tol_token in self._async_chat_streamly(history, gen_conf, with_reasoning=False, **kwargs):
                if delta.startswith("<think>") or delta.endswith("</think>"):
                    continue
                final_ans += delta
                total_tokens = tol_token

            if len(final_ans.strip()) == 0:
                final_ans = "**ERROR**: Empty response from reasoning model"

            return final_ans.strip(), total_tokens

        if self.model_name.lower().find("qwen3") >= 0:
            kwargs["extra_body"] = {"enable_thinking": False}

        response = await self.async_client.chat.completions.create(model=self.model_name, messages=history, **gen_conf, **kwargs)

        if not response.choices or not response.choices[0].message or not response.choices[0].message.content:
            return "", 0
        ans = response.choices[0].message.content.strip()
        if response.choices[0].finish_reason == "length":
            ans = self._length_stop(ans)
        return ans, total_token_count_from_response(response)

    async def async_chat(self, system_prompt: Optional[str], history: List[Dict[str, str]], gen_conf: Dict[str, Any] = {}, **kwargs) -> Tuple[str, int]:
        """Async chat with the LLM."""
        if system_prompt and history and history[0].get("role") != "system":
            history.insert(0, {"role": "system", "content": system_prompt})
        gen_conf = self._clean_conf(gen_conf)

        for attempt in range(self.max_retries + 1):
            try:
                return await self._async_chat(history, gen_conf, **kwargs)
            except Exception as e:
                e = await self._exceptions_async(e, attempt)
                if e:
                    return e, 0
        raise RuntimeError("Shouldn't be here.")
        
    def _length_stop(self, ans: str) -> str:
        """Add length notification to the answer if it was truncated."""
        if is_chinese(ans):
            return ans + LENGTH_NOTIFICATION_CN
        return ans + LENGTH_NOTIFICATION_EN

    @property
    def _retryable_errors(self) -> set[str]:
        return {
            LLMErrorCode.ERROR_RATE_LIMIT,
            LLMErrorCode.ERROR_SERVER,
        }

    def _should_retry(self, error_code: str) -> bool:
        return error_code in self._retryable_errors

    def _exceptions(self, e: Exception, attempt: int) -> Optional[str]:
        """Handle exceptions for sync methods."""
        logging.exception("OpenAI chat_with_tools")
        # Classify the error
        error_code = self._classify_error(e)
        if attempt == self.max_retries:
            error_code = LLMErrorCode.ERROR_MAX_RETRIES

        if self._should_retry(error_code):
            delay = self._get_delay()
            logging.warning(f"Error: {error_code}. Retrying in {delay:.2f} seconds... (Attempt {attempt + 1}/{self.max_retries})")
            time.sleep(delay)
            return None

        msg = f"{ERROR_PREFIX}: {error_code} - {str(e)}"
        logging.error(f"sync base giving up: {msg}")
        return msg

    async def _exceptions_async(self, e: Exception, attempt: int) -> Optional[str]:
        """Handle exceptions for async methods."""
        logging.exception("OpenAI async completion")
        error_code = self._classify_error(e)
        if attempt == self.max_retries:
            error_code = LLMErrorCode.ERROR_MAX_RETRIES

        if self._should_retry(error_code):
            delay = self._get_delay()
            logging.warning(f"Error: {error_code}. Retrying in {delay:.2f} seconds... (Attempt {attempt + 1}/{self.max_retries})")
            await asyncio.sleep(delay)
            return None

        msg = f"{ERROR_PREFIX}: {error_code} - {str(e)}"
        logging.error(f"async base giving up: {msg}")
        return msg

    def _verbose_tool_use(self, name: str, args: Dict[str, Any], res: Any) -> str:
        """Format tool use for verbose output."""
        return "<tool_call>" + json.dumps({"name": name, "args": args, "result": res}, ensure_ascii=False, indent=2) + "</tool_call>"

    def _append_history(self, hist: List[Dict[str, Any]], tool_call: Any, tool_res: Any) -> List[Dict[str, Any]]:
        """Append tool call and response to history."""
        hist.append(
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": tool_call.id,
                        "function": {
                            "name": tool_call.function.name,
                            "arguments": tool_call.function.arguments,
                        },
                        "type": "function",
                    },
                ],
            }
        )
        try:
            if isinstance(tool_res, dict):
                tool_res = json.dumps(tool_res, ensure_ascii=False)
        finally:
            hist.append({"role": "tool", "tool_call_id": tool_call.id, "content": str(tool_res)})
        return hist

    def bind_tools(self, toolcall_session: Any, tools: List[Dict[str, Any]]) -> None:
        """Bind tools to the LLM.

        Args:
            toolcall_session: The tool call session.
            tools: List of tools to bind.
        """
        if not (toolcall_session and tools):
            return
        self.is_tools = True
        self.toolcall_session = toolcall_session
        self.tools = tools
    
    
    def _get_delay(self) -> float:
        """Get delay for retry with jitter."""
        return self.base_delay * random.uniform(1.0, 1.5)  # Reduced jitter range for more predictable behavior

    def _classify_error(self, error: Exception) -> str:
        """Classify error into error code."""
        error_str = str(error).lower()

        keywords_mapping = [
            (["quota", "capacity", "credit", "billing", "balance", "欠费"], LLMErrorCode.ERROR_QUOTA),
            (["rate limit", "429", "tpm limit", "too many requests", "requests per minute"], LLMErrorCode.ERROR_RATE_LIMIT),
            (["auth", "key", "apikey", "401", "forbidden", "permission"], LLMErrorCode.ERROR_AUTHENTICATION),
            (["invalid", "bad request", "400", "format", "malformed", "parameter"], LLMErrorCode.ERROR_INVALID_REQUEST),
            (["server", "503", "502", "504", "500", "unavailable"], LLMErrorCode.ERROR_SERVER),
            (["timeout", "timed out"], LLMErrorCode.ERROR_TIMEOUT),
            (["connect", "network", "unreachable", "dns"], LLMErrorCode.ERROR_CONNECTION),
            (["filter", "content", "policy", "blocked", "safety", "inappropriate"], LLMErrorCode.ERROR_CONTENT_FILTER),
            (["model", "not found", "does not exist", "not available"], LLMErrorCode.ERROR_MODEL),
            (["max rounds"], LLMErrorCode.ERROR_MAX_ROUNDS),
        ]
        for words, code in keywords_mapping:
            if any(word in error_str for word in words):
                return code

        return LLMErrorCode.ERROR_GENERIC

    def _clean_conf(self, gen_conf: Dict[str, Any]) -> Dict[str, Any]:
        """Clean and validate generation configuration."""
        if "max_tokens" in gen_conf:
            del gen_conf["max_tokens"]

        allowed_conf = {
            "temperature",
            "max_completion_tokens",
            "top_p",
            "stream",
            "stream_options",
            "stop",
            "n",
            "presence_penalty",
            "frequency_penalty",
            "functions",
            "function_call",
            "logit_bias",
            "user",
            "response_format",
            "seed",
            "tools",
            "tool_choice",
            "logprobs",
            "top_logprobs",
            "extra_headers",
        }

        gen_conf = {k: v for k, v in gen_conf.items() if k in allowed_conf}

        model_name_lower = (self.model_name or "").lower()
        # gpt-5 and gpt-5.1 endpoints have inconsistent parameter support, clear custom generation params to prevent unexpected issues
        if "gpt-5" in model_name_lower:
            gen_conf = {}

        return gen_conf


class OpenAIAPIChat(BaseLLM):
    _FACTORY_NAME = ["VLLM", "OpenAIAPI-Compatible"]

    def __init__(self, api_key: str, model_name: str, base_url: str, **kwargs):
        if not base_url:
            raise ValueError("base_url cannot be None")
        model_name = model_name.split("___")[0]
        super().__init__(model_name, api_key, base_url, **kwargs)

class VolcEngineChat(BaseLLM):
    _FACTORY_NAME = "VolcEngine"

    def __init__(self, api_key: str, model_name: str, base_url: str = "https://ark.cn-beijing.volces.com/api/v3", **kwargs):
        """
        Initialize VolcEngine chat.
        Since the VolcEngine authentication method is special, we parse the api_key as a dictionary.
        
        Args:
            api_key: JSON string containing ark_api_key and ep_id/endpoint_id
            model_name: Model name (for display only)
            base_url: API base URL
            **kwargs: Additional configuration options
        """
        base_url = base_url if base_url else "https://ark.cn-beijing.volces.com/api/v3"
        key_data = json.loads(api_key)
        ark_api_key = key_data.get("ark_api_key", "")
        actual_model_name = key_data.get("ep_id", "") + key_data.get("endpoint_id", "")
        super().__init__(actual_model_name, ark_api_key, base_url, **kwargs)
        

class HuggingFaceChat(BaseLLM):
    _FACTORY_NAME = "HuggingFace"

    def __init__(self, api_key: Optional[str] = None, model_name: str = "", base_url: str = "", **kwargs):
        if not base_url:
            raise ValueError("base_url cannot be None")
        base_url = urljoin(base_url, "v1")
        super().__init__(model_name.split("___")[0], api_key or "", base_url, **kwargs)


class ModelScopeChat(BaseLLM):
    _FACTORY_NAME = "ModelScope"

    def __init__(self, api_key: Optional[str] = None, model_name: str = "", base_url: str = "", **kwargs):
        if not base_url:
            raise ValueError("base_url cannot be None")
        base_url = urljoin(base_url, "v1")
        super().__init__(model_name.split("___")[0], api_key or "", base_url, **kwargs)


class BaiChuanChat(BaseLLM):
    _FACTORY_NAME = "BaiChuan"

    def __init__(self, api_key: str, model_name: str = "Baichuan3-Turbo", base_url: str = "https://api.baichuan-ai.com/v1", **kwargs):
        if not base_url:
            base_url = "https://api.baichuan-ai.com/v1"
        super().__init__(model_name, api_key, base_url, **kwargs)

    @staticmethod
    def _format_params(params):
        return {
            "temperature": params.get("temperature", 0.3),
            "top_p": params.get("top_p", 0.85),
        }

    def _clean_conf(self, gen_conf):
        return {
            "temperature": gen_conf.get("temperature", 0.3),
            "top_p": gen_conf.get("top_p", 0.85),
        }

    def _chat(self, history, gen_conf={}, **kwargs):
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=history,
            extra_body={"tools": [{"type": "web_search", "web_search": {"enable": True, "search_mode": "performance_first"}}]},
            **gen_conf,
        )
        ans = response.choices[0].message.content.strip()
        if response.choices[0].finish_reason == "length":
            if is_chinese([ans]):
                ans += LENGTH_NOTIFICATION_CN
            else:
                ans += LENGTH_NOTIFICATION_EN
        return ans, total_token_count_from_response(response)

    def chat_streamly(self, system, history, gen_conf={}, **kwargs):
        if system and history and history[0].get("role") != "system":
            history.insert(0, {"role": "system", "content": system})
        if "max_tokens" in gen_conf:
            del gen_conf["max_tokens"]
        ans = ""
        total_tokens = 0
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=history,
                extra_body={"tools": [{"type": "web_search", "web_search": {"enable": True, "search_mode": "performance_first"}}]},
                stream=True,
                **self._format_params(gen_conf),
            )
            for resp in response:
                if not resp.choices:
                    continue
                if not resp.choices[0].delta.content:
                    resp.choices[0].delta.content = ""
                ans = resp.choices[0].delta.content
                tol = total_token_count_from_response(resp)
                if not tol:
                    total_tokens += num_tokens_from_string(resp.choices[0].delta.content)
                else:
                    total_tokens = tol
                if resp.choices[0].finish_reason == "length":
                    if is_chinese([ans]):
                        ans += LENGTH_NOTIFICATION_CN
                    else:
                        ans += LENGTH_NOTIFICATION_EN
                yield ans

        except Exception as e:
            yield ans + "\n**ERROR**: " + str(e)

        yield total_tokens
        
        
class LocalAIChat(BaseLLM):
    _FACTORY_NAME = "LocalAI"

    def __init__(self, api_key: str, model_name: str, base_url: Optional[str] = None, **kwargs):
        if not base_url:
            raise ValueError("base_url cannot be None")
        base_url = urljoin(base_url, "v1")
        super().__init__(model_name.split("___")[0], "empty", base_url, **kwargs)
        self.client = OpenAI(api_key="empty", base_url=base_url)
        

class MistralChat(BaseLLM):
    _FACTORY_NAME = "Mistral"

    def __init__(self, api_key: str, model_name: str, base_url: Optional[str] = None, **kwargs):
        super().__init__(model_name, api_key, base_url or "", **kwargs)

        from mistralai.client import MistralClient

        self.client = MistralClient(api_key=api_key)
        self.model_name = model_name

    def _clean_conf(self, gen_conf):
        for k in list(gen_conf.keys()):
            if k not in ["temperature", "top_p", "max_tokens"]:
                del gen_conf[k]
        return gen_conf

    def _chat(self, history, gen_conf={}, **kwargs):
        gen_conf = self._clean_conf(gen_conf)
        response = self.client.chat(model=self.model_name, messages=history, **gen_conf)
        ans = response.choices[0].message.content
        if response.choices[0].finish_reason == "length":
            if is_chinese(ans):
                ans += LENGTH_NOTIFICATION_CN
            else:
                ans += LENGTH_NOTIFICATION_EN
        return ans, total_token_count_from_response(response)

    def chat_streamly(self, system, history, gen_conf={}, **kwargs):
        if system and history and history[0].get("role") != "system":
            history.insert(0, {"role": "system", "content": system})
        gen_conf = self._clean_conf(gen_conf)
        ans = ""
        total_tokens = 0
        try:
            response = self.client.chat_stream(model=self.model_name, messages=history, **gen_conf, **kwargs)
            for resp in response:
                if not resp.choices or not resp.choices[0].delta.content:
                    continue
                ans = resp.choices[0].delta.content
                total_tokens += 1
                if resp.choices[0].finish_reason == "length":
                    if is_chinese(ans):
                        ans += LENGTH_NOTIFICATION_CN
                    else:
                        ans += LENGTH_NOTIFICATION_EN
                yield ans

        except openai.APIError as e:
            yield ans + "\n**ERROR**: " + str(e)

        yield total_tokens


class LmStudioChat(BaseLLM):
    _FACTORY_NAME = "LM-Studio"

    def __init__(self, api_key: str, model_name: str, base_url: str, **kwargs):
        if not base_url:
            raise ValueError("base_url cannot be None")
        base_url = urljoin(base_url, "v1")
        super().__init__(model_name, "lm-studio", base_url, **kwargs)
        self.client = OpenAI(api_key="lm-studio", base_url=base_url)


class OpenAI_APIChat(BaseLLM):
    _FACTORY_NAME = ["VLLM", "OpenAI-API-Compatible"]

    def __init__(self, api_key: str, model_name: str, base_url: str, **kwargs):
        if not base_url:
            raise ValueError("base_url cannot be None")
        model_name = model_name.split("___")[0]
        super().__init__(model_name, api_key, base_url, **kwargs)


class LeptonAIChat(BaseLLM):
    _FACTORY_NAME = "LeptonAI"

    def __init__(self, api_key: str, model_name: str, base_url: Optional[str] = None, **kwargs):
        if not base_url:
            base_url = urljoin("https://" + model_name + ".lepton.run", "api/v1")
        super().__init__(model_name, api_key, base_url, **kwargs)



class SparkChat(BaseLLM):
    _FACTORY_NAME = "XunFei Spark"

    def __init__(self, api_key: str, model_name: str, base_url: str = "https://spark-api-open.xf-yun.com/v1", **kwargs):
        if not base_url:
            base_url = "https://spark-api-open.xf-yun.com/v1"
        model2version = {
            "Spark-Max": "generalv3.5",
            "Spark-Lite": "general",
            "Spark-Pro": "generalv3",
            "Spark-Pro-128K": "pro-128k",
            "Spark-4.0-Ultra": "4.0Ultra",
        }
        version2model = {v: k for k, v in model2version.items()}
        assert model_name in model2version or model_name in version2model, f"The given model name is not supported yet. Support: {list(model2version.keys())}"
        if model_name in model2version:
            model_version = model2version[model_name]
        else:
            model_version = model_name
        super().__init__(model_version, api_key, base_url, **kwargs)


class BaiduYiyanChat(BaseLLM):
    _FACTORY_NAME = "BaiduYiyan"

    def __init__(self, api_key: str, model_name: str, base_url: Optional[str] = None, **kwargs):
        super().__init__(model_name.lower(), "", base_url or "", **kwargs)

        import qianfan

        key_data = json.loads(api_key)
        ak = key_data.get("yiyan_ak", "")
        sk = key_data.get("yiyan_sk", "")
        self.client = qianfan.ChatCompletion(ak=ak, sk=sk)
        self.model_name = model_name.lower()

    def _clean_conf(self, gen_conf):
        gen_conf["penalty_score"] = ((gen_conf.get("presence_penalty", 0) + gen_conf.get("frequency_penalty", 0)) / 2) + 1
        if "max_tokens" in gen_conf:
            del gen_conf["max_tokens"]
        return gen_conf

    def _chat(self, history, gen_conf):
        system = history[0]["content"] if history and history[0]["role"] == "system" else ""
        response = self.client.do(model=self.model_name, messages=[h for h in history if h["role"] != "system"], system=system, **gen_conf).body
        ans = response["result"]
        return ans, total_token_count_from_response(response)

    def chat_streamly(self, system, history, gen_conf={}, **kwargs):
        gen_conf["penalty_score"] = ((gen_conf.get("presence_penalty", 0) + gen_conf.get("frequency_penalty", 0)) / 2) + 1
        if "max_tokens" in gen_conf:
            del gen_conf["max_tokens"]
        ans = ""
        total_tokens = 0

        try:
            response = self.client.do(model=self.model_name, messages=history, system=system, stream=True, **gen_conf)
            for resp in response:
                resp = resp.body
                ans = resp["result"]
                total_tokens = total_token_count_from_response(resp)

                yield ans

        except Exception as e:
            return ans + "\n**ERROR**: " + str(e), 0

        yield total_tokens


class GoogleChat(BaseLLM):
    _FACTORY_NAME = "Google Cloud"

    def __init__(self, api_key: str, model_name: str, base_url: Optional[str] = None, **kwargs):
        super().__init__(model_name, "", base_url or "", **kwargs)

        import base64
        from google.oauth2 import service_account

        key_data = json.loads(api_key)
        service_account_key = key_data.get("google_service_account_key", "")
        access_token = json.loads(base64.b64decode(service_account_key)) if service_account_key else None
        project_id = key_data.get("google_project_id", "")
        region = key_data.get("google_region", "")

        scopes = ["https://www.googleapis.com/auth/cloud-platform"]
        self.model_name = model_name

        if "claude" in self.model_name:
            from anthropic import AnthropicVertex
            from google.auth.transport.requests import Request

            if access_token:
                credits = service_account.Credentials.from_service_account_info(access_token, scopes=scopes)
                request = Request()
                credits.refresh(request)
                token = credits.token
                self.client = AnthropicVertex(region=region, project_id=project_id, access_token=token)
            else:
                self.client = AnthropicVertex(region=region, project_id=project_id)
        else:
            from google import genai

            if access_token:
                credits = service_account.Credentials.from_service_account_info(access_token, scopes=scopes)
                self.client = genai.Client(vertexai=True, project=project_id, location=region, credentials=credits)
            else:
                self.client = genai.Client(vertexai=True, project=project_id, location=region)

    def _clean_conf(self, gen_conf):
        if "claude" in self.model_name:
            if "max_tokens" in gen_conf:
                del gen_conf["max_tokens"]
        else:
            if "max_tokens" in gen_conf:
                gen_conf["max_output_tokens"] = gen_conf["max_tokens"]
                del gen_conf["max_tokens"]
            for k in list(gen_conf.keys()):
                if k not in ["temperature", "top_p", "max_output_tokens"]:
                    del gen_conf[k]
        return gen_conf

    def _chat(self, history, gen_conf={}, **kwargs):
        system = history[0]["content"] if history and history[0]["role"] == "system" else ""

        if "claude" in self.model_name:
            gen_conf = self._clean_conf(gen_conf)
            response = self.client.messages.create(
                model=self.model_name,
                messages=[h for h in history if h["role"] != "system"],
                system=system,
                stream=False,
                **gen_conf,
            ).json()
            ans = response["content"][0]["text"]
            if response["stop_reason"] == "max_tokens":
                ans += "...\nFor the content length reason, it stopped, continue?" if is_english([ans]) else "······\n由于长度的原因，回答被截断了，要继续吗？"
            return (
                ans,
                response["usage"]["input_tokens"] + response["usage"]["output_tokens"],
            )

        # Gemini models with google-genai SDK
        # Set default thinking_budget=0 if not specified
        if "thinking_budget" not in gen_conf:
            gen_conf["thinking_budget"] = 0

        thinking_budget = gen_conf.pop("thinking_budget", 0)
        gen_conf = self._clean_conf(gen_conf)

        # Build GenerateContentConfig
        try:
            from google.genai.types import Content, GenerateContentConfig, Part, ThinkingConfig
        except ImportError as e:
            logging.error(f"[GoogleChat] Failed to import google-genai: {e}. Please install: pip install google-genai>=1.41.0")
            raise

        config_dict = {}
        if system:
            config_dict["system_instruction"] = system
        if "temperature" in gen_conf:
            config_dict["temperature"] = gen_conf["temperature"]
        if "top_p" in gen_conf:
            config_dict["top_p"] = gen_conf["top_p"]
        if "max_output_tokens" in gen_conf:
            config_dict["max_output_tokens"] = gen_conf["max_output_tokens"]

        # Add ThinkingConfig
        config_dict["thinking_config"] = ThinkingConfig(thinking_budget=thinking_budget)

        config = GenerateContentConfig(**config_dict)

        # Convert history to google-genai Content format
        contents = []
        for item in history:
            if item["role"] == "system":
                continue
            # google-genai uses 'model' instead of 'assistant'
            role = "model" if item["role"] == "assistant" else item["role"]
            content = Content(
                role=role,
                parts=[Part(text=item["content"])],
            )
            contents.append(content)

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=contents,
            config=config,
        )

        ans = response.text
        # Get token count from response
        try:
            total_tokens = response.usage_metadata.total_token_count
        except Exception:
            total_tokens = 0

        return ans, total_tokens

    def chat_streamly(self, system, history, gen_conf={}, **kwargs):
        if "claude" in self.model_name:
            if "max_tokens" in gen_conf:
                del gen_conf["max_tokens"]
            ans = ""
            total_tokens = 0
            try:
                response = self.client.messages.create(
                    model=self.model_name,
                    messages=history,
                    system=system,
                    stream=True,
                    **gen_conf,
                )
                for res in response.iter_lines():
                    res = res.decode("utf-8")
                    if "content_block_delta" in res and "data" in res:
                        text = json.loads(res[6:])["delta"]["text"]
                        ans = text
                        total_tokens += num_tokens_from_string(text)
            except Exception as e:
                yield ans + "\n**ERROR**: " + str(e)

            yield total_tokens
        else:
            # Gemini models with google-genai SDK
            ans = ""
            total_tokens = 0

            # Set default thinking_budget=0 if not specified
            if "thinking_budget" not in gen_conf:
                gen_conf["thinking_budget"] = 0

            thinking_budget = gen_conf.pop("thinking_budget", 0)
            gen_conf = self._clean_conf(gen_conf)

            # Build GenerateContentConfig
            try:
                from google.genai.types import Content, GenerateContentConfig, Part, ThinkingConfig
            except ImportError as e:
                logging.error(f"[GoogleChat] Failed to import google-genai: {e}. Please install: pip install google-genai>=1.41.0")
                raise

            config_dict = {}
            if system:
                config_dict["system_instruction"] = system
            if "temperature" in gen_conf:
                config_dict["temperature"] = gen_conf["temperature"]
            if "top_p" in gen_conf:
                config_dict["top_p"] = gen_conf["top_p"]
            if "max_output_tokens" in gen_conf:
                config_dict["max_output_tokens"] = gen_conf["max_output_tokens"]

            # Add ThinkingConfig
            config_dict["thinking_config"] = ThinkingConfig(thinking_budget=thinking_budget)

            config = GenerateContentConfig(**config_dict)

            # Convert history to google-genai Content format
            contents = []
            for item in history:
                # google-genai uses 'model' instead of 'assistant'
                role = "model" if item["role"] == "assistant" else item["role"]
                content = Content(
                    role=role,
                    parts=[Part(text=item["content"])],
                )
                contents.append(content)

            try:
                for chunk in self.client.models.generate_content_stream(
                    model=self.model_name,
                    contents=contents,
                    config=config,
                ):
                    text = chunk.text
                    ans = text
                    total_tokens += num_tokens_from_string(text)
                    yield ans

            except Exception as e:
                yield ans + "\n**ERROR**: " + str(e)

            yield total_tokens


class TokenPonyChat(BaseLLM):
    _FACTORY_NAME = "TokenPony"

    def __init__(self, api_key: str, model_name: str, base_url: str = "https://ragflow.vip-api.tokenpony.cn/v1", **kwargs):
        if not base_url:
            base_url = "https://ragflow.vip-api.tokenpony.cn/v1"
        super().__init__(model_name, api_key, base_url, **kwargs)