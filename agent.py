import os
import asyncio
import sqlite3
import logging
import argparse
from datetime import datetime
from typing import List, Dict, Any, Optional

import mimetypes
from aiohttp import web

from llms.chats import BaseLLM
from llms.schema import ChatMessage

from memorydb import MemoryDB

MEDIA_EXTENSIONS = {
    # Images
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
    ".svg": "image/svg+xml",
    # Audio
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".ogg": "audio/ogg",
    ".flac": "audio/flac",
    ".m4a": "audio/mp4",
    ".aac": "audio/aac",
    # Video
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".mov": "video/quicktime",
    ".avi": "video/x-msvideo",
    ".mkv": "video/x-matroska",
    # Documents
    ".pdf": "application/pdf",
}

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# # 数据库操作类
# class MemoryDB:
#     def __init__(self, db_path: str = 'memory.db'):
#         self.db_path = db_path
#         self._init_db()
    
#     def _init_db(self):
#         """初始化数据库表"""
#         with sqlite3.connect(self.db_path) as conn:
#             cursor = conn.cursor()
#             # 记忆表
#             cursor.execute('''
#             CREATE TABLE IF NOT EXISTS memories (
#                 id INTEGER PRIMARY KEY AUTOINCREMENT,
#                 raw_text TEXT,
#                 summary TEXT,
#                 entities TEXT,
#                 topics TEXT,
#                 importance REAL,
#                 source TEXT,
#                 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
#                 consolidated BOOLEAN DEFAULT 0
#             )
#             ''')
#             # 整合表
#             cursor.execute('''
#             CREATE TABLE IF NOT EXISTS consolidations (
#                 id INTEGER PRIMARY KEY AUTOINCREMENT,
#                 source_ids TEXT,
#                 summary TEXT,
#                 insight TEXT,
#                 connections TEXT,
#                 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
#             )
#             ''')
#             conn.commit()
    
#     def store_memory(self, raw_text: str, summary: str, entities: List[str], 
#                     topics: List[str], importance: float, source: str) -> Dict[str, Any]:
#         """存储记忆"""
#         with sqlite3.connect(self.db_path) as conn:
#             cursor = conn.cursor()
#             cursor.execute(
#                 '''INSERT INTO memories (raw_text, summary, entities, topics, importance, source) 
#                 VALUES (?, ?, ?, ?, ?, ?)''',
#                 (raw_text, summary, str(entities), str(topics), importance, source)
#             )
#             memory_id = cursor.lastrowid
#             conn.commit()
#         return {"memory_id": memory_id, "message": "记忆存储成功"}
    
#     def read_unconsolidated_memories(self) -> Dict[str, Any]:
#         """读取未整合的记忆"""
#         with sqlite3.connect(self.db_path) as conn:
#             cursor = conn.cursor()
#             cursor.execute(
#                 '''SELECT id, raw_text, summary, entities, topics, importance, source, created_at 
#                 FROM memories WHERE consolidated = 0 ORDER BY created_at DESC'''
#             )
#             memories = []
#             for row in cursor.fetchall():
#                 memories.append({
#                     "id": row[0],
#                     "raw_text": row[1],
#                     "summary": row[2],
#                     "entities": eval(row[3]),
#                     "topics": eval(row[4]),
#                     "importance": row[5],
#                     "source": row[6],
#                     "created_at": row[7]
#                 })
#         return {"memories": memories, "count": len(memories)}
    
#     def store_consolidation(self, source_ids: List[int], summary: str, 
#                           insight: str, connections: List[Dict[str, Any]]) -> Dict[str, Any]:
#         """存储整合结果"""
#         with sqlite3.connect(self.db_path) as conn:
#             cursor = conn.cursor()
#             cursor.execute(
#                 '''INSERT INTO consolidations (source_ids, summary, insight, connections) 
#                 VALUES (?, ?, ?, ?)''',
#                 (str(source_ids), summary, insight, str(connections))
#             )
#             # 标记源记忆为已整合
#             cursor.execute(
#                 "UPDATE memories SET consolidated = 1 WHERE id IN (" + ",".join([str(id) for id in source_ids]) + ")"
#             )
#             conn.commit()
#         return {"message": "整合结果存储成功"}
    
