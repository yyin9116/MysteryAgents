"""
Personality Prompt Editor API Endpoints

Allows users to view, edit, and reset MBTI personality configurations.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field, field_validator
from typing import Dict, Optional
from datetime import datetime
import json
from pathlib import Path

router = APIRouter(prefix="/api/personality", tags=["personality"])

# Pydantic Models
class PersonalityPreset(BaseModel):
    """Personality preset configuration"""
    traits: str = Field(..., min_length=1, max_length=500, description="核心特质")
    speaking_style: str = Field(..., min_length=1, max_length=500, description="说话风格")
    thinking_pattern: str = Field(..., min_length=1, max_length=500, description="思维模式")
    
    @field_validator('traits', 'speaking_style', 'thinking_pattern')
    @classmethod
    def validate_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Field cannot be empty or whitespace only")
        return v.strip()


class PersonalityPresetUpdate(BaseModel):
    """Update request for personality preset"""
    traits: str
    speaking_style: str
    thinking_pattern: str


class PersonalityConfigExport(BaseModel):
    """Export format for personality configurations"""
    version: str = "1.0.0"
    exported_at: str
    config: Dict[str, PersonalityPreset]


class PersonalityConfigImport(BaseModel):
    """Import format for personality configurations"""
    version: str
    config: Dict[str, Dict[str, str]]
    
    @field_validator('version')
    @classmethod
    def validate_version(cls, v: str) -> str:
        if v != "1.0.0":
            raise ValueError("Unsupported version. Expected 1.0.0")
        return v


# Default personality presets (from personality_engine.py)
DEFAULT_PRESETS = {
    "ENTJ": {
        "traits": "指挥官：发言具有侵略性，倾向于质疑他人，试图主导投票风向",
        "speaking_style": "直接、果断、带有权威感",
        "thinking_pattern": "战略性思考，关注效率和结果"
    },
    "INFP": {
        "traits": "调护者：描述词偏向感受和意象，在被怀疑时会表现得防御性强且情绪化",
        "speaking_style": "温和、富有想象力、情感丰富",
        "thinking_pattern": "基于价值观和感受进行判断"
    },
    "ISTP": {
        "traits": "鉴赏家：发言极简，只观察不废话，逻辑非常务实",
        "speaking_style": "简洁、实用、冷静",
        "thinking_pattern": "基于事实和逻辑的分析"
    },
    "ENFJ": {
        "traits": "主人公：善于察言观色，关注群体和谐，试图调解冲突但也会引导舆论",
        "speaking_style": "热情、有感染力、善于沟通",
        "thinking_pattern": "关注人际关系和团队动态"
    },
    "INTP": {
        "traits": "逻辑学家：喜欢分析和辩论，追求逻辑一致性，可能过度分析而忽略社交线索",
        "speaking_style": "理性、客观、有时显得冷漠",
        "thinking_pattern": "系统性分析，寻找模式"
    },
    "ESTJ": {
        "traits": "总经理：注重规则和秩序，倾向于组织和管理，发言直接且务实",
        "speaking_style": "权威、清晰、注重细节",
        "thinking_pattern": "基于经验和传统的决策"
    },
    "ISFP": {
        "traits": "探险家：温和但坚持自己的价值观，描述富有艺术感和个人色彩",
        "speaking_style": "柔和、真诚、富有表现力",
        "thinking_pattern": "基于当下感受和美学判断"
    },
    "ENTP": {
        "traits": "辩论家：喜欢挑战和创新，善于发现漏洞，可能故意制造混乱来测试他人",
        "speaking_style": "机智、挑衅、充满创意",
        "thinking_pattern": "发散性思维，探索多种可能性"
    },
    "ISFJ": {
        "traits": "守卫者：忠诚可靠，注重细节，倾向于维护和谐，不喜欢冲突",
        "speaking_style": "谨慎、体贴、注重传统",
        "thinking_pattern": "基于过往经验和责任感"
    },
    "ESFP": {
        "traits": "表演者：活泼外向，喜欢成为焦点，描述生动且富有感染力",
        "speaking_style": "热情、幽默、充满活力",
        "thinking_pattern": "关注当下体验和他人反应"
    },
    "INTJ": {
        "traits": "建筑师：独立思考，战略规划能力强，倾向于长期分析和系统性推理",
        "speaking_style": "简洁、深刻、有时显得高冷",
        "thinking_pattern": "长远规划，系统性思考"
    },
    "ESFJ": {
        "traits": "执政官：热心助人，注重社交和谐，倾向于维护群体利益",
        "speaking_style": "友好、热情、善于交际",
        "thinking_pattern": "关注他人需求和社会规范"
    },
    "ESTP": {
        "traits": "企业家：行动导向，喜欢冒险，善于应对突发情况，发言直接且自信",
        "speaking_style": "大胆、直接、充满能量",
        "thinking_pattern": "实用主义，快速反应"
    },
    "INFJ": {
        "traits": "提倡者：理想主义，洞察力强，善于理解他人动机，描述富有深度",
        "speaking_style": "深沉、富有洞察、神秘",
        "thinking_pattern": "直觉导向，关注深层含义"
    },
    "ENFP": {
        "traits": "竞选者：热情洋溢，富有创造力，善于激励他人，描述充满想象力",
        "speaking_style": "热情、富有表现力、鼓舞人心",
        "thinking_pattern": "发散思维，关注可能性"
    },
    "ISTJ": {
        "traits": "物流师：务实可靠，注重事实和细节，倾向于按部就班，发言严谨",
        "speaking_style": "严谨、务实、注重细节",
        "thinking_pattern": "基于事实和逻辑的系统分析"
    }
}

VALID_MBTI_TYPES = set(DEFAULT_PRESETS.keys())


# Storage functions (using JSON file for simplicity, can be replaced with database)
def get_user_config_path(user_id: str = "default") -> Path:
    """Get path to user's personality config file"""
    config_dir = Path("./user_configs/personality")
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / f"{user_id}.json"


