"""
Character data models for the Character Persona System.

角色人设系统的数据模型
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
from datetime import datetime


class Character(BaseModel):
    """角色数据模型"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "sun_wukong",
                "name": "孙悟空",
                "mbti": "ENTP",
                "source": "神话传说 - 西游记",
                "original_era": "西游记时代",
                "background_story": "齐天大圣孙悟空，花果山水帘洞美猴王...",
                "signature_events": "大闹天宫、三打白骨精、真假美猴王、智取芭蕉扇",
                "famous_quotes": "俺老孙来也！|妖怪，哪里逃！|师父被妖怪抓走了！",
                "personality_traits": "创新思维、挑战权威、机智幽默、行动力强",
                "speaking_style": "直率豪爽，自称'俺老孙'，喜欢讲英雄事迹",
                "modern_perspective": "觉得现代科技很有意思，像新的法宝",
                "avatar_url": "/avatars/sun_wukong.jpg"
            }
        }
    )

    id: str = Field(..., description="角色唯一标识符")
    name: str = Field(..., description="角色名字")
    mbti: str = Field(..., description="MBTI 类型")
    source: str = Field(..., description="角色来源")
    original_era: str = Field(..., description="原始时代")
    background_story: str = Field(..., description="背景故事")
    signature_events: str = Field(..., description="标志性事件")
    famous_quotes: str = Field(..., description="名言名句")
    personality_traits: str = Field(..., description="性格特征")
    speaking_style: str = Field(..., description="说话风格")
    modern_perspective: str = Field(..., description="现代视角")
    avatar_url: str = Field(..., description="头像 URL")
    
class GeneratedProfession(BaseModel):
    """动态生成的现代职业"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "profession_name": "AI 系统压力测试工程师",
                "workplace": "花果山科技公司",
                "daily_work": "用七十二变测试 AI 系统极限，经常把系统搞崩溃",
                "connection_to_past": "当年大闹天宫就是测试天庭系统漏洞",
                "relevance_to_topic": "最懂 AI 的弱点，能从实战角度讨论伦理"
            }
        }
    )

    profession_name: str = Field(..., description="职业名称")
    workplace: str = Field(..., description="工作地点/环境")
    daily_work: str = Field(..., description="日常工作描述")
    connection_to_past: str = Field(..., description="与原始故事的联系")
    relevance_to_topic: str = Field(..., description="如何帮助理解讨论话题")
    
class CharacterWithProfession(BaseModel):
    """带职业的角色（用于讨论）"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "character": {
                    "id": "sun_wukong",
                    "name": "孙悟空",
                    "mbti": "ENTP"
                },
                "profession": {
                    "profession_name": "AI 系统压力测试工程师",
                    "workplace": "花果山科技公司"
                },
                "assigned_at": "2024-12-24T10:00:00Z"
            }
        }
    )

    character: Character = Field(..., description="角色信息")
    profession: GeneratedProfession = Field(..., description="动态生成的职业")
    assigned_at: str = Field(..., description="分配时间")