#     def read_all_memories(self) -> Dict[str, Any]:
#         """读取所有记忆"""
#         with sqlite3.connect(self.db_path) as conn:
#             cursor = conn.cursor()
#             cursor.execute(
#                 '''SELECT id, raw_text, summary, entities, topics, importance, source, created_at 
#                 FROM memories ORDER BY created_at DESC'''
#             )
#             memories = []
#             for row in cursor.fetchall():
#                 memories.append({
#                     "id": row[0],
#                     "raw_text": row[1],
#                     "summary": row[2],
#                     "entities": eval(row[3]),
#                     "topics": eval(row[4]),
#                     "importance": row[5],
#                     "source": row[6],
#                     "created_at": row[7]
#                 })
#         return {"memories": memories, "count": len(memories)}
    
#     def read_consolidation_history(self) -> Dict[str, Any]:
#         """读取整合历史"""
#         with sqlite3.connect(self.db_path) as conn:
#             cursor = conn.cursor()
#             cursor.execute(
#                 '''SELECT id, source_ids, summary, insight, connections, created_at 
#                 FROM consolidations ORDER BY created_at DESC'''
#             )
#             consolidations = []
#             for row in cursor.fetchall():
#                 consolidations.append({
#                     "id": row[0],
#                     "source_ids": eval(row[1]),
#                     "summary": row[2],
#                     "insight": row[3],
#                     "connections": eval(row[4]),
#                     "created_at": row[5]
#                 })
#         return {"consolidations": consolidations}
    
#     def get_memory_stats(self) -> Dict[str, Any]:
#         """获取记忆统计信息"""
#         with sqlite3.connect(self.db_path) as conn:
#             cursor = conn.cursor()
#             # 总记忆数
#             cursor.execute("SELECT COUNT(*) FROM memories")
#             total_memories = cursor.fetchone()[0]
#             # 未整合记忆数
#             cursor.execute("SELECT COUNT(*) FROM memories WHERE consolidated = 0")
#             unconsolidated_memories = cursor.fetchone()[0]
#             # 整合次数
#             cursor.execute("SELECT COUNT(*) FROM consolidations")
#             consolidation_count = cursor.fetchone()[0]
#         return {
#             "total_memories": total_memories,
#             "unconsolidated_memories": unconsolidated_memories,
#             "consolidation_count": consolidation_count
#         }
    
#     def delete_memory(self, memory_id: int) -> Dict[str, Any]:
#         """删除记忆"""
#         with sqlite3.connect(self.db_path) as conn:
#             cursor = conn.cursor()
#             cursor.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
#             conn.commit()
#         return {"message": "记忆删除成功"}
    
#     def clear_all_memories(self) -> Dict[str, Any]:
#         """清空所有记忆"""
#         with sqlite3.connect(self.db_path) as conn:
#             cursor = conn.cursor()
#             cursor.execute("DELETE FROM memories")
#             cursor.execute("DELETE FROM consolidations")
#             conn.commit()
#         return {"message": "所有记忆已清空"}

# 工具调用会话类
class ToolCallSession:
    def __init__(self, db: MemoryDB):
        self.db = db
    
    def tool_call(self, name: str, args: Dict[str, Any]) -> str:
        """工具调用方法"""
        if name == "store_memory":
            return str(self.db.store_memory(
                args.get("raw_text"),
                args.get("summary"),
                args.get("entities", []),
                args.get("topics", []),
                args.get("importance", 0.5),
                args.get("source", "unknown")
            ))
        elif name == "read_unconsolidated_memories":
            return str(self.db.read_unconsolidated_memories())
        elif name == "store_consolidation":
            return str(self.db.store_consolidation(
                args.get("source_ids", []),
                args.get("summary"),
                args.get("insight"),
                args.get("connections", [])
            ))
        elif name == "read_all_memories":
            return str(self.db.read_all_memories())
        elif name == "read_consolidation_history":
            return str(self.db.read_consolidation_history())
        elif name == "get_memory_stats":
            return str(self.db.get_memory_stats())
        else:
            return f"未知工具: {name}"