def load_user_personality_config(user_id: str = "default") -> Dict[str, PersonalityPreset]:
    """Load user's custom personality configurations"""
    config_path = get_user_config_path(user_id)
    
    if not config_path.exists():
        return {}
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return {
                mbti: PersonalityPreset(**preset)
                for mbti, preset in data.items()
            }
    except Exception as e:
        print(f"Error loading user config: {e}")
        return {}


def save_user_personality_config(
    user_id: str,
    mbti_type: str,
    preset: PersonalityPreset
):
    """Save a single personality preset for user"""
    config_path = get_user_config_path(user_id)
    
    # Load existing config
    existing_config = {}
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            existing_config = json.load(f)
    
    # Update with new preset
    if hasattr(preset, "model_dump"):
        existing_config[mbti_type] = preset.model_dump(mode="json")
    else:
        existing_config[mbti_type] = preset.dict()
    
    # Save back
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(existing_config, f, ensure_ascii=False, indent=2)


def delete_user_personality_config(user_id: str, mbti_type: str):
    """Delete a single personality preset for user"""
    config_path = get_user_config_path(user_id)
    
    if not config_path.exists():
        return
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    if mbti_type in config:
        del config[mbti_type]
    
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def delete_all_user_personality_configs(user_id: str):
    """Delete all personality presets for user"""
    config_path = get_user_config_path(user_id)
    
    if config_path.exists():
        config_path.unlink()


# API Endpoints
@router.get("/presets")
async def get_personality_presets(
    include_custom: bool = True,
    user_id: str = "default"
):
    """
    Get all personality presets (default and custom).
    
    Args:
        include_custom: Whether to include user's custom configurations
        user_id: User identifier
    
    Returns:
        List of personality presets with modification status
    """
    custom_presets = {}
    
    if include_custom:
        custom_presets = load_user_personality_config(user_id)
    
    # Build response with all MBTI types
    presets = []
    for mbti_type in VALID_MBTI_TYPES:
        if mbti_type in custom_presets:
            # Use custom preset
            preset_data = custom_presets[mbti_type].dict()
            preset_data["mbti_type"] = mbti_type
            preset_data["is_modified"] = True
        else:
            # Use default preset
            preset_data = DEFAULT_PRESETS[mbti_type].copy()
            preset_data["mbti_type"] = mbti_type
            preset_data["is_modified"] = False
        
        presets.append(preset_data)
    
    return {
        "presets": presets
    }


