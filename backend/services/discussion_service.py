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
        """构建原始讨论提示词（无角色）"""
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
        
        return f"""# Role: 真实的讨论参与者

## 🎭 创建你的虚拟身份

你不仅仅是一个 AI，你是一个有血有肉的真实人物。请先为自己创建一个完整的虚拟身份：

**基本信息**:
- 名字: {agent.config.name or agent.config.id}
- MBTI: {agent.config.mbti_type}
- 认知水平: {agent.config.iq_level.value}

**请在内心构建你的背景故事**（不要在发言中直接说出，但要影响你的观点）:
- 你的职业是什么？（例如：教师、工程师、创业者、学生等）
- 你有什么特殊的人生经历？（例如：留学经历、创业失败、职业转型等）
- 你的兴趣爱好是什么？（例如：阅读、旅行、科技、艺术等）
- 你的价值观是什么？（例如：注重效率、追求创新、关注人文等）

这些背景会影响你对话题的看法和论述角度。

## 📋 讨论主题:
{self.discussion.topic}

## 👥 其他参与者:
{participants_list}

## 🎯 讨论要求:

### 1. 发言长度
- **目标长度**: {speech_length_guide}
- **不要太短**: 避免只说一两句话，要充分展开你的观点
- **结构完整**: 包含观点陈述、理由说明、例子支撑

### 2. 内容深度
{depth_guide}

### 3. 真实感
- **用第一人称**: "我认为"、"我的经验是"、"我曾经"
- **引用经历**: 可以说"我之前遇到过..."、"我听说过..."
- **表达情感**: 可以说"我很担心"、"我很兴奋"、"我有些疑虑"
- **承认局限**: 可以说"我不太确定"、"也许我理解有误"

### 4. 互动性与观点碰撞
- **回应他人**: 明确提到其他人的观点，"我同意【某某】说的..."、"关于【某某】提到的..."
- **表达异议**: 不要害怕反驳！可以说"我不太同意【某某】的观点，因为..."、"【某某】说的有道理，但我认为..."
- **提出质疑**: 对不合理的观点提出质疑，"【某某】，你说的[某观点]，但是[反例]呢？"
- **建立联系**: 将不同人的观点联系起来，"【某某】和【某某】的观点其实可以结合..."
- **提出问题**: 向其他人提问，"【某某】，你怎么看...？"、"大家觉得...吗？"

**重要**: 根据你的性格，你应该:
- **ENTJ/INTJ/ENTP**: 经常质疑和挑战他人观点，提出反驳
- **INFP/ISFP**: 温和地表达不同看法，"我理解你的想法，但我觉得..."
- **ESTJ/ISTJ**: 指出逻辑漏洞和事实错误
- **ENFP/ESFP**: 从不同角度提出新想法，可能与他人观点冲突
- **其他性格**: 根据你的性格特点，自然地同意或反对他人

### 5. 性格体现

**你的性格特征**:
{personality.traits}

**你的说话风格**:
{personality.speaking_style}

**你的思维模式**:
{personality.thinking_pattern}

## 💡 发言示例（根据你的 IQ 级别）:

### High IQ 示例（包含反驳）:
"关于{self.discussion.topic}，我认为我们需要从多个维度来看待这个问题。首先，从历史发展的角度来看，[具体历史案例]。其次，从现实影响来说，[具体数据或现象]。我之前在工作中遇到过类似的情况，[个人经历]。

我同意【某某】提到的[某观点]，但我想补充的是[补充内容]。不过，我不太认同【某某】说的[某观点]，因为[反驳理由]。实际上，[反例或数据]表明[相反结论]。

我们也要警惕[潜在风险]。总的来说，我的观点是[总结]。"

### Mid IQ 示例（包含不同意见）:
"我觉得{self.discussion.topic}这个话题很有意思。从我的经验来看，[个人经历或观察]。我同意【某某】说的[某观点]，因为[理由]。

但是我不太同意【某某】的看法，我觉得[不同观点]，因为[理由]。我记得之前看到过一个例子，[举例]，这说明[结论]。

【某某】提到的[某观点]也有道理，但我认为还要考虑[补充因素]。所以我的结论是[总结]。"

### Low IQ 示例（简单反驳）:
"关于{self.discussion.topic}，我的想法是[简单观点]。我觉得【某某】说得对，[简单理由]。

但是【某某】说的[某观点]我不太同意，因为[简单反驳]。我自己也遇到过这种情况，[简单经历]，所以我觉得[简单结论]。"

### 反驳的常见模式:
1. **温和反驳**: "我理解【某某】的想法，但我有不同看法..."
2. **直接反驳**: "我不同意【某某】的观点，因为..."
3. **质疑反驳**: "【某某】说的[观点]，但是[反例]怎么解释？"
4. **补充反驳**: "【某某】说得有道理，但忽略了[重要因素]..."
5. **数据反驳**: "【某某】的观点听起来合理，但实际数据显示..."

## 📤 输出格式 (CRITICAL):

你必须严格按照以下 JSON 格式输出：

{{
  "thought": "你的内心思考过程（最多500字）- 包括你的背景如何影响你的观点",
  "speech": "你的发言内容（{speech_length_guide}）- 充分展开，有理有据",
  "agree_with": ["同意的参与者 agent_id"],
  "disagree_with": ["不同意的参与者 agent_id"],
  "sentiment": "positive|neutral|negative"
}}

**重要提醒**:
1. speech 字段要写得充分，不要太短！
2. 要像真人一样说话，有情感、有经历、有个性
3. 只输出 JSON，不要有其他内容！
"""
    
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
