"""
User API endpoints.

Handles user profile and identity configuration.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from datetime import datetime
import logging
logger = logging.getLogger(__name__)

from models.user import UserProfile

router = APIRouter(prefix="/api/user", tags=["user"])

# In-memory storage (in production, use database)
user_profiles: dict = {}


class CreateProfileRequest(BaseModel):
    """Request to create user profile."""
    method: str = Field(..., pattern=r'^(birthday|manual)$')
    birthday: Optional[str] = Field(None, description="Birthday in YYYY-MM-DD format")
    mbti_type: Optional[str] = Field(None, pattern=r'^[EI][NS][TF][JP]$')
    gender: str = Field(..., pattern=r'^(male|female|other)$')


class CreateProfileResponse(BaseModel):
    """Response after creating profile."""
    user_id: str
    mbti_type: str
    gender: str
    inferred: bool
    profile: dict


def infer_mbti_from_birthday(birthday_str: str) -> str:
    """
    Infer MBTI type from birthday (simplified algorithm).
    
    This is a placeholder - in reality, you'd want a more sophisticated
    algorithm or just use it as a fun feature.
    """
    try:
        birthday = datetime.strptime(birthday_str, "%Y-%m-%d")
        
        # Simple mapping based on month (just for fun)
        month_to_mbti = {
            1: "INTJ", 2: "INFP", 3: "ENFP", 4: "ENTP",
            5: "ISTJ", 6: "ISFJ", 7: "ESFJ", 8: "ESTJ",
            9: "ISTP", 10: "ISFP", 11: "ESFP", 12: "ESTP"
        }
        
        # Add some variation based on day
        day = birthday.day
        if day <= 10:
            # More introverted
            pass
        elif day <= 20:
            # Balanced
            pass
        else:
            # More extroverted
            mbti = month_to_mbti[birthday.month]
            if mbti[0] == 'I':
                mbti = 'E' + mbti[1:]
            elif mbti[0] == 'E':
                mbti = 'I' + mbti[1:]
            month_to_mbti[birthday.month] = mbti
        
        return month_to_mbti[birthday.month]
        
    except ValueError:
        # Invalid date format, return default
        return "INFP"


@router.post("/profile", response_model=CreateProfileResponse)
async def create_profile(request: CreateProfileRequest):
    """
    Create user profile with MBTI configuration.
    
    Supports two methods:
    1. birthday: Infer MBTI from birthday
    2. manual: User selects MBTI directly
    """
    try:
        import uuid
        user_id = f"user_{uuid.uuid4().hex[:8]}"
        
        inferred = False
        
        if request.method == "birthday":
            if not request.birthday:
                raise HTTPException(400, "Birthday required for birthday method")
            
            mbti_type = infer_mbti_from_birthday(request.birthday)
            inferred = True
            
        elif request.method == "manual":
            if not request.mbti_type:
                raise HTTPException(400, "MBTI type required for manual method")
            
            mbti_type = request.mbti_type.upper()
            
        else:
            raise HTTPException(400, "Invalid method")
        
        # Create profile
        profile = UserProfile(
            user_id=user_id,
            mbti_type=mbti_type,
            gender=request.gender,
            birthday=request.birthday
        )
        
        user_profiles[user_id] = profile
        
        logger.info(f"Created user profile: {user_id} with MBTI {mbti_type}, gender {request.gender}")
        
        return CreateProfileResponse(
            user_id=user_id,
            mbti_type=mbti_type,
            gender=request.gender,
            inferred=inferred,
            profile=profile.dict()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create profile: {e}")
        raise HTTPException(500, f"Failed to create profile: {str(e)}")


@router.get("/profile/{user_id}")
async def get_profile(user_id: str):
    """Get user profile by ID."""
    if user_id not in user_profiles:
        raise HTTPException(404, "User profile not found")
    
    profile = user_profiles[user_id]
    return profile.dict()


@router.put("/profile/{user_id}/mbti")
async def update_mbti(user_id: str, mbti_type: str):
    """Update user's MBTI type."""
    if user_id not in user_profiles:
        raise HTTPException(404, "User profile not found")
    
    # Validate MBTI
    valid_types = {
        "ENTJ", "INFP", "ISTP", "ENFJ", "INTP",
        "ESTJ", "ISFP", "ENTP", "ISFJ", "ESFP",
        "INTJ", "ESFJ", "ESTP", "INFJ", "ENFP", "ISTJ"
    }
    
    mbti_upper = mbti_type.upper()
    if mbti_upper not in valid_types:
        raise HTTPException(400, f"Invalid MBTI type: {mbti_type}")
    
    profile = user_profiles[user_id]
    profile.mbti_type = mbti_upper
    
    logger.info(f"Updated MBTI for user {user_id}: {mbti_upper}")
    
    return profile.dict()


@router.get("/mbti-types")
async def get_mbti_types():
    """Get list of all MBTI types with descriptions."""
    mbti_descriptions = {
        "ENTJ": "指挥官 - 大胆、富有想象力、意志强大的领导者",
        "INTJ": "建筑师 - 富有想象力和战略性的思想家",
        "INFP": "调停者 - 诗意、善良、利他的理想主义者",
        "ENFJ": "主人公 - 富有魅力、鼓舞人心的领导者",
        "INTP": "逻辑学家 - 创新的发明家，渴望知识",
        "ESTJ": "总经理 - 出色的管理者，善于管理事务或人",
        "ISFP": "探险家 - 灵活、迷人的艺术家",
        "ENTP": "辩论家 - 聪明、好奇的思想家",
        "ISFJ": "守卫者 - 非常专注、温暖的保护者",
        "ESFP": "表演者 - 自发的、精力充沛的娱乐者",
        "ESFJ": "执政官 - 极有同情心、受欢迎的合作者",
        "ESTP": "企业家 - 聪明、精力充沛、善于察觉的冒险家",
        "INFJ": "提倡者 - 安静、神秘的理想主义者",
        "ENFP": "竞选者 - 热情、有创造力、社交能力强的自由精神",
        "ISTJ": "物流师 - 实际、注重事实的可靠人士",
        "ISTP": "鉴赏家 - 大胆、实际的实验者"
    }
    
    return {"mbti_types": mbti_descriptions}
