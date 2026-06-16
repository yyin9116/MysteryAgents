"""
Game service managing game flow, rounds, and win conditions.
"""

import random
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum
import logging
import yaml
import os
from pathlib import Path

logger = logging.getLogger(__name__)

from models.agent import Agent, AgentRole
from models.game import GameState, GamePhase, GameConfig


def _model_dump(model: Any) -> Dict[str, Any]:
    """Compatibility helper for Pydantic v1/v2 style models."""
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    return model.dict()


class GameResult(str, Enum):
    """Game result enumeration."""
    CIVILIANS_WIN = "civilians_win"
    UNDERCOVER_WIN = "undercover_win"
    IN_PROGRESS = "in_progress"


class GameService:
    """Service for managing game logic and flow."""
    
    # 类级别的 prompt 缓存
    _prompt_templates: Optional[Dict[str, str]] = None
    
    def __init__(self, config: GameConfig, agents: List[Agent], assign_words_and_roles: bool = True):
        self.config = config
        self.agents = {agent.config.id: agent for agent in agents}
        self.current_round = 0
        self.phase = GamePhase.DESCRIPTION
        self.conversation_history: List[Dict[str, Any]] = []
        self.elimination_history: List[Dict[str, Any]] = []
        
        # Select speaker 模式相关
        self.speakers_this_round: List[str] = []  # 本轮已发言的 Agent ID
        self.speaking_order: List[str] = []  # 本轮发言顺序
        self.voters_this_round: List[str] = []  # 本轮已投票的 Agent ID
        
        # 加载 prompt 模板
        self._load_prompt_templates()
        
        # Assign words and roles
        if assign_words_and_roles:
            self._assign_words_and_roles()
        
        logger.info(f"Game initialized with {len(agents)} agents")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GameService":
        """Rebuild a game service from serialized state."""
        config = GameConfig(**data["config"])
        agents = [Agent.from_dict(agent_data) for agent_data in data["agents"].values()]
        game = cls(config, agents, assign_words_and_roles=False)
        game.current_round = data.get("current_round", 0)
        game.phase = GamePhase(data.get("phase", GamePhase.DESCRIPTION.value))
        game.conversation_history = data.get("conversation_history", [])
        game.elimination_history = data.get("elimination_history", [])
        game.speakers_this_round = data.get("speakers_this_round", [])
        game.speaking_order = data.get("speaking_order", [])
        game.voters_this_round = data.get("voters_this_round", [])
        return game
    
    @classmethod
    def _load_prompt_templates(cls):
        """从配置文件加载 prompt 模板（如果存在），否则使用硬编码的默认值"""
        if cls._prompt_templates is not None:
            return  # 已经加载过
        
        config_path = Path(__file__).parent.parent / "config" / "prompts.yaml"
        
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    cls._prompt_templates = yaml.safe_load(f)
                logger.info(f"✅ 已从配置文件加载 prompt 模板: {config_path}")
            except Exception as e:
                logger.warning(f"⚠️ 加载 prompt 配置文件失败，使用硬编码默认值: {e}")
                cls._prompt_templates = {}
        else:
            logger.info(f"ℹ️ 未找到 prompt 配置文件 ({config_path})，使用硬编码默认值")
            cls._prompt_templates = {}
    
    def _assign_words_and_roles(self):
        """Assign words and roles to agents."""
        agent_ids = list(self.agents.keys())
        random.shuffle(agent_ids)
        
        # Select one undercover agent
        undercover_id = agent_ids[0]
        
        for agent_id in agent_ids:
            agent = self.agents[agent_id]
            if agent_id == undercover_id:
                agent.config.word = self.config.undercover_word
                agent.config.role = AgentRole.UNDERCOVER
                logger.info(f"Agent {agent_id} assigned as UNDERCOVER with word: {self.config.undercover_word}")
            else:
                agent.config.word = self.config.civilian_word
                agent.config.role = AgentRole.CIVILIAN
                logger.info(f"Agent {agent_id} assigned as CIVILIAN with word: {self.config.civilian_word}")
    
    async def _apply_memory_decay(self):
        """Apply memory decay mechanism to all alive agents."""
        for agent in self.get_alive_agents():
            if not agent.is_possessed:
                try:
                    # Each agent has its own memory_system
                    agent.memory_system.apply_memory_decay(self.current_round)
                    logger.debug(f"Applied memory decay to {agent.config.id}")
                except Exception as e:
                    logger.warning(f"Memory decay failed for {agent.config.id}: {e}")
    
    def get_alive_agents(self) -> List[Agent]:
        """Get list of alive agents."""
        return [agent for agent in self.agents.values() if agent.is_alive]
    
    def get_agent(self, agent_id: str) -> Optional[Agent]:
        """Get agent by ID."""
        return self.agents.get(agent_id)
    
    def _determine_speaking_order(self, agents: List[Agent]) -> List[Agent]:
        """
        Determine the speaking order for agents.
        
        Current strategy: Random order for each round to add variety.
        Can be extended to use MBTI, IQ, or other factors.
        
        Args:
            agents: List of alive agents
            
        Returns:
            List of agents in speaking order
        """
        import random
        ordered = agents.copy()
        random.shuffle(ordered)
        
        logger.info(f"Speaking order determined: {[a.config.id for a in ordered]}")
        return ordered
    
    def calculate_similarity(self, text1: str, text2: str) -> float:
        """
        计算两段文本的相似度（使用 Jaccard 相似度）
        
        Args:
            text1: 第一段文本
            text2: 第二段文本
            
        Returns:
            相似度分数 (0.0 - 1.0)
        """
        if not text1 or not text2:
            return 0.0
        
        # 转换为字符集合
        set1 = set(text1)
        set2 = set(text2)
        
        # 计算交集和并集
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        
        if union == 0:
            return 0.0
        
        # Jaccard 相似度
        similarity = intersection / union
        
        logger.debug(f"Similarity between '{text1[:20]}...' and '{text2[:20]}...': {similarity:.2f}")
        return similarity
    
    def check_duplicate_speech(
        self,
        current_speech: str,
        agent_id: str,
        threshold: float = 0.9
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        检查当前发言是否与历史发言重复
        
        Args:
            current_speech: 当前发言内容
            agent_id: 当前发言的 Agent ID
            threshold: 相似度阈值（默认 0.9，更严格避免误判）
            
        Returns:
            (is_duplicate, duplicate_agent_id, duplicate_speech)
            - is_duplicate: 是否重复
            - duplicate_agent_id: 重复的来源 Agent ID
            - duplicate_speech: 重复的原始发言
        """
        # 前两轮不检测重复（需要建立基础描述）
        if self.current_round <= 2:
            logger.debug(f"Round {self.current_round}: Skipping duplicate detection (early rounds)")
            return (False, None, None)
        
        # 遍历历史发言记录
        for entry in self.conversation_history:
            # 只检查描述类型的发言
            if entry.get("type") != "description":
                continue
            
            # 获取历史发言内容
            history_speech = entry.get("content", "")
            history_agent_id = entry.get("agent_id", "")
            
            if not history_speech:
                continue
            
            # 计算相似度
            similarity = self.calculate_similarity(current_speech, history_speech)
            
            # 如果相似度超过阈值（非常高的相似度才算重复）
            if similarity >= threshold:
                logger.warning(
                    f"Duplicate detected! Agent {agent_id} speech similar to {history_agent_id} "
                    f"(similarity: {similarity:.2f})"
                )
                return (True, history_agent_id, history_speech)
        
        logger.debug(f"No duplicate detected for Agent {agent_id}")
        return (False, None, None)
    
    async def run_description_phase(self) -> List[Dict[str, Any]]:
        """
        Run description phase where all agents describe their word.
        
        Returns:
            List of agent responses
        """
        self.current_round += 1
        self.phase = GamePhase.DESCRIPTION
        
        logger.info("=" * 80)
        logger.info(f"🎮 ROUND {self.current_round} - DESCRIPTION PHASE STARTED")
        logger.info("=" * 80)
        
        # Apply memory decay at the start of each round
        await self._apply_memory_decay()
        
        responses = []
        alive_agents = self.get_alive_agents()
        
        # Determine speaking order
        speaking_order = self._determine_speaking_order(alive_agents)
        
        logger.info(f"📋 Total agents to speak: {len(speaking_order)}")
        logger.info(f"👥 Speaking order: {' -> '.join([a.config.id for a in speaking_order])}")
        
        for idx, agent in enumerate(speaking_order, 1):
            if agent.is_possessed:
                # Skip AI generation for possessed agents
                logger.info(f"⏸️  [{idx}/{len(speaking_order)}] Agent {agent.config.id} is possessed, waiting for user input")
                continue
            
            logger.info(f"🎤 [{idx}/{len(speaking_order)}] Agent {agent.config.id} is speaking...")
            logger.info(f"   └─ MBTI: {agent.config.mbti_type}, IQ: {agent.config.iq_level.value}, Role: {agent.config.role.value}")
            logger.info(f"   └─ Word: {agent.config.word}")
            
            # Build system prompt
            system_prompt = self._build_description_prompt(agent)
            
            # Generate description
            # 获取当前最新的对话历史（包含本轮前面 Agent 的发言）
            current_history = self.conversation_history[-10:]
            logger.info(f"   └─ Calling LLM for {agent.config.id}...")
            logger.info(f"   └─ Current conversation history size: {len(current_history)} messages")
            if current_history:
                logger.info(f"   └─ Last message: {current_history[-1].get('agent_id', 'unknown')} said '{current_history[-1].get('content', '')[:50]}...'")
            
            try:
                response = await agent.generate_description(
                    system_prompt=system_prompt,
                    conversation_history=current_history,  # 使用最新的对话历史
                    current_round=self.current_round
                )
                
                logger.info(f"   ✅ LLM response received for {agent.config.id}")
                logger.info(f"   └─ Speech: {response['speech']}")
                logger.info(f"   └─ Thought: {response['thought'][:100]}..." if len(response['thought']) > 100 else f"   └─ Thought: {response['thought']}")
                logger.info(f"   └─ Suspicion scores: {response['suspicion']}")
                
            except Exception as e:
                logger.error(f"   ❌ Failed to generate description for {agent.config.id}: {e}")
                # Use fallback response
                response = {
                    "thought": "思考中...",
                    "speech": "我需要更多时间思考。",
                    "suspicion": {}
                }
            
            # Record in conversation history
            message = {
                "round": self.current_round,
                "agent_id": agent.config.id,
                "type": "description",
                "content": response["speech"],
                "thought": response["thought"],
                "suspicion": response["suspicion"]
            }
            self.conversation_history.append(message)
            responses.append(message)
            
            # Let other agents observe this
            logger.info(f"   └─ Notifying other agents about {agent.config.id}'s speech...")
            for other_agent in alive_agents:
                if other_agent.config.id != agent.config.id:
                    other_agent.observe_event(
                        f"{agent.config.id} 说: {response['speech']}",
                        self.current_round
                    )
            
            logger.info(f"   ✅ Agent {agent.config.id} completed speaking")
            logger.info("")
        
        logger.info("=" * 80)
        logger.info(f"✅ ROUND {self.current_round} - DESCRIPTION PHASE COMPLETED")
        logger.info(f"   Total responses: {len(responses)}")
        logger.info("=" * 80)
        
        return responses
    
    async def run_voting_phase(self) -> Dict[str, Any]:
        """
        Run voting phase where agents vote to eliminate someone.
        
        Returns:
            Dict with vote results and eliminated agent
        """
        self.phase = GamePhase.VOTING
        logger.info("=" * 80)
        logger.info(f"🗳️  ROUND {self.current_round} - VOTING PHASE STARTED")
        logger.info("=" * 80)
        
        votes: Dict[str, List[str]] = {}  # voted_for -> [voter_ids]
        vote_details = []
        
        alive_agents = self.get_alive_agents()
        valid_agent_ids = [a.config.id for a in alive_agents]
        
        logger.info(f"📋 Agents eligible to vote: {valid_agent_ids}")
        logger.info(f"👥 Total voters: {len(alive_agents)}")
        logger.info("")
        
        # Determine voting order (same as speaking order)
        voting_order = self._determine_speaking_order(alive_agents)
        
        for idx, agent in enumerate(voting_order, 1):
            if agent.is_possessed:
                logger.info(f"⏸️  [{idx}/{len(voting_order)}] Agent {agent.config.id} is possessed, waiting for user vote")
                continue
            
            logger.info(f"🗳️  [{idx}/{len(voting_order)}] Agent {agent.config.id} is voting...")
            logger.info(f"   └─ MBTI: {agent.config.mbti_type}, IQ: {agent.config.iq_level.value}")
            logger.info(f"   └─ Can vote for: {[aid for aid in valid_agent_ids if aid != agent.config.id]}")
            
            # Build voting prompt
            system_prompt = self._build_voting_prompt(agent, valid_agent_ids)
            
            # Generate vote
            # 获取当前最新的对话历史（包含本轮所有描述和前面的投票）
            current_history = self.conversation_history[-10:]
            logger.info(f"   └─ Calling LLM for vote from {agent.config.id}...")
            logger.info(f"   └─ Current conversation history size: {len(current_history)} messages")
            
            try:
                vote_response = await agent.generate_vote(
                    system_prompt=system_prompt,
                    conversation_history=current_history,  # 使用最新的对话历史
                    valid_agent_ids=[aid for aid in valid_agent_ids if aid != agent.config.id],
                    current_round=self.current_round
                )
                
                voted_for = vote_response["vote"]
                if voted_for not in votes:
                    votes[voted_for] = []
                votes[voted_for].append(agent.config.id)
                
                vote_details.append({
                    "voter": agent.config.id,
                    "voted_for": voted_for,
                    "confidence": vote_response["confidence"],
                    "thought": vote_response["thought"]
                })
                
                logger.info(f"   ✅ {agent.config.id} voted for {voted_for} (confidence: {vote_response['confidence']})")
                logger.info(f"   └─ Thought: {vote_response['thought'][:100]}..." if len(vote_response['thought']) > 100 else f"   └─ Thought: {vote_response['thought']}")
                
            except Exception as e:
                logger.error(f"   ❌ Failed to generate vote for {agent.config.id}: {e}")
                # Use random vote as fallback
                import random
                voted_for = random.choice([aid for aid in valid_agent_ids if aid != agent.config.id])
                if voted_for not in votes:
                    votes[voted_for] = []
                votes[voted_for].append(agent.config.id)
                logger.warning(f"   ⚠️  Using random vote: {agent.config.id} -> {voted_for}")
            
            logger.info("")
        
        # Determine who gets eliminated
        logger.info("📊 Vote Summary:")
        for candidate, voters in votes.items():
            logger.info(f"   └─ {candidate}: {len(voters)} votes from {voters}")
        logger.info("")
        
        eliminated_id = self._determine_elimination(votes)
        eliminated_agent = self.agents[eliminated_id]
        eliminated_agent.eliminate()
        
        logger.info(f"💀 ELIMINATION: Agent {eliminated_id} has been eliminated")
        logger.info(f"   └─ Role: {eliminated_agent.config.role.value}")
        logger.info(f"   └─ Word: {eliminated_agent.config.word}")
        logger.info(f"   └─ Votes received: {len(votes.get(eliminated_id, []))}")
        logger.info("")
        
        elimination_record = {
            "round": self.current_round,
            "eliminated_id": eliminated_id,
            "eliminated_word": eliminated_agent.config.word,
            "eliminated_role": eliminated_agent.config.role.value,
            "votes": votes,
            "vote_details": vote_details
        }
        self.elimination_history.append(elimination_record)
        
        # Let agents observe elimination
        logger.info("📢 Notifying remaining agents about elimination...")
        for agent in alive_agents:
            if agent.is_alive:
                agent.observe_event(
                    f"{eliminated_id} 被投票淘汰了",
                    self.current_round
                )
        
        logger.info("=" * 80)
        logger.info(f"✅ ROUND {self.current_round} - VOTING PHASE COMPLETED")
        logger.info(f"   Remaining agents: {len([a for a in alive_agents if a.is_alive])}")
        logger.info("=" * 80)
        
        return elimination_record
    
    def _determine_elimination(self, votes: Dict[str, List[str]]) -> str:
        """
        Determine which agent gets eliminated based on votes.
        
        Args:
            votes: Dict mapping voted_for -> list of voter IDs
            
        Returns:
            ID of eliminated agent
        """
        if not votes:
            # No votes, eliminate random agent
            alive_agents = self.get_alive_agents()
            return random.choice(alive_agents).config.id
        
        # Find agent(s) with most votes
        max_votes = max(len(voters) for voters in votes.values())
        candidates = [agent_id for agent_id, voters in votes.items() if len(voters) == max_votes]
        
        if len(candidates) == 1:
            return candidates[0]
        
        # Tie-breaker: random selection
        logger.info(f"Tie between {candidates}, selecting randomly")
        return random.choice(candidates)
    
    def check_win_condition(self) -> Tuple[GameResult, Optional[str]]:
        """
        Check if game has ended and determine winner.
        
        Returns:
            Tuple of (result, message)
        """
        alive_agents = self.get_alive_agents()
        
        # Check if undercover is eliminated
        undercover_alive = any(
            agent.config.role == AgentRole.UNDERCOVER
            for agent in alive_agents
        )
        
        if not undercover_alive:
            return (
                GameResult.CIVILIANS_WIN,
                "平民获胜！卧底已被淘汰。"
            )
        
        # Check if only 2 agents remain
        if len(alive_agents) <= 2:
            return (
                GameResult.UNDERCOVER_WIN,
                "卧底获胜！剩余人数过少。"
            )
        
        # Check round limit
        if self.current_round >= self.config.max_rounds:
            return (
                GameResult.UNDERCOVER_WIN,
                "卧底获胜！达到最大回合数。"
            )
        
        return (GameResult.IN_PROGRESS, None)
    
    def _build_description_prompt(self, agent: Agent, attempt: int = 0) -> str:
        """Build system prompt for description phase."""
        from models.personality import PersonalityPrompt
        
        # Get personality configuration
        personality = PersonalityPrompt.get_default(agent.config.mbti_type)
        
        # 获取其他存活 Agent 的信息
        alive_agents = self.get_alive_agents()
        other_agents_info = []
        for other_agent in alive_agents:
            if other_agent.config.id != agent.config.id:
                name = other_agent.config.name or other_agent.config.id
                other_agents_info.append(f"- {other_agent.config.id}: {name}")
        
        other_agents_list = "\n".join(other_agents_info) if other_agents_info else "（暂无其他玩家）"
        
        # 如果是重试，添加额外提示
        retry_hint = ""
        if attempt > 0:
            retry_hint = f"\n\n⚠️ 重要提示：你上一次的描述与其他人重复了，请换一个完全不同的角度描述！（这是第 {attempt + 1} 次尝试）"
        
        # 准备模板变量
        template_vars = {
            'agent_name': agent.config.name or agent.config.id,
            'mbti_type': agent.config.mbti_type,
            'iq_level': agent.config.iq_level.value,
            'word': agent.config.word,
            'other_agents_list': other_agents_list,
            'personality_traits': personality.traits,
            'speaking_style': personality.speaking_style,
            'thinking_pattern': personality.thinking_pattern,
            'retry_hint': retry_hint,
            'current_round': self.current_round
        }
        
        # 尝试从配置文件加载模板，否则使用硬编码默认值
        if self._prompt_templates and 'description_prompt' in self._prompt_templates:
            prompt_template = self._prompt_templates['description_prompt']
            prompt = prompt_template.format(**template_vars)
            logger.debug("✅ 使用配置文件中的 description_prompt")
        else:
            # 硬编码的默认 prompt（保持向后兼容）
            prompt = self._get_default_description_prompt(template_vars)
            logger.debug("ℹ️ 使用硬编码的默认 description_prompt")
        
        return prompt
    
    def _get_default_description_prompt(self, vars: Dict[str, str]) -> str:
        """获取硬编码的默认描述阶段 prompt"""
        return f"""# Role: 《谁是卧底》游戏执行官
你负责驱动一个具备人格特征的博弈智能体。

## 你的底层参数 (严格遵守):
- **你的名字**: {vars['agent_name']}
- **MBTI**: {vars['mbti_type']} (决定你的表达偏好、情绪阈值、对他人的信任方式)
- **IQ Tier**: {vars['iq_level']} (决定你的逻辑严密程度)
- **Current Word**: {vars['word']} 

## ⚠️ 游戏核心规则 - 绝对禁止 (违反将导致游戏失败):
1. **绝对不能直接说出你的词！** 
   - 例如：如果你的词是"牛奶"，不能说"牛奶"这个词
2. **绝对不能说出词中包含的任何字！**
   - 例如：如果你的词是"牛奶"，不能说"牛"字，也不能说"奶"字
   - 例如：如果你的词是"豆浆"，不能说"豆"字，也不能说"浆"字
   - 例如：如果你的词是"苹果"，不能说"苹"字，也不能说"果"字
3. **只能用完全不包含词中任何字的描述性语言暗示你的词**
   - ✅ 正确示例（词是"牛奶"）："这是一种白色的液体"、"早餐常喝的东西"、"富含钙质"
   - ❌ 错误示例（词是"牛奶"）："这是牛产的"、"含有奶制品"、"牛身上来的"
4. **这是游戏的铁律，任何违反都会立即暴露身份！**

## 🎯 描述策略 - 必须多样化:
1. **从不同角度描述**：颜色、形状、用途、来源、味道、温度、包装等
2. **❌ 严格禁止重复**：
   - 禁止说其他玩家已经说过的描述
   - 禁止说你自己之前说过的描述
   - 如果别人说了"白色"，你必须换角度，比如"冷藏保存"、"液体"、"营养丰富"
   - 如果你上一轮说了"早餐饮品"，这一轮必须说别的，比如"含钙"、"保质期短"
3. **根据你的性格选择描述方式**：
   - ENTJ/INTJ: 理性分析，提到成分、营养价值
   - INFP/ENFP: 感性描述，提到感受、情感联想
   - ISTP/ESTP: 实用描述，提到使用场景、实际功能
4. **第一轮可以简单，后续轮次要更具体**
5. **创造性很重要**：尝试用独特的角度描述，让你的发言与众不同

## 其他玩家信息:
{vars['other_agents_list']}

## 重要规则:
1. **称呼规则**: 在发言中提到其他玩家时，必须使用他们的名字，而不是 agent_id
   - 正确示例: "我觉得【小明】说的有点奇怪"
   - 错误示例: "我觉得 agent_2 说的有点奇怪"
2. **@ 提及**: 当你想特别指出某个玩家时，使用 @名字 的格式
   - 示例: "@小明，你刚才说的白色液体是什么意思？"
3. **自然对话**: 像真实的群聊一样，自然地称呼其他玩家

## 性格特征:
{vars['personality_traits']}

## 说话风格:
{vars['speaking_style']}

## 思维模式:
{vars['thinking_pattern']}

## 输出格式 (CRITICAL):
你必须严格按照以下 JSON 格式输出，不要添加任何其他文字：

{{{{
  "thought": "你的内心分析过程（最多500字）",
  "speech": "你的公开描述（一句话，最多100字）- 记住：绝对不能说出词本身或词中的任何字！",
  "suspicion": {{{{"agent_id": 可疑度分数 0-10}}}}
}}}}

示例输出（假设你的词是"牛奶"）：
{{{{
  "thought": "【小明】刚才的描述很模糊，可能在隐藏什么。【小红】的说法和我的词很接近，应该是平民。我要避开'牛'和'奶'这两个字。",
  "speech": "这个东西富含钙质和蛋白质，需要冷藏保存。",
  "suspicion": {{{{"agent_2": 7, "agent_3": 3}}}}
}}}}

更多示例（展示多样性，注意都没有包含"牛"或"奶"字）：
- High IQ 角度1: "这个东西的主要成分是蛋白质和钙，通常需要冷藏保存，保质期较短。"
- High IQ 角度2: "这种液体来自动物，经过巴氏消毒处理，富含维生素D。"
- Mid IQ 角度1: "这是一种白色的液体，很多人早餐会喝，对骨骼有好处。"
- Mid IQ 角度2: "这个东西装在盒子或瓶子里，打开后要尽快喝完。"
- Low IQ 角度1: "白色的，能喝，冰箱里有。"
- Low IQ 角度2: "甜甜的，小孩子喜欢喝。"

⚠️ 重要提醒：
- 如果对话历史中已经有人说了"白色"、"液体"、"早餐"等词，你必须避开这些词！
- 选择完全不同的描述角度，比如：温度、包装、来源、加工方式、营养成分、保存方式等
- **再次强调：绝对不能说出词中的任何字！这是游戏的核心规则！**

❌ 错误示例（违反规则）：
{{{{
  "speech": "我的词是牛奶"  // 错误1：直接说出词
}}}}
{{{{
  "speech": "这是牛产的东西"  // 错误2：包含"牛"字
}}}}
{{{{
  "speech": "这是一种奶制品"  // 错误3：包含"奶"字
}}}}

重要：
1. 只输出 JSON，不要有其他内容！
2. 在 thought 和 speech 中使用玩家名字，不要使用 agent_id
3. suspicion 的 key 仍然使用 agent_id（系统需要）
4. **绝对不能在 speech 中说出词本身或词中的任何字！**
"""
    
    def _build_voting_prompt(self, agent: Agent, valid_agent_ids: List[str]) -> str:
        """Build system prompt for voting phase."""
        # 获取其他存活 Agent 的信息
        alive_agents = self.get_alive_agents()
        other_agents_info = []
        agent_id_to_name = {}
        
        for other_agent in alive_agents:
            if other_agent.config.id != agent.config.id:
                name = other_agent.config.name or other_agent.config.id
                agent_id_to_name[other_agent.config.id] = name
                other_agents_info.append(f"- {other_agent.config.id}: {name}")
        
        other_agents_list = "\n".join(other_agents_info) if other_agents_info else "（暂无其他玩家）"
        
        # 准备模板变量
        template_vars = {
            'agent_name': agent.config.name or agent.config.id,
            'mbti_type': agent.config.mbti_type,
            'iq_level': agent.config.iq_level.value,
            'word': agent.config.word,
            'other_agents_list': other_agents_list
        }
        
        # 尝试从配置文件加载模板，否则使用硬编码默认值
        if self._prompt_templates and 'voting_prompt' in self._prompt_templates:
            prompt_template = self._prompt_templates['voting_prompt']
            prompt = prompt_template.format(**template_vars)
            logger.debug("✅ 使用配置文件中的 voting_prompt")
        else:
            # 硬编码的默认 prompt（保持向后兼容）
            prompt = self._get_default_voting_prompt(template_vars)
            logger.debug("ℹ️ 使用硬编码的默认 voting_prompt")
        
        return prompt
    
    def _get_default_voting_prompt(self, vars: Dict[str, str]) -> str:
        """获取硬编码的默认投票阶段 prompt"""
        return f"""# 投票阶段

你需要根据之前的对话，投票淘汰一个你认为是卧底的玩家。

## 你的信息:
- **你的名字**: {vars['agent_name']}
- **MBTI**: {vars['mbti_type']}
- **IQ Tier**: {vars['iq_level']}
- **Your Word**: {vars['word']}

## 可投票的玩家:
{vars['other_agents_list']}

## 重要规则:
1. 在 thought 中使用玩家名字分析，不要使用 agent_id
2. vote 字段必须填写 agent_id（系统需要）
3. 示例: "我觉得【小明】最可疑" → vote: "agent_2"

## 输出格式:
{{{{
  "thought": "你的投票理由（最多500字），使用玩家名字",
  "vote": "agent_id",
  "confidence": 0.85
}}}}

示例输出：
{{{{
  "thought": "综合分析，【小明】的描述和大家完全不同，很可能是卧底。【小红】和【小刚】的说法都很一致。",
  "vote": "agent_2",
  "confidence": 0.85
}}}}

重要：只输出 JSON！
"""
    
    def get_state(self) -> GameState:
        """Get current game state."""
        return GameState(
            game_id=self.config.game_id,
            current_round=self.current_round,
            phase=self.phase,
            agents=[agent.get_state() for agent in self.agents.values()],
            conversation_history=self.conversation_history,
            elimination_history=self.elimination_history
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize game state."""
        return {
            "config": _model_dump(self.config),
            "current_round": self.current_round,
            "phase": self.phase.value,
            "agents": {aid: agent.to_dict() for aid, agent in self.agents.items()},
            "conversation_history": self.conversation_history,
            "elimination_history": self.elimination_history,
            "speakers_this_round": self.speakers_this_round,
            "speaking_order": self.speaking_order,
            "voters_this_round": self.voters_this_round
        }
    
    # ==================== Select Speaker 模式方法 ====================
    
    def start_new_round(self):
        """开始新的一轮，重置发言和投票状态"""
        self.current_round += 1
        self.phase = GamePhase.DESCRIPTION
        self.speakers_this_round = []
        self.speaking_order = []
        self.voters_this_round = []
        logger.info(f"Started round {self.current_round}")
    
    def select_next_speaker(self, strategy: str = "round_robin", manual_agent_id: Optional[str] = None) -> Optional[str]:
        """
        选择下一个发言人
        
        Args:
            strategy: 选择策略 ("round_robin", "random", "manual")
            manual_agent_id: 手动指定的 Agent ID (仅当 strategy="manual" 时使用)
            
        Returns:
            选中的 Agent ID，如果所有人都发言完毕则返回 None
        """
        alive_agents = self.get_alive_agents()
        alive_ids = [a.config.id for a in alive_agents]
        
        # 找出还没发言的 Agent
        remaining = [aid for aid in alive_ids if aid not in self.speakers_this_round]
        
        if not remaining:
            logger.info("All agents have spoken this round")
            return None
        
        if strategy == "manual" and manual_agent_id:
            if manual_agent_id in remaining:
                return manual_agent_id
            else:
                logger.warning(f"Manual agent {manual_agent_id} not in remaining speakers")
                return remaining[0]
        
        elif strategy == "random":
            import random
            return random.choice(remaining)
        
        else:  # round_robin (默认)
            return remaining[0]
    
    async def agent_speak(self, agent_id: str, max_retries: int = 2) -> Dict[str, Any]:
        """
        让指定的 Agent 发言

        Args:
            agent_id: Agent ID
            max_retries: 最大重试次数（如果检测到重复）

        Returns:
            包含发言内容和状态的字典
        """
        agent = self.get_agent(agent_id)
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")

        if not agent.is_alive:
            raise ValueError(f"Agent {agent_id} is not alive")

        if agent_id in self.speakers_this_round:
            raise ValueError(f"Agent {agent_id} has already spoken this round")

        # 夺舍模式下跳过 AI 发言
        if agent.is_possessed:
            logger.info(f"Agent {agent_id} is possessed, skipping AI generation")
            # 返回等待用户输入的状态
            return {
                "agent_id": agent_id,
                "speech": "",
                "thought": "",
                "suspicion": {},
                "is_duplicate": False,
                "eliminated": False,
                "all_spoke": False,
                "speakers_count": len(self.speakers_this_round),
                "total_count": len(self.get_alive_agents()),
                "waiting_for_user": True
            }

        # 尝试生成发言，如果重复则重试
        for attempt in range(max_retries + 1):
            # 生成发言
            system_prompt = self._build_description_prompt(agent, attempt=attempt)
            current_history = self.conversation_history[-15:]  # 增加历史上下文

            response = await agent.generate_description(
                system_prompt=system_prompt,
                conversation_history=current_history,
                current_round=self.current_round
            )

            # 检测重复发言
            is_duplicate, duplicate_agent_id, duplicate_speech = self.check_duplicate_speech(
                current_speech=response["speech"],
                agent_id=agent_id,
                threshold=0.9
            )

            # 如果不重复，或者已经是最后一次尝试，接受这个发言
            if not is_duplicate or attempt == max_retries:
                if is_duplicate and attempt == max_retries:
                    logger.warning(f"Agent {agent_id} still duplicate after {max_retries} retries, accepting anyway")

                # 正常发言：记录发言
                message = {
                    "round": self.current_round,
                    "agent_id": agent_id,
                    "type": "description",
                    "content": response["speech"],
                    "thought": response["thought"],
                    "suspicion": response["suspicion"]
                }
                self.conversation_history.append(message)
                self.speakers_this_round.append(agent_id)
                self.speaking_order.append(agent_id)

                # 通知其他 Agents
                for other_agent in self.get_alive_agents():
                    if other_agent.config.id != agent_id:
                        other_agent.observe_event(
                            f"{agent.config.name or agent_id} 说: {response['speech']}",
                            self.current_round
                        )

                # 检查是否所有人都发言完毕
                alive_count = len(self.get_alive_agents())
                all_spoke = len(self.speakers_this_round) >= alive_count

                logger.info(f"Agent {agent_id} spoke ({len(self.speakers_this_round)}/{alive_count})")

                return {
                    "agent_id": agent_id,
                    "speech": response["speech"],
                    "thought": response["thought"],
                    "suspicion": response["suspicion"],
                    "is_duplicate": False,
                    "eliminated": False,
                    "all_spoke": all_spoke,
                    "speakers_count": len(self.speakers_this_round),
                    "total_count": alive_count,
                    "retry_count": attempt
                }
            else:
                # 重复了，记录并重试
                logger.warning(f"Agent {agent_id} speech duplicate (attempt {attempt + 1}/{max_retries + 1}), retrying...")
                await asyncio.sleep(0.5)  # 短暂延迟后重试
    
    def can_start_voting(self) -> bool:
        """检查是否可以开始投票"""
        alive_count = len(self.get_alive_agents())
        return len(self.speakers_this_round) >= alive_count
    
    def start_voting_phase(self):
        """开始投票阶段"""
        if not self.can_start_voting():
            raise ValueError("Not all agents have spoken yet")
        
        self.phase = GamePhase.VOTING
        self.voters_this_round = []
        logger.info("Started voting phase")
    
    async def agent_vote(self, agent_id: str) -> Dict[str, Any]:
        """
        让指定的 Agent 投票
        
        Args:
            agent_id: Agent ID
            
        Returns:
            包含投票内容和状态的字典
        """
        agent = self.get_agent(agent_id)
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")
        
        if not agent.is_alive:
            raise ValueError(f"Agent {agent_id} is not alive")
        
        if agent_id in self.voters_this_round:
            raise ValueError(f"Agent {agent_id} has already voted this round")
        
        alive_agents = self.get_alive_agents()
        valid_agent_ids = [a.config.id for a in alive_agents]
        
        # 生成投票
        system_prompt = self._build_voting_prompt(agent, valid_agent_ids)
        current_history = self.conversation_history[-10:]
        
        vote_response = await agent.generate_vote(
            system_prompt=system_prompt,
            conversation_history=current_history,
            valid_agent_ids=[aid for aid in valid_agent_ids if aid != agent_id],
            current_round=self.current_round
        )
        
        self.voters_this_round.append(agent_id)
        
        # 检查是否所有人都投票完毕
        alive_count = len(alive_agents)
        all_voted = len(self.voters_this_round) >= alive_count
        
        logger.info(f"Agent {agent_id} voted for {vote_response['vote']} ({len(self.voters_this_round)}/{alive_count})")
        
        return {
            "agent_id": agent_id,
            "voted_for": vote_response["vote"],
            "confidence": vote_response["confidence"],
            "thought": vote_response["thought"],
            "all_voted": all_voted,
            "voters_count": len(self.voters_this_round),
            "total_count": alive_count
        }
    
    async def complete_voting_and_eliminate(self) -> Dict[str, Any]:
        """
        完成投票并淘汰得票最多的 Agent
        
        Returns:
            包含淘汰信息和游戏状态的字典
        """
        if self.phase != GamePhase.VOTING:
            raise ValueError("Not in voting phase")
        
        alive_agents = self.get_alive_agents()
        if len(self.voters_this_round) < len(alive_agents):
            raise ValueError("Not all agents have voted yet")
        
        # 收集所有投票（从 agent 的 vote_history 中获取）
        votes = {}
        vote_details = []
        
        for agent in alive_agents:
            if agent.vote_history:
                last_vote = agent.vote_history[-1]
                voted_for = last_vote["voted_for"]
                
                if voted_for not in votes:
                    votes[voted_for] = []
                votes[voted_for].append(agent.config.id)
                
                vote_details.append({
                    "voter": agent.config.id,
                    "voted_for": voted_for,
                    "confidence": last_vote.get("confidence", 0.5),
                    "thought": last_vote.get("thought", "")
                })
        
        # 淘汰得票最多的 Agent
        eliminated_id = self._determine_elimination(votes)
        eliminated_agent = self.agents[eliminated_id]
        eliminated_agent.eliminate()
        
        elimination_record = {
            "round": self.current_round,
            "eliminated_id": eliminated_id,
            "eliminated_name": eliminated_agent.config.name or eliminated_id,
            "eliminated_word": eliminated_agent.config.word,
            "eliminated_role": eliminated_agent.config.role.value,
            "votes": votes,
            "vote_details": vote_details
        }
        self.elimination_history.append(elimination_record)
        
        # 通知剩余 Agents
        for agent in alive_agents:
            if agent.is_alive:
                agent.observe_event(
                    f"{eliminated_id} 被投票淘汰了",
                    self.current_round
                )
        
        # 检查游戏结束条件
        self.phase = GamePhase.DESCRIPTION
        result, message = self.check_win_condition()
        
        logger.info(f"Agent {eliminated_id} eliminated. Game result: {result.value}")
        
        return {
            "eliminated_id": eliminated_id,
            "eliminated_name": eliminated_agent.config.name or eliminated_id,
            "eliminated_role": eliminated_agent.config.role.value,
            "eliminated_word": eliminated_agent.config.word,
            "votes": votes,
            "vote_count": len(votes.get(eliminated_id, [])),
            "game_over": result != GameResult.IN_PROGRESS,
            "result": result.value if result != GameResult.IN_PROGRESS else None,
            "message": message
        }
