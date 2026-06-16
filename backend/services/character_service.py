"""
Character Service for managing character pool.

角色管理服务
"""

import yaml
import logging
from typing import Dict, List, Optional
from pathlib import Path

from models.character import Character

logger = logging.getLogger(__name__)


class CharacterService:
    """角色管理服务"""
    
    def __init__(self, config_path: str = "config/characters.yaml"):
        raw_path = Path(config_path)
        if not raw_path.is_absolute():
            raw_path = Path(__file__).parent.parent / raw_path
        self.config_path = raw_path
        self.characters: Dict[str, Character] = {}
        self.characters_by_mbti: Dict[str, List[Character]] = {}
        self._load_characters()
    
    def _load_characters(self) -> None:
        """从配置文件加载角色池"""
        try:
            if not self.config_path.exists():
                logger.error(f"Character config file not found: {self.config_path}")
                self._load_minimal_characters()
                return
            
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            if not config or 'characters' not in config:
                logger.error("Invalid character config format")
                self._load_minimal_characters()
                return
            
            # Parse characters
            for char_data in config['characters']:
                try:
                    character = Character(**char_data)
                    self.characters[character.id] = character
                    
                    # Index by MBTI
                    if character.mbti not in self.characters_by_mbti:
                        self.characters_by_mbti[character.mbti] = []
                    self.characters_by_mbti[character.mbti].append(character)
                    
                except Exception as e:
                    logger.error(f"Failed to parse character {char_data.get('id', 'unknown')}: {e}")
                    continue
            
            logger.info(f"Loaded {len(self.characters)} characters from {self.config_path}")
            logger.info(f"MBTI distribution: {[(mbti, len(chars)) for mbti, chars in self.characters_by_mbti.items()]}")
            
        except Exception as e:
            logger.error(f"Failed to load characters from {self.config_path}: {e}")
            self._load_minimal_characters()
    
    def _load_minimal_characters(self) -> None:
        """加载最小角色集（失败时使用）"""
        logger.warning("Loading minimal character set as fallback")
        
        # Create a minimal character for testing
        minimal_char = Character(
            id="default_agent",
            name="默认角色",
            mbti="ENTP",
            source="系统默认",
            original_era="现代",
            background_story="这是一个默认角色，用于系统测试。",
            signature_events="无",
            famous_quotes="无",
            personality_traits="灵活、适应性强",
            speaking_style="中性、客观",
            modern_perspective="适应现代社会",
            avatar_url="/avatars/default.jpg"
        )
        
        self.characters[minimal_char.id] = minimal_char
        self.characters_by_mbti[minimal_char.mbti] = [minimal_char]
    
    def get_all_characters(self) -> List[Character]:
        """获取所有角色"""
        return list(self.characters.values())
    
    def get_character_by_id(self, character_id: str) -> Optional[Character]:
        """根据 ID 获取角色"""
        return self.characters.get(character_id)
    
    def get_characters_by_mbti(self, mbti: str) -> List[Character]:
        """根据 MBTI 类型获取角色列表"""
        return self.characters_by_mbti.get(mbti.upper(), [])
    
    def reload_characters(self) -> None:
        """重新加载角色配置"""
        logger.info("Reloading character configuration...")
        self.characters.clear()
        self.characters_by_mbti.clear()
        self._load_characters()
    
    def get_character_count(self) -> int:
        """获取角色总数"""
        return len(self.characters)
    
    def get_mbti_distribution(self) -> Dict[str, int]:
        """获取 MBTI 分布"""
        return {mbti: len(chars) for mbti, chars in self.characters_by_mbti.items()}
    
    def validate_character_pool(self) -> Dict[str, any]:
        """验证角色池完整性"""
        all_mbti_types = [
            "ENTJ", "INFP", "ISTP", "ENFJ", "INTP",
            "ESTJ", "ISFP", "ENTP", "ISFJ", "ESFP",
            "INTJ", "ESFJ", "ESTP", "INFJ", "ENFP", "ISTJ"
        ]
        
        missing_mbti = []
        incomplete_mbti = []
        
        for mbti in all_mbti_types:
            chars = self.get_characters_by_mbti(mbti)
            if len(chars) == 0:
                missing_mbti.append(mbti)
            elif len(chars) < 3:
                incomplete_mbti.append((mbti, len(chars)))
        
        return {
            "total_characters": self.get_character_count(),
            "mbti_distribution": self.get_mbti_distribution(),
            "missing_mbti": missing_mbti,
            "incomplete_mbti": incomplete_mbti,
            "is_complete": len(missing_mbti) == 0 and len(incomplete_mbti) == 0
        }


# Global character service instance
_character_service: Optional[CharacterService] = None


def get_character_service() -> CharacterService:
    """获取全局角色服务实例"""
    global _character_service
    if _character_service is None:
        _character_service = CharacterService()
    return _character_service