# 智能体基类
class BaseAgent:
    def __init__(self, llm: BaseLLM, tool_session: ToolCallSession):
        self.llm = llm
        self.tool_session = tool_session
    
    async def run(self, system_prompt: str="", history: List[Dict[str, str]] = [],gen_conf: Dict[str, Any] = {}) -> str:
        
        result, _ = await self.llm.async_chat_with_tools(
            system_prompt=system_prompt,
            history=history,
            gen_conf=gen_conf
        )
        return result,_

# 摄入智能体
class IngestAgent(BaseAgent):
    def __init__(self, llm: BaseLLM, tool_session: ToolCallSession):
        super().__init__(llm, tool_session)
        self.system_prompt = (
            "You are a Memory Ingest Agent. You handle ALL types of input — text, images,\n"
            "audio, video, and PDFs. For any input you receive:\n"
            "1. Thoroughly describe what the content contains\n"
            "2. Create a concise 1-2 sentence summary\n"
            "3. Extract key entities (people, companies, products, concepts, objects, locations)\n"
            "4. Assign 2-4 topic tags\n"
            "5. Rate importance from 0.0 to 1.0\n"
            "6. Call store_memory with all extracted information\n\n"
            "For images: describe the scene, objects, text, people, and any visual details.\n"
            "For audio/video: describe the spoken content, sounds, scenes, and key moments.\n"
            "For PDFs: extract and summarize the document content.\n\n"
            "Use the full description as raw_text in store_memory so the context is preserved.\n"
            "Always call store_memory. Be concise and accurate.\n"
            "After storing, confirm what was stored in one sentence."
        )
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "store_memory",
                    "description": "将处理后的记忆存储在数据库中",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "raw_text": {
                                "type": "string",
                                "description": "原始输入文本"
                            },
                            "summary": {
                                "type": "string",
                                "description": "简洁的1-2句话摘要"
                            },
                            "entities": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "关键人物、公司、产品或概念"
                            },
                            "topics": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "2-4个主题标签"
                            },
                            "importance": {
                                "type": "number",
                                "description": "表示重要性的0.0到1.0之间的浮点数"
                            },
                            "source": {
                                "type": "string",
                                "description": "该记忆的来源（文件名、URL等）"
                            }
                        },
                        "required": ["raw_text", "summary", "entities", "topics", "importance", "source"]
                    }
                }
            }
        ]
        self.llm.bind_tools(self.tool_session, self.tools)
    
    async def process(self, user_prompt: str="", source: str = "") -> str:
        """处理输入内容"""
        
        if os.path.isfile(source):
            suffix = os.path.splitext(source)[-1].lower()
            mime_type = MEDIA_EXTENSIONS.get(suffix)
            if not mime_type:
                # Fallback to mimetypes module
                mime_type, _ = mimetypes.guess_type(str(source))
                mime_type = mime_type or "application/octet-stream"

            # file_bytes = source.read_bytes()
            # size_mb = len(file_bytes) / (1024 * 1024)
            
            user_prompt=(
            f"Remember this file (source: {os.path.basename(source)}, type: {mime_type}).\n\n"
            f"Thoroughly analyze the content of this {mime_type.split('/')[0]} file and "
            f"extract all meaningful information for memory storage."
        )
            message=ChatMessage().to_message(
                user_prompt=user_prompt,
                system_prompt=self.system_prompt,
                file_path=source,
                )
        else:
            user_prompt=f"Remember this information (source: {source}):\n\n{user_prompt}" if source else f"Remember this information:\n\n{user_prompt}"
            message=ChatMessage().to_message(
                user_prompt=user_prompt,
                system_prompt=self.system_prompt,
                )
        # print(message)
        result,_ = await self.run(
            system_prompt=self.system_prompt,
            history=message,
            gen_conf={"temperature": 0.}
        )
        print(f"======>>Ingested:\n {result}")
        return result

