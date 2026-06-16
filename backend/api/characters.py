"""
Character API endpoints.

角色 API 端点
"""

from fastapi import APIRouter, HTTPException
from typing import List, Optional
import logging

from models.character import Character
from services.character_service import get_character_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/characters", tags=["characters"])


@router.get("", response_model=dict)
async def get_all_characters(mbti_type: Optional[str] = None):
    """
    获取所有角色或按 MBTI 筛选
    
    Args:
        mbti_type: 可选的 MBTI 类型筛选
        
    Returns:
        角色列表和统计信息
    """
    try:
        char_service = get_character_service()
        
        if mbti_type:
            # Filter by MBTI
            characters = char_service.get_characters_by_mbti(mbti_type.upper())
            logger.info(f"Retrieved {len(characters)} characters for MBTI {mbti_type}")
        else:
            # Get all characters
            characters = char_service.get_all_characters()
            logger.info(f"Retrieved all {len(characters)} characters")
        
        # Get distribution
        distribution = char_service.get_mbti_distribution()
        
        # Format response
        return {
            "characters": [
                {
                    "id": char.id,
                    "name": char.name,
                    "mbti_type": char.mbti,  # Use mbti_type for consistency
                    "source": char.source,
                    "original_era": char.original_era,
                    "avatar_url": char.avatar_url,
                    "description": char.background_story[:100] + "..." if len(char.background_story) > 100 else char.background_story
                }
                for char in characters
            ],
            "total": len(characters),
            "mbti_distribution": distribution
        }
        
    except Exception as e:
        logger.error(f"Failed to get characters: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{character_id}", response_model=dict)
async def get_character_by_id(character_id: str):
    """
    获取指定角色的详细信息
    
    Args:
        character_id: 角色 ID
        
    Returns:
        角色详细信息
    """
    try:
        char_service = get_character_service()
        character = char_service.get_character_by_id(character_id)
        
        if not character:
            raise HTTPException(status_code=404, detail=f"Character {character_id} not found")
        
        logger.info(f"Retrieved character: {character.name}")
        
        # Format response with all details
        return {
            "id": character.id,
            "name": character.name,
            "mbti_type": character.mbti,  # Use mbti_type for consistency
            "source": character.source,
            "original_era": character.original_era,
            "description": character.background_story,
            "background": character.background_story,
            "signature_events": character.signature_events.split("|") if "|" in character.signature_events else [character.signature_events],
            "famous_quotes": character.famous_quotes.split("|") if "|" in character.famous_quotes else [character.famous_quotes],
            "personality_traits": character.personality_traits.split("|") if "|" in character.personality_traits else [character.personality_traits],
            "speaking_style": character.speaking_style,
            "modern_perspective": character.modern_perspective,
            "avatar_url": character.avatar_url
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get character {character_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/validate/pool", response_model=dict)
async def validate_character_pool():
    """
    验证角色池完整性
    
    Returns:
        验证结果
    """
    try:
        char_service = get_character_service()
        validation = char_service.validate_character_pool()
        
        logger.info(f"Character pool validation: {validation['is_complete']}")
        
        return validation
        
    except Exception as e:
        logger.error(f"Failed to validate character pool: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reload", response_model=dict)
async def reload_characters():
    """
    重新加载角色配置
    
    Returns:
        重新加载结果
    """
    try:
        char_service = get_character_service()
        char_service.reload_characters()
        
        count = char_service.get_character_count()
        logger.info(f"Reloaded {count} characters")
        
        return {
            "success": True,
            "message": f"Reloaded {count} characters",
            "characters_loaded": count,
            "total": count
        }
        
    except Exception as e:
        logger.error(f"Failed to reload characters: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/validate", response_model=dict)
async def validate_characters():
    """
    验证角色配置
    
    Returns:
        验证结果
    """
    try:
        char_service = get_character_service()
        validation = char_service.validate_character_pool()
        
        errors = []
        if validation['missing_mbti']:
            errors.append(f"Missing MBTI types: {', '.join(validation['missing_mbti'])}")
        if validation['incomplete_mbti']:
            for mbti, count in validation['incomplete_mbti']:
                errors.append(f"Incomplete MBTI {mbti}: only {count}/3 characters")
        
        logger.info(f"Character validation: {len(errors)} errors found")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "total_characters": validation['total_characters'],
            "mbti_distribution": validation['mbti_distribution']
        }
        
    except Exception as e:
        logger.error(f"Failed to validate characters: {e}")
        raise HTTPException(status_code=500, detail=str(e))