@router.get("/presets/{mbti_type}")
async def get_personality_preset(
    mbti_type: str,
    user_id: str = "default"
):
    """
    Get personality preset for specific MBTI type.
    
    Args:
        mbti_type: MBTI type (e.g., "ENTJ")
        user_id: User identifier
    
    Returns:
        Personality preset configuration
    """
    if mbti_type not in VALID_MBTI_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid MBTI type. Must be one of: {', '.join(VALID_MBTI_TYPES)}"
        )
    
    # Check for custom config first
    custom_presets = load_user_personality_config(user_id)
    
    if mbti_type in custom_presets:
        return {
            "mbti_type": mbti_type,
            "preset": custom_presets[mbti_type].dict(),
            "is_custom": True
        }
    
    # Return default
    return {
        "mbti_type": mbti_type,
        "preset": DEFAULT_PRESETS[mbti_type],
        "is_custom": False
    }


@router.put("/preset/{mbti_type}")
async def update_personality_preset(
    mbti_type: str,
    preset: PersonalityPresetUpdate,
    user_id: str = "default"
):
    """
    Update personality preset for specific MBTI type.
    
    Args:
        mbti_type: MBTI type to update
        preset: New personality configuration
        user_id: User identifier
    
    Returns:
        Success status and updated preset
    """
    if mbti_type not in VALID_MBTI_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid MBTI type. Must be one of: {', '.join(VALID_MBTI_TYPES)}"
        )
    
    try:
        # Validate preset
        validated_preset = PersonalityPreset(**preset.dict())
        
        # Save to user config
        save_user_personality_config(user_id, mbti_type, validated_preset)
        
        return {
            "status": "success",
            "mbti_type": mbti_type,
            "preset": validated_preset.dict(),
            "message": f"Personality preset for {mbti_type} updated successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/preset/{mbti_type}/reset")
async def reset_personality_preset(
    mbti_type: str,
    user_id: str = "default"
):
    """
    Reset personality preset to default for specific MBTI type.
    
    Args:
        mbti_type: MBTI type to reset
        user_id: User identifier
    
    Returns:
        Success status and default preset
    """
    if mbti_type not in VALID_MBTI_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid MBTI type. Must be one of: {', '.join(VALID_MBTI_TYPES)}"
        )
    
    try:
        delete_user_personality_config(user_id, mbti_type)
        default_preset = DEFAULT_PRESETS[mbti_type]
        
        return {
            "status": "success",
            "mbti_type": mbti_type,
            "preset": default_preset,
            "message": f"Personality preset for {mbti_type} reset to default"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reset-all")
async def reset_all_personality_presets(user_id: str = "default"):
    """
    Reset all personality presets to default.
    
    Args:
        user_id: User identifier
    
    Returns:
        Success status
    """
    try:
        delete_all_user_personality_configs(user_id)
        
        return {
            "status": "success",
            "message": "All personality presets reset to default"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/export")
async def export_personality_config(user_id: str = "default"):
    """
    Export user's custom personality configurations.
    
    Args:
        user_id: User identifier
    
    Returns:
        JSON export of custom configurations
    """
    custom_config = load_user_personality_config(user_id)
    
    export_data = PersonalityConfigExport(
        version="1.0.0",
        exported_at=datetime.now().isoformat(),
        config=custom_config
    )
    
    return export_data.dict()


@router.post("/import")
async def import_personality_config(
    config: PersonalityConfigImport,
    user_id: str = "default"
):
    """
    Import personality configurations.
    
    Args:
        config: Configuration data to import
        user_id: User identifier
    
    Returns:
        Success status and import count
    """
    try:
        imported_count = 0
        
        for mbti_type, preset_data in config.config.items():
            # Validate MBTI type
            if mbti_type not in VALID_MBTI_TYPES:
                continue
            
            # Validate and save preset
            validated_preset = PersonalityPreset(**preset_data)
            save_user_personality_config(user_id, mbti_type, validated_preset)
            imported_count += 1
        
        return {
            "status": "success",
            "imported_count": imported_count,
            "message": f"Successfully imported {imported_count} personality presets"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/validate/{mbti_type}")
async def validate_mbti_type(mbti_type: str):
    """
    Validate if MBTI type is supported.
    
    Args:
        mbti_type: MBTI type to validate
    
    Returns:
        Validation result
    """
    is_valid = mbti_type in VALID_MBTI_TYPES
    
    return {
        "mbti_type": mbti_type,
        "is_valid": is_valid,
        "valid_types": list(VALID_MBTI_TYPES) if not is_valid else None
    }