# 整合智能体
class ConsolidateAgent(BaseAgent):
    def __init__(self, llm: BaseLLM, tool_session: ToolCallSession):
        super().__init__(llm, tool_session)
        self.system_prompt = (
            "You are a Memory Consolidation Agent. You:\n"
            "1. Call read_unconsolidated_memories to see what needs processing\n"
            "2. If fewer than 2 memories, say nothing to consolidate\n"
            "3. Find connections and patterns across the memories\n"
            "4. Create a synthesized summary and one key insight\n"
            "5. Call store_consolidation with source_ids, summary, insight, and connections\n\n"
            "Connections: list of dicts with 'from_id', 'to_id', 'relationship' keys.\n"
            "Think deeply about cross-cutting patterns."
        )
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "read_unconsolidated_memories",
                    "description": "读取尚未整合的记忆",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "store_consolidation",
                    "description": "存储整合结果，并将源记忆标记为已整合",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "source_ids": {
                                "type": "array",
                                "items": {"type": "integer"},
                                "description": "已整合的记忆ID列表"
                            },
                            "summary": {
                                "type": "string",
                                "description": "所有源记忆的综合摘要"
                            },
                            "insight": {
                                "type": "string",
                                "description": "发现的一个关键模式或见解"
                            },
                            "connections": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "from_id": {
                                            "type": "integer",
                                            "description": "起始记忆ID"
                                        },
                                        "to_id": {
                                            "type": "integer",
                                            "description": "目标记忆ID"
                                        },
                                        "relationship": {
                                            "type": "string",
                                            "description": "它们之间的关系"
                                        }
                                    },
                                    "required": ["from_id", "to_id", "relationship"]
                                },
                                "description": "包含'from_id'、'to_id'、'relationship'的字典列表"
                            }
                        },
                        "required": ["source_ids", "summary", "insight", "connections"]
                    }
                }
            }
        ]
        self.llm.bind_tools(self.tool_session, self.tools)
    
    async def process(self) -> str:
        """执行整合"""
        history = [{"role": "system", "content": self.system_prompt},
                   {"role": "user", "content": "请执行记忆整合"}]
        result, _ = await self.run(
            system_prompt=self.system_prompt,
            history=history,
            gen_conf={"temperature": 0.}
        )
        print(f"======>>ConsolidateAgent:\n {result}")
        return result

# 查询智能体
class QueryAgent(BaseAgent):
    def __init__(self, llm: BaseLLM, tool_session: ToolCallSession):
        super().__init__(llm, tool_session)
        self.system_prompt = (
            "You are a Memory Query Agent. When asked a question:\n"
            "1. Call read_all_memories to access the memory store\n"
            "2. Call read_consolidation_history for higher-level insights\n"
            "3. Synthesize an answer based ONLY on stored memories\n"
            "4. Reference memory IDs: [Memory 1], [Memory 2], etc.\n"
            "5. If no relevant memories exist, say so honestly\n\n"
            "Be thorough but concise. Always cite sources."
        )
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "read_all_memories",
                    "description": "从数据库中读取所有存储的记忆，按最新的在前排序",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "read_consolidation_history",
                    "description": "读取过往的整合见解",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            }
        ]
        self.llm.bind_tools(self.tool_session, self.tools)
    
    async def process(self, question: str) -> str:
        """处理查询"""
        message=ChatMessage().to_message(
            user_prompt=question,
            system_prompt=self.system_prompt,
        )
        result, _ = await self.run(
            system_prompt=self.system_prompt,
            history=message,
            gen_conf={"temperature": 0.}
        )
        print(f"======>>QueryAgent:\n {result}")
        return result

