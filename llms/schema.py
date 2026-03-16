from email.mime import image
from math import e
import sys
import os
from typing import Literal,TypeAlias
if sys.version_info>=(3,8):
    from typing import TypedDict,Required
from typing import List, Literal, Optional, Tuple, Union

from pydantic import BaseModel, field_validator, model_validator
from common.utils_cv import ImageBase64
from common.utils_file import VIDEO_FORMAT,IMG_FORMAT
# Chat Message types
MessageRole:TypeAlias=Literal["user","assistant","system"]


ROLE="role"
SYSTEM="system"
USER="user"
ASSISTANT="assistant"
FUNCTION="function"


class ChatItemText(TypedDict,total=False):
    type:Required[Literal["text"]]
    text:Required[str]
    
class ChatItemImage(TypedDict,total=False):
    type:Required[Literal["image_url"]]
    image_url:Required[dict]
    
class ChatItemVideo(TypedDict,total=False):
    type:Required[Literal["video_url"]]
    video_url:Required[dict]
class ChatItemAudio(TypedDict,total=False):
    type:Required[Literal["audio_url"]]
    audio_url:Required[dict]

class ChatSystemMessage(TypedDict,total=False):
    role:Required[Literal["system"]]
    content:Required[str]
class ChatUserMessage(TypedDict,total=False):
    role:Required[Literal["user"]]
    content:Required[List[dict]]


class ChatAssistantMessage(TypedDict,total=False):
    role:Required[Literal["assistant"]]
    content:Required[str]
    
    
class ChatMessage:
    def __init__(self,user_prompt=None,system_prompt=None,*,file_path:str|list="",messages:list=[]):
        self.user_prompt=user_prompt
        self.system_prompt=system_prompt
        self.file_path=file_path
        self.messages=messages
    
    def to_message(self,user_prompt,system_prompt=None,*,file_path:str|list="",messages:list=[]):
        if system_prompt and messages and messages[0]["role"]!="system":
            messages.insert(0,{"role":"system","content":system_prompt})
        
        user_content=[]
        if file_path:
            if isinstance(file_path,str):
                file_path=[file_path]
           
            for path in file_path:
                print(path)
                
                if not os.path.isfile(path):continue
                ext=path.split(".")[-1].lower()
                if ext in IMG_FORMAT:
                    
                    if path.startswith("http"):
                        image_content={
                            "type": "image_url",
                            "image_url": {
                                "url": f"{path}"
                            }
                        }
                    elif os.path.isfile(path):
                        
                        image_base64=ImageBase64.image_as_base64(path)
                        
                        if not image_base64.startswith("data:image"):
                            image_base64=f"data:image/png;base64,{image_base64}"
                            
                        image_content={
                            "type": "image_url",
                            "image_url": {
                                "url": f"{image_base64}"
                            }
                        }
                    else:
                        raise ValueError(f"Unsupported file format: {ext}, or file_path={path} not exists")
                    
                    user_content.append(image_content)
                elif ext in VIDEO_FORMAT:
                    if path.startswith("http"):
                        video_content={
                            "type": "video_url",
                            "video_url": {
                                "url": f"{path}"
                            }
                        }
                    elif os.path.isfile(path):
                        print("TODO video_url") 
                        
                    else:
                        raise ValueError(f"Unsupported file format: {ext}, or file_path={path} not exists")
                else:
                    raise ValueError(f"Unsupported file format: {ext},file_path={path}")
        
        user_content.append({"type": "text","text": user_prompt})
        messages.append({"role": "user","content": user_content})
        
        return messages
    
    def update_messages(self,user_prompt,system_prompt=None,*,file_path:str|list="",messages:list=[]):
        self.user_prompt=user_prompt
        self.system_prompt=system_prompt
        self.file_path=file_path
        
        self.messages=self.to_message(user_prompt,system_prompt,file_path=file_path,messages=messages)
        
    def add_assistant_message(self,assistant_content):
        self.messages.append({"role": "assistant","content": assistant_content})
        
    def get_messages(self):
        return self.messages
    
    def clear_messages(self):
        self.messages=[]
        
        



