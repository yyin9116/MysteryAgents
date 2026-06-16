"""
Discussion mode data models.
自由讨论模式的数据模型
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime
from enum import Enum


class DiscussionStatus(str, Enum):
    """讨论状态"""
    CREATED = "created"
    ACTIVE = "active"
    PAUSED = "paused"
    ENDED = "ended"


class MessageType(str, Enum):
    """消息类型"""
    AGENT = "agent"
    USER = "user"
    SYSTEM = "system"


class DiscussionMessage(BaseModel):
    """讨论消息"""
    id: str
    discussion_id: str
    speaker_id: str
    speaker_name: str
    speaker_type: MessageType
    content: str
    thought: Optional[str] = None  # 仅 Agent 有
    agree_with: List[str] = Field(default_factory=list)
    disagree_with: List[str] = Field(default_factory=list)
    sentiment: str = "neutral"  # positive, neutral, negative
    mentions: List[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.now)


class DiscussionConfig(BaseModel):
    """讨论配置"""
    topic: str = Field(..., min_length=1, max_length=500)
    agent_count: int = Field(default=6, ge=3, le=10)
    use_balanced_team: bool = True
    max_rounds: Optional[int] = None
    agents: List[Dict[str, str]] = Field(default_factory=list)
    # 模型配置
    model_provider: Optional[str] = None
    model_name: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None


class Discussion(BaseModel):
    """讨论会话"""
    id: str
    topic: str
    agents: List[Dict]
    messages: List[DiscussionMessage] = Field(default_factory=list)
    status: DiscussionStatus = DiscussionStatus.CREATED
    current_round: int = 0
    created_at: datetime = Field(default_factory=datetime.now)
    ended_at: Optional[datetime] = None