# 协调智能体
class OrchestratorAgent:
    def __init__(self, llm: BaseLLM, tool_session: ToolCallSession, 
                 ingest_agent: IngestAgent, consolidate_agent: ConsolidateAgent, 
                 query_agent: QueryAgent):
        self.llm = llm
        self.tool_session = tool_session
        self.ingest_agent = ingest_agent
        self.consolidate_agent = consolidate_agent
        self.query_agent = query_agent
        self.system_prompt = (
            "You are the Memory Orchestrator for an always-on memory system.\n"
            "Route requests to the right sub-agent:\n"
            "- New information -> ingest_agent\n"
            "- Consolidation request -> consolidate_agent\n"
            "- Questions -> query_agent\n"
            "- Status check -> call get_memory_stats and report\n\n"
            "After the sub-agent completes, give a brief summary."
        )
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_memory_stats",
                    "description": "获取当前内存统计信息",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            }
        ]
        self.llm.bind_tools(self.tool_session, self.tools)
    
    async def process(self, request: str) -> str:
        """处理请求"""
        # 简单的路由逻辑
        if any(keyword in request.lower() for keyword in ["status", "统计", "状态"]):
            # 状态检查
            stats = self.tool_session.tool_call("get_memory_stats", {})
            return f"记忆系统状态:\n{stats}"
        elif any(keyword in request.lower() for keyword in ["consolidate", "整合"]):
            # 整合请求
            result = await self.consolidate_agent.process()
            return f"整合完成:\n{result}"
        elif any(keyword in request.lower() for keyword in ["ingest", "摄入", "添加", "存储"]):
            # 摄入请求
            # 提取内容和来源
            content = request
            source = "user_input"
            result = await self.ingest_agent.process(content, source)
            return f"摄入完成:\n{result}"
        else:
            # 查询请求
            result = await self.query_agent.process(request)
            return f"查询结果:\n{result}"

# HTTP API处理
class MemoryAgentAPI:
    def __init__(self, orchestrator: OrchestratorAgent, db: MemoryDB):
        self.orchestrator = orchestrator
        self.db = db
    
    async def handle_status(self, request):
        stats = self.db.get_memory_stats()
        return web.json_response(stats)
    
    async def handle_memories(self, request):
        memories = self.db.read_all_memories()
        return web.json_response(memories)
    
    async def handle_ingest(self, request):
        data = await request.json()
        text = data.get("text", "")
        source = data.get("source", "api")
        result = await self.orchestrator.ingest_agent.process(text, source)
        return web.json_response({"result": result})
    
    async def handle_query(self, request):
        question = request.query.get("q", "")
        result = await self.orchestrator.query_agent.process(question)
        return web.json_response({"result": result})
    
    async def handle_consolidate(self, request):
        result = await self.orchestrator.consolidate_agent.process()
        return web.json_response({"result": result})
    
    async def handle_delete(self, request):
        data = await request.json()
        memory_id = data.get("memory_id")
        result = self.db.delete_memory(memory_id)
        return web.json_response(result)
    
    async def handle_clear(self, request):
        result = self.db.clear_all_memories()
        return web.json_response(result)
    
    def setup_routes(self, app):
        app.add_routes([
            web.get('/status', self.handle_status),
            web.get('/memories', self.handle_memories),
            web.post('/ingest', self.handle_ingest),
            web.get('/query', self.handle_query),
            web.post('/consolidate', self.handle_consolidate),
            web.post('/delete', self.handle_delete),
            web.post('/clear', self.handle_clear),
        ])

