import sys
from datetime import datetime
from typing import Literal,TypeAlias
if sys.version_info>=(3,8):
    from typing import TypedDict,Required
else:
    from typing_extensions import TypedDict,Required

from pydantic import BaseModel

# >>>>>>>>>> Message Types >>>>>>>>>>

# Chat Message types
MessageRole:TypeAlias=Literal["user","assistant","system"]

# Messagt structure

class MessageDict(TypedDict):
    """Typed dictionary for chat message dictionaries."""
    role:Required[MessageRole]
    content:Required[str]
    # chat_time:str | None # Optional 消息的可选时间戳，格式不受限制，可以是任何模糊或精确的时间字符串。
    # message_id: str | None # Optional 消息的可选ID，用于唯一标识消息。
    
    # """An optional name for the participant.

    # Provides the model information to differentiate between participants of the same
    # role.
    # """
    # name: str|None
    
    
# Message collection
MessageList:TypeAlias=list[MessageDict]

# Chat history structure
class ChatHistoryDict(BaseModel):
    """Model to represent chat history for export."""
    user_id:str
    session_id:str
    created_at:datetime
    total_messages:int
    chat_history:MessageList
    




# >>>>>>>>>> API Types >>>>>>>>>>
# for API Permission
Permission: TypeAlias = Literal["read", "write", "delete", "execute"]


# Message structure
class PermissionDict(TypedDict, total=False):
    """用于聊天消息字典的类型化字典。"""

    permissions: list[Permission]
    mem_cube_id: str


class UserContext(BaseModel):
    """Model to represent user context."""

    user_id: str | None = None
    mem_cube_id: str | None = None
    session_id: str | None = None
    operation: list[PermissionDict] | None = None
