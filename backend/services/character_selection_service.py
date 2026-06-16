"""
Character Selection Service for random character selection with deduplication.

角色选择服务（带随机性和去重）
"""

import random
import logging
from typing import Dict, List, Set, Optional
from collections import defaultdict

from models.character import Character
from services.character_service import CharacterService

logger = logging.getLogger(__name__)


class CharacterSelectionService:
    """角色选择服务（带随机性和去重）"""
    
    def __init__(self, character_service: CharacterService):
        self.character_service = character_service
        
        # Usage tracking: MBTI -> [character_ids]
        # Tracks recent usage to avoid repetition
        self.usage_tracker: Dict[str, List[str]] = defaultdict(list)
        
        # Recent combinations: List of sets of character IDs
        # Tracks recent character combinations to avoid repetition
        self.recent_combinations: List[Set[str]] = []
        
        # Configuration
        self.max_recent_combinations = 10  # Track last 10 combinations
        self.max_usage_history = 30  # Track last 30 uses per MBTI
    
    def select_characters_for_discussion(
        self,
        mbti_list: List[str]
    ) -> List[Character]:
        """
        为讨论选择角色
        
        Args:
            mbti_list: MBTI 类型列表
            
        Returns:
            List[Character]: 选中的角色列表
        """
        logger.info(f"Selecting characters for MBTI types: {mbti_list}")
        
        selected = []
        
        for mbti in mbti_list:
            character = self._select_character_for_mbti(mbti, selected)
            selected.append(character)
            logger.info(f"Selected {character.name} ({character.id}) for {mbti}")
        
        # Record this combination
        self._record_combination(selected)
        
        logger.info(f"Selected {len(selected)} characters: {[c.name for c in selected]}")
        return selected
    
    def _select_character_for_mbti(
        self,
        mbti: str,
        already_selected: List[Character]
    ) -> Character:
        """
        为指定 MBTI 类型选择一个角色
        
        策略：
        1. 获取该 MBTI 的所有角色（最多3个）
        2. 排除已选择的角色
        3. 根据使用频率排序（最少使用的优先）
        4. 从使用最少的角色中随机选择一个
        
        Args:
            mbti: MBTI 类型
            already_selected: 已选择的角色列表
            
        Returns:
            Character: 选中的角色
        """
        # Get available characters for this MBTI
        available = self.character_service.get_characters_by_mbti(mbti)
        
        if not available:
            raise ValueError(f"No characters available for MBTI type: {mbti}")
        
        # Exclude already selected characters
        already_selected_ids = {c.id for c in already_selected}
        available = [c for c in available if c.id not in already_selected_ids]
        
        if not available:
            # All characters for this MBTI are already selected
            # This should only happen if we have fewer than 3 characters per MBTI
            logger.warning(f"All characters for {mbti} already selected, allowing duplicate")
            available = self.character_service.get_characters_by_mbti(mbti)
        
        # Get usage counts for this MBTI
        usage_counts = self._get_usage_counts(mbti)
        
        # Sort by usage count (least used first)
        available.sort(key=lambda c: usage_counts.get(c.id, 0))
        
        # Get the minimum usage count
        min_usage = usage_counts.get(available[0].id, 0)
        
        # Select from characters with minimum usage
        candidates = [c for c in available if usage_counts.get(c.id, 0) == min_usage]
        
        # Randomly select from candidates
        selected = random.choice(candidates)
        
        # Update usage tracking
        self._update_usage(mbti, selected.id)
        
        logger.debug(f"Selected {selected.name} for {mbti} (usage: {min_usage})")
        
        return selected
    
    def _get_usage_counts(self, mbti: str) -> Dict[str, int]:
        """
        获取该 MBTI 类型各角色的使用次数
        
        Args:
            mbti: MBTI 类型
            
        Returns:
            Dict[str, int]: 角色ID -> 使用次数
        """
        if mbti not in self.usage_tracker:
            return {}
        
        usage_list = self.usage_tracker[mbti]
        return {char_id: usage_list.count(char_id) for char_id in set(usage_list)}
    
    def _update_usage(self, mbti: str, character_id: str) -> None:
        """
        更新使用记录
        
        Args:
            mbti: MBTI 类型
            character_id: 角色ID
        """
        self.usage_tracker[mbti].append(character_id)
        
        # Keep only recent history
        if len(self.usage_tracker[mbti]) > self.max_usage_history:
            self.usage_tracker[mbti] = self.usage_tracker[mbti][-self.max_usage_history:]
    
    def _record_combination(self, characters: List[Character]) -> None:
        """
        记录角色组合
        
        Args:
            characters: 角色列表
        """
        combination = {c.id for c in characters}
        self.recent_combinations.append(combination)
        
        # Keep only recent combinations
        if len(self.recent_combinations) > self.max_recent_combinations:
            self.recent_combinations = self.recent_combinations[-self.max_recent_combinations:]
    
    def is_combination_recent(self, characters: List[Character]) -> bool:
        """
        检查角色组合是否最近使用过
        
        Args:
            characters: 角色列表
            
        Returns:
            bool: 是否最近使用过
        """
        combination = {c.id for c in characters}
        return combination in self.recent_combinations
    
    def get_usage_stats(self) -> Dict:
        """
        获取使用统计
        
        Returns:
            Dict: 统计信息
        """
        stats = {
            "usage_by_mbti": {},
            "recent_combinations_count": len(self.recent_combinations),
            "recent_combinations": [
                list(combo) for combo in self.recent_combinations
            ]
        }
        
        for mbti, usage_list in self.usage_tracker.items():
            usage_counts = self._get_usage_counts(mbti)
            stats["usage_by_mbti"][mbti] = {
                "total_uses": len(usage_list),
                "character_counts": usage_counts
            }
        
        return stats
    
    def reset_usage_tracking(self, mbti: Optional[str] = None):
        """
        重置使用追踪
        
        Args:
            mbti: 如果指定，只重置该 MBTI 的追踪；否则重置全部
        """
        if mbti:
            if mbti in self.usage_tracker:
                self.usage_tracker[mbti].clear()
                logger.info(f"Reset usage tracking for {mbti}")
        else:
            self.usage_tracker.clear()
            self.recent_combinations.clear()
            logger.info("Reset all usage tracking")
    
    def get_least_used_characters(self, mbti: str, count: int = 3) -> List[Character]:
        """
        获取最少使用的角色
        
        Args:
            mbti: MBTI 类型
            count: 返回数量
            
        Returns:
            List[Character]: 最少使用的角色列表
        """
        available = self.character_service.get_characters_by_mbti(mbti)
        
        if not available:
            return []
        
        usage_counts = self._get_usage_counts(mbti)
        
        # Sort by usage count
        available.sort(key=lambda c: usage_counts.get(c.id, 0))
        
        return available[:count]


# Global character selection service instance
_character_selection_service: Optional[CharacterSelectionService] = None


def get_character_selection_service() -> CharacterSelectionService:
    """获取全局角色选择服务实例"""
    global _character_selection_service
    if _character_selection_service is None:
        from services.character_service import get_character_service
        _character_selection_service = CharacterSelectionService(get_character_service())
    return _character_selection_service
