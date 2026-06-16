"""
Discussion Factory for creating discussions with characters.

讨论工厂 - 创建带角色的讨论
"""

import logging
import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime

from models.discussion import Discussion, DiscussionStatus
from models.agent import Agent, AgentConfig, IQLevel
from models.character import CharacterWithProfession
from services.memory_service import AgentMemorySystem
from services.character_service import get_character_service
from services.character_selection_service import get_character_selection_service
from services.profession_generator_service import get_profession_generator
from services.discussion_service import DiscussionService

logger = logging.getLogger(__name__)


class DiscussionFactory:
    """讨论工厂"""
    
    @staticmethod
    async def create_discussion_with_characters(
        topic: str,
        agent_count: int,
        mbti_list: List[str],
        model_config: Optional[Dict[str, Any]] = None
    ) -> tuple[Discussion, DiscussionService]:
        """
        创建带角色的讨论
        
        Args:
            topic: 讨论话题
            agent_count: Agent 数量
            mbti_list: MBTI 类型列表
            model_config: 模型配置（可选）
            
        Returns:
            tuple[Discussion, DiscussionService]: 讨论对象和服务
        """
        logger.info(f"Creating discussion with characters: topic='{topic}', agents={agent_count}")
        
        # Validate
        if len(mbti_list) != agent_count:
            raise ValueError(f"MBTI list length ({len(mbti_list)}) must match agent count ({agent_count})")
        
        # 1. Select characters
        char_service = get_character_service()
        selection_service = get_character_selection_service()
        
        characters = selection_service.select_characters_for_discussion(mbti_list)
        logger.info(f"Selected characters: {[c.name for c in characters]}")
        
        # 2. Generate professions for each character
        prof_generator = get_profession_generator()
        logger.info(
            "Using profession generator instance=%s timeout=%s",
            hex(id(prof_generator)),
            prof_generator.generation_timeout,
        )
        
        professions = await prof_generator.generate_professions_batch(
            characters=characters,
            topic=topic,
            model_config=model_config,
        )
        logger.info(f"Generated professions: {[p.profession_name for p in professions]}")
        
        # 3. Create CharacterWithProfession objects
        characters_with_professions = []
        for character, profession in zip(characters, professions):
            char_with_prof = CharacterWithProfession(
                character=character,
                profession=profession,
                assigned_at=datetime.now().isoformat()
            )
            characters_with_professions.append(char_with_prof)
        
        # 4. Create Agents with character names
        agents = []
        for i, (char_with_prof, mbti) in enumerate(zip(characters_with_professions, mbti_list)):
            agent_id = f"agent_{i+1}"
            
            # Determine IQ level based on MBTI (simple heuristic)
            iq_level = DiscussionFactory._determine_iq_level(mbti)
            
            # Create agent config
            agent_config = AgentConfig(
                id=agent_id,
                mbti_type=mbti,
                iq_level=iq_level,
                name=char_with_prof.character.name  # Use character name
            )
            
            # Create memory system
            memory_system = AgentMemorySystem(
                agent_id=agent_id,
                iq_level=iq_level.value
            )
            
            # Create agent
            agent = Agent(
                config=agent_config,
                memory_system=memory_system,
                model_config=model_config
            )
            
            agents.append(agent)
            logger.info(f"Created agent {agent_id}: {char_with_prof.character.name} ({mbti}, {iq_level.value})")
        
        # 5. Create Discussion
        discussion = Discussion(
            id=f"disc_{uuid.uuid4().hex[:8]}",
            topic=topic,
            agents=[],  # Will be populated by API
            status=DiscussionStatus.ACTIVE,
            created_at=datetime.now(),
            messages=[],
            current_round=0
        )
        
        # 6. Create DiscussionService
        discussion_service = DiscussionService(
            discussion=discussion,
            agents=agents,
            characters=characters_with_professions
        )
        
        logger.info(f"Discussion created: {discussion.id}")
        
        return discussion, discussion_service
    
    @staticmethod
    def _determine_iq_level(mbti: str) -> IQLevel:
        """
        根据 MBTI 类型确定 IQ 级别
        
        简单启发式规则：
        - NT 类型 (INTJ, ENTJ, INTP, ENTP) -> High IQ
        - NF 类型 (INFJ, ENFJ, INFP, ENFP) -> Mid IQ
        - ST 类型 (ISTJ, ESTJ, ISTP, ESTP) -> Mid IQ
        - SF 类型 (ISFJ, ESFJ, ISFP, ESFP) -> Low IQ
        """
        mbti = mbti.upper()
        
        if 'NT' in mbti or mbti in ['INTJ', 'ENTJ', 'INTP', 'ENTP']:
            return IQLevel.HIGH
        elif 'SF' in mbti or mbti in ['ISFJ', 'ESFJ', 'ISFP', 'ESFP']:
            return IQLevel.LOW
        else:
            return IQLevel.MID
    
    @staticmethod
    async def create_discussion_without_characters(
        topic: str,
        agent_count: int,
        mbti_list: List[str],
        model_config: Optional[Dict[str, Any]] = None
    ) -> tuple[Discussion, DiscussionService]:
        """
        创建不带角色的讨论（原始模式）
        
        Args:
            topic: 讨论话题
            agent_count: Agent 数量
            mbti_list: MBTI 类型列表
            model_config: 模型配置（可选）
            
        Returns:
            tuple[Discussion, DiscussionService]: 讨论对象和服务
        """
        logger.info(f"Creating discussion without characters: topic='{topic}', agents={agent_count}")
        
        # Validate
        if len(mbti_list) != agent_count:
            raise ValueError(f"MBTI list length ({len(mbti_list)}) must match agent count ({agent_count})")
        
        # Create Agents
        agents = []
        for i, mbti in enumerate(mbti_list):
            agent_id = f"agent_{i+1}"
            
            # Determine IQ level
            iq_level = DiscussionFactory._determine_iq_level(mbti)
            
            # Create agent config
            agent_config = AgentConfig(
                id=agent_id,
                mbti_type=mbti,
                iq_level=iq_level,
                name=f"参与者{i+1}"  # Generic name
            )
            
            # Create memory system
            memory_system = AgentMemorySystem(
                agent_id=agent_id,
                iq_level=iq_level.value
            )
            
            # Create agent
            agent = Agent(
                config=agent_config,
                memory_system=memory_system,
                model_config=model_config
            )
            
            agents.append(agent)
        
        # Create Discussion
        discussion = Discussion(
            id=f"disc_{uuid.uuid4().hex[:8]}",
            topic=topic,
            agents=[],  # Will be populated by API
            status=DiscussionStatus.ACTIVE,
            created_at=datetime.now(),
            messages=[],
            current_round=0
        )
        
        # Create DiscussionService (without characters)
        discussion_service = DiscussionService(
            discussion=discussion,
            agents=agents,
            characters=None
        )
        
        logger.info(f"Discussion created: {discussion.id}")
        
        return discussion, discussion_service


# Global factory instance
_discussion_factory: Optional[DiscussionFactory] = None


def get_discussion_factory() -> DiscussionFactory:
    """获取全局讨论工厂实例"""
    global _discussion_factory
    if _discussion_factory is None:
        _discussion_factory = DiscussionFactory()
    return _discussion_factory
