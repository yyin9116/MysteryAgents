"""
Discussion service managing free discussion mode.
自由讨论模式服务
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

from models.agent import Agent
from models.discussion import Discussion, DiscussionMessage, DiscussionStatus, MessageType
from models.character import Character, CharacterWithProfession
from services import prompt_registry


class DiscussionService:
    """管理自由讨论模式的服务"""
    
    def __init__(
        self, 
        discussion: Discussion, 
        agents: List[Agent],
        characters: Optional[List[CharacterWithProfession]] = None
    ):
        self.discussion = discussion
        self.agents = {agent.config.id: agent for agent in agents}
        self.characters = {char.character.id: char for char in characters} if characters else {}
        self.agent_to_character = {}  # agent_id -> character_id mapping
        self.is_paused = False
        self.is_ended = False
        
        # Build agent-character mapping if characters provided
        if characters and len(characters) == len(agents):
            for agent, char_with_prof in zip(agents, characters):
                self.agent_to_character[agent.config.id] = char_with_prof.character.id
    
    def get_character_for_agent(self, agent_id: str) -> Optional[CharacterWithProfession]:
        """获取 Agent 对应的角色"""
        char_id = self.agent_to_character.get(agent_id)
        if char_id:
            return self.characters.get(char_id)
        return None
    
    def get_agent(self, agent_id: str) -> Optional[Agent]:
        """获取指定 Agent"""
        return self.agents.get(agent_id)
    
    def get_alive_agents(self) -> List[Agent]:
        """获取所有存活的 Agents"""
        return [agent for agent in self.agents.values() if agent.is_alive]
    
    async def agent_discuss(self, agent_id: str) -> Dict[str, Any]:
        """让指定 Agent 发言讨论"""
        agent = self.get_agent(agent_id)
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")

        if not agent.is_alive:
            raise ValueError(f"Agent {agent_id} is not alive")

        # 夺舍模式下跳过 AI 发言
        if agent.is_possessed:
            logger.info(f"Agent {agent_id} is possessed, skipping AI generation in discussion mode")
            return {
                "agent_id": agent_id,
                "agent_name": agent.config.name or agent_id,
                "speech": "",
                "thought": "",
                "agree_with": [],
                "disagree_with": [],
                "sentiment": "neutral",
                "waiting_for_user": True
            }

        # 构建讨论提示词
        system_prompt = self._build_discussion_prompt(agent)

        # 获取最近的对话历史
        recent_messages = self.discussion.messages[-20:]
        conversation_history = self._format_messages_for_agent(recent_messages)

        # 生成讨论发言
        try:
            response = await agent.generate_description(
                system_prompt=system_prompt,
                conversation_history=conversation_history,
                current_round=self.discussion.current_round
            )

            # 确保字段存在，使用默认值
            agree_with = response.get("agree_with", [])
            disagree_with = response.get("disagree_with", [])
            sentiment = response.get("sentiment", "neutral")

            # 创建消息记录
            message = DiscussionMessage(
                id=f"msg_{len(self.discussion.messages)}",
                discussion_id=self.discussion.id,
                speaker_id=agent_id,
                speaker_name=agent.config.name or agent_id,
                speaker_type=MessageType.AGENT,
                content=response["speech"],
                thought=response.get("thought", ""),
                agree_with=agree_with,
                disagree_with=disagree_with,
                sentiment=sentiment
            )

            self.discussion.messages.append(message)

            # 通知其他 Agents
            for other_agent in self.get_alive_agents():
                if other_agent.config.id != agent_id:
                    other_agent.observe_event(
                        f"{agent.config.name or agent_id} 说: {response['speech']}",
                        self.discussion.current_round
                    )

            logger.info(f"Agent {agent_id} discussed: {response['speech'][:50]}...")

            return {
                "agent_id": agent_id,
                "agent_name": agent.config.name or agent_id,
                "speech": response["speech"],
                "thought": response.get("thought", ""),
                "agree_with": agree_with,
                "disagree_with": disagree_with,
                "sentiment": sentiment
            }

        except Exception as e:
            logger.error(f"Failed to generate discussion for {agent_id}: {e}")
            # 返回错误信息
            return {
                "agent_id": agent_id,
                "agent_name": agent.config.name or agent_id,
                "speech": "我需要更多时间思考...",
                "thought": f"生成失败: {str(e)}",
                "agree_with": [],
                "disagree_with": [],
                "sentiment": "neutral",
                "error": str(e)
            }
    
    def user_speak(self, speech: str, mention_agents: List[str] = None) -> DiscussionMessage:
        """用户发言"""
        message = DiscussionMessage(
            id=f"msg_{len(self.discussion.messages)}",
            discussion_id=self.discussion.id,
            speaker_id="user",
            speaker_name="你",
            speaker_type=MessageType.USER,
            content=speech,
            mentions=mention_agents or []
        )
        
        self.discussion.messages.append(message)
        
        # 通知所有 Agents
        for agent in self.get_alive_agents():
            agent.observe_event(
                f"用户说: {speech}",
                self.discussion.current_round
            )
        
        logger.info(f"User spoke: {speech[:50]}...")
        return message
    
    def pause(self):
        """暂停讨论"""
        self.is_paused = True
        self.discussion.status = DiscussionStatus.PAUSED
        logger.info("Discussion paused")
    
    def resume(self):
        """继续讨论"""
        self.is_paused = False
        self.discussion.status = DiscussionStatus.ACTIVE
        logger.info("Discussion resumed")
    
    def end(self):
        """结束讨论"""
        self.is_ended = True
        self.discussion.status = DiscussionStatus.ENDED
        self.discussion.ended_at = datetime.now()
        logger.info("Discussion ended")
    
    def _build_discussion_prompt(self, agent: Agent) -> str:
        """构建讨论提示词"""
        # Check if agent has a character
        char_with_prof = self.get_character_for_agent(agent.config.id)
        
        if char_with_prof:
            # Use character cosplay prompt
            from services.character_prompt_builder import get_character_prompt_builder
            prompt_builder = get_character_prompt_builder()
            
            return prompt_builder.build_character_cosplay_prompt(
                character=char_with_prof.character,
                profession=char_with_prof.profession,
                topic=self.discussion.topic,
                iq_level=agent.config.iq_level.value
            )
        else:
            # Use original prompt (without character)
            return self._build_original_discussion_prompt(agent)
    
    def _build_original_discussion_prompt(self, agent: Agent) -> str:
        """构建原始讨论提示词（无角色，模板来自 prompt_registry）"""
        from models.personality import PersonalityPrompt

        personality = PersonalityPrompt.get_default(agent.config.mbti_type)

        # 获取其他参与者信息
        participants = []
        for other_agent in self.get_alive_agents():
            if other_agent.config.id != agent.config.id:
                participants.append(f"- {other_agent.config.name or other_agent.config.id}")

        participants_list = "\n".join(participants) if participants else "（暂无其他参与者）"

        # 根据 IQ 级别设置发言长度指导
        if agent.config.iq_level.value == "High":
            speech_length_guide = "300-500字，深入分析，引用具体案例、数据或理论"
            depth_guide = "进行多层次分析，考虑历史背景、现实影响、未来趋势，引用具体例子"
        elif agent.config.iq_level.value == "Mid":
            speech_length_guide = "200-300字，结合个人经验和常识，逻辑清晰"
            depth_guide = "结合实际生活经验，用通俗易懂的方式表达观点，可以举例说明"
        else:
            speech_length_guide = "100-200字，简单直接，基于直觉"
            depth_guide = "用简单直白的语言表达想法，可以基于个人感受和直觉"

        return prompt_registry.render("debate_plain_prompt", {
            "agent_name": agent.config.name or agent.config.id,
            "mbti_type": agent.config.mbti_type,
            "iq_level": agent.config.iq_level.value,
            "topic": self.discussion.topic,
            "participants_list": participants_list,
            "speech_length_guide": speech_length_guide,
            "depth_guide": depth_guide,
            "personality_traits": personality.traits,
            "speaking_style": personality.speaking_style,
            "thinking_pattern": personality.thinking_pattern,
        })

    def _format_messages_for_agent(self, messages: List[DiscussionMessage]) -> List[Dict]:
        """格式化消息供 Agent 使用"""
        formatted = []
        for msg in messages:
            formatted.append({
                "round": self.discussion.current_round,
                "agent_id": msg.speaker_id,
                "type": msg.speaker_type.value,
                "content": f"{msg.speaker_name}: {msg.content}",
                "thought": msg.thought or "",
                "suspicion": {}
            })
        return formatted