# 文件监听
async def watch_directory(inbox_dir: str, ingest_agent: IngestAgent):
    """监听目录中的新文件"""
    import os
    import time
    from common.utils_file import read_file_content, ensure_directory
    
    # 确保目录存在
    ensure_directory(inbox_dir)
    logger.info(f"开始监听目录: {inbox_dir}")
    
    # 使用字典存储文件的修改时间，以便检测新文件或修改的文件
    file_mod_times = {}
    
    while True:
        try:
            files = os.listdir(inbox_dir)
            for file in files:
                file_path = os.path.join(inbox_dir, file)
                if os.path.isfile(file_path):
                    # 获取文件的修改时间
                    mod_time = os.path.getmtime(file_path)
                    
                    # 检查是否是新文件或修改过的文件
                    if file_path not in file_mod_times or mod_time > file_mod_times[file_path]:
                        try:
                            logger.info(f"处理文件: {file_path}")
                            # content = read_file_content(file_path)
                            await ingest_agent.process("", file_path)
                            # 更新文件修改时间
                            file_mod_times[file_path] = mod_time
                        except Exception as e:
                            logger.error(f"处理文件 {file_path} 时出错: {e}")
            await asyncio.sleep(5)  # 每5秒检查一次
        except Exception as e:
            logger.error(f"监听目录时出错: {e}")
            await asyncio.sleep(10)

# 定时整合
async def scheduled_consolidation(consolidate_agent: ConsolidateAgent, interval_minutes: int):
    """定时执行整合"""
    logger.info(f"设置定时整合，间隔: {interval_minutes} 分钟")
    while True:
        try:
            logger.info("执行定时整合")
            await consolidate_agent.process()
        except Exception as e:
            logger.error(f"定时整合时出错: {e}")
        await asyncio.sleep(interval_minutes * 60)

async def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="常驻记忆智能体")
    parser.add_argument('--watch', default='./inbox', help='监听目录（默认：./inbox）')
    parser.add_argument('--port', type=int, default=8888, help='API端口（默认：8888）')
    parser.add_argument('--consolidate-every', type=int, default=30, help='整合间隔（默认：30分钟）')
    args = parser.parse_args()
    
    # 初始化数据库
    db = MemoryDB()
    
    # 初始化工具会话
    tool_session = ToolCallSession(db)
    
    # 初始化LLM
    # 这里使用默认的模型配置，实际使用时需要从环境变量或配置文件读取
    llm = BaseLLM(
        model_name="gpt-4o",
        api_key=os.getenv("OPENAI_API_KEY"),
        api_base_url=os.getenv("OPENAI_BASE_URL"),
    )
    
    # 初始化智能体
    ingest_agent = IngestAgent(llm, tool_session)
    consolidate_agent = ConsolidateAgent(llm, tool_session)
    query_agent = QueryAgent(llm, tool_session)
    orchestrator = OrchestratorAgent(llm, tool_session, ingest_agent, consolidate_agent, query_agent)
    
    # 初始化API
    api = MemoryAgentAPI(orchestrator, db)
    app = web.Application(client_max_size=10*1024*1024)  # 10MB请求体大小限制
    api.setup_routes(app)
    
    # 启动任务
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', args.port)
    await site.start()
    
    print(">>> 记忆智能体已启动")
    # 启动文件监听和定时整合
    watch_task = asyncio.create_task(watch_directory(args.watch, ingest_agent))
    consolidate_task = asyncio.create_task(scheduled_consolidation(consolidate_agent, args.consolidate_every))
    
    logger.info(f"记忆智能体已启动，API端口: {args.port}")
    logger.info(f"监听目录: {args.watch}")
    logger.info(f"整合间隔: {args.consolidate_every} 分钟")
    
    # 保持运行
    try:
        await asyncio.gather(watch_task, consolidate_task)
    except KeyboardInterrupt:
        logger.info("正在关闭...")
        await runner.cleanup()

if __name__ == "__main__":
    asyncio.run(main())