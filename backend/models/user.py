"""
User identity and profile models.
"""

from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import date, datetime


class UserIdentityInput(BaseModel):
    """Input for creating user identity."""
    method: Literal["birthday", "manual"] = Field(..., description="Method of MBTI determination")
    birthday: Optional[date] = None
    mbti: Optional[str] = Field(None, min_length=4, max_length=4)
    nickname: Optional[str] = Field(None, max_length=50)
    gender: Optional[Literal["male", "female", "other"]] = None


class UserProfile(BaseModel):
    """User profile with MBTI and gender information."""
    user_id: str = Field(..., description="Unique user identifier")
    mbti_type: str = Field(..., min_length=4, max_length=4, description="MBTI type")
    gender: str = Field(..., description="User gender")
    birthday: Optional[str] = Field(None, description="User birthday")
    created_at: datetime = Field(default_factory=datetime.now)
