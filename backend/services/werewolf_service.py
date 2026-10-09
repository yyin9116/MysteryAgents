"""
Werewolf game service - 狼人杀游戏核心逻辑

Implements complete werewolf game logic including:
- Game creation and role assignment
- Night actions (werewolf kill, seer check, witch save/poison, guard protect)
- Day phase (dawn announcement, discussion, voting)
- Win condition checking
- Agent state management
"""

import logging
import json
import random
import re
import uuid
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime

from models.werewolf import (
    WerewolfRole, WerewolfFaction, WerewolfPhase, NightActionType,
    WerewolfGameState, WerewolfAgentState, WitchPotions, NightAction,
    ROLE_DISTRIBUTION, get_faction, get_role_name_cn, GameEvent, GameEventType
)
from models.agent import Agent, AgentConfig, IQLevel
from models.personality import PersonalityPrompt
from services.agent_factory import AgentFactory
from services.memory_service import AgentMemorySystem
from services import prompt_registry
from services.werewolf_replay_store import werewolf_replay_store

logger = logging.getLogger(__name__)


class WerewolfService:
    """Werewolf game service managing game state and logic."""

    def __init__(
        self,
        game_id: str,
        player_count: int,
        model_config: Optional[Dict[str, Any]] = None,
        game_config: Optional[Dict[str, Any]] = None,
        agent_model_configs: Optional[List[Optional[Dict[str, Any]]]] = None,
        roster: Optional[List[Dict[str, Any]]] = None,
        roster_work: Optional[str] = None,
        auto_model_plan: Optional[Dict[str, Any]] = None,
        player_mode: str = "spectate",
        player_agent_id: Optional[str] = None,
    ):
        """
        Initialize werewolf game.

        Args:
            game_id: Unique game identifier
            player_count: Number of players (6-12)
            model_config: Optional model configuration shared by all agents
            agent_model_configs: Optional per-slot model overrides; index i maps
                to werewolf_agent_{i+1}. None entries inherit model_config.
            roster: Optional themed roster (name + mbti + gender per slot) from
                the roster preview; index i maps to werewolf_agent_{i+1}.
                When present, agent names/MBTI come from the roster and the
                LLM rename pass is skipped to keep the theme intact.
            roster_work: Optional source work name (e.g. 西游记) the roster
                characters come from; used to flavor public speech with the
                character's iconic traits.
            auto_model_plan: Optional smart model assignment plan:
                {"candidates": [...], "blacklist": [...], "effort_by_role": bool}.
                Roles are assigned inside _create_agents, so slot→model mapping
                is computed there by role strength tier.
        """
        if player_count not in ROLE_DISTRIBUTION:
            raise ValueError(f"Invalid player count: {player_count}. Must be 6-12.")

        self.game_id = game_id
        self.player_count = player_count
        self.model_config = model_config
        self.agent_model_configs = agent_model_configs
        self.auto_model_plan = auto_model_plan or {}
        self.roster = self._normalize_roster(roster)
        self.roster_work = (roster_work or "").strip()
        # 夺席模式下玩家代打的发言：agent_id -> 待消费的发言文本
        self.pending_player_speeches: Dict[str, str] = {}
        # 参与模式：participate = 玩家接管一个席位（发言/投票由玩家提交）
        self.player_mode = player_mode if player_mode in ("spectate", "participate") else "spectate"
        self.player_agent_id = player_agent_id
        self.game_config = game_config or {}
        self.fast_mode = bool(self.game_config.get("fast_mode", False))
        # 讨论风格：speech = 圆桌完整发言；group_chat = QQ/微信群聊短消息气泡
        self.chat_style = self.game_config.get("chat_style") or "speech"
        configured_turn_limit = self.game_config.get("discussion_turn_limit")
        if configured_turn_limit is None and self.fast_mode:
            configured_turn_limit = min(2, player_count)
        self.discussion_turn_limit = configured_turn_limit

        # Initialize game state
        self.state = WerewolfGameState(
            game_id=game_id,
            phase=WerewolfPhase.NIGHT,
            current_round=1,
            agents={},
            night_actions=[],
            conversation_history=[],
            death_tonight=[],
            votes_this_round={},
            speakers_this_round=[]
        )

        # Agent instances
        self.agents: Dict[str, Agent] = {}

        # Game events for replay
        self.game_events: List[GameEvent] = []

        # Create agents with role assignment
        self._create_agents()

        # 参与模式：玩家接管的席位标记为受控（仅状态层，运行时仍可代打）
        if self.player_mode == "participate":
            if not self.player_agent_id or self.player_agent_id not in self.state.agents:
                self.player_agent_id = "werewolf_agent_1"
            self.state.agents[self.player_agent_id].is_possessed = True

        self._persist_replay()

        logger.info(f"Created werewolf game {game_id} with {player_count} players")

    def get_discussion_agents_for_round(self) -> List[WerewolfAgentState]:
        """Return the alive agents scheduled to speak this round."""
        alive_agents = self.get_alive_agents()
        if self.discussion_turn_limit is None:
            return alive_agents
        return alive_agents[: max(1, min(len(alive_agents), int(self.discussion_turn_limit)))]

    @staticmethod
    def _model_dump(model: Any) -> Dict[str, Any]:
        """Compatibility helper for Pydantic v1/v2 style models."""
        if hasattr(model, "model_dump"):
            return model.model_dump(mode="json")
        return model.dict()

    @staticmethod
    def _enum_value(value: Any) -> Any:
        """Return enum value when present, otherwise the raw value."""
        return value.value if hasattr(value, "value") else value

    # 间隔号变体统一为「·」：・(片假名中点)、‧、•、∙ 等
    _NAME_SEPARATOR_VARIANTS = str.maketrans({"・": "·", "‧": "·", "•": "·", "∙": "·", "⋅": "·"})
    _EMOJI_RE = re.compile(
        "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF\u2B00-\u2BFF\uFE0F]"
    )

    @classmethod
    def _clean_character_name(cls, name: str) -> str:
        """统一译名分隔符并去掉 emoji：译名拆分由提示词负责；・→·；去除空白。"""
        name = cls._EMOJI_RE.sub("", name)
        name = name.translate(cls._NAME_SEPARATOR_VARIANTS)
        name = re.sub(r"\s+", "", name)
        return name

    @staticmethod
    def _normalize_roster(roster: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """Normalize a themed roster: keep valid entries, dedupe names."""
        if not roster:
            return []
        valid_mbti = {
            "ENTJ", "INFP", "ISTP", "ENFJ", "INTP", "ESTJ", "ISFP", "ENTP",
            "ISFJ", "ESFP", "INTJ", "ESFJ", "ESTP", "INFJ", "ENFP", "ISTJ",
        }
        normalized: List[Dict[str, Any]] = []
        seen: set[str] = set()
        for item in roster:
            if not isinstance(item, dict):
                continue
            name = WerewolfService._clean_character_name(str(item.get("name") or "")).strip()
            mbti = str(item.get("mbti") or "").strip().upper()
            if not (2 <= len(name) <= 15) or name in seen or mbti not in valid_mbti:
                continue
            seen.add(name)
            normalized.append(
                {
                    "name": name,
                    "mbti": mbti,
                    "gender": "女" if "女" in str(item.get("gender") or "") else "男",
                }
            )
        return normalized

    # 角色强度分档：0 = 需要最强推理（核心博弈角色），1 = 中等，2 = 轻量
    _ROLE_TIER = {
        WerewolfRole.WEREWOLF: 0,
        WerewolfRole.SEER: 0,
        WerewolfRole.WITCH: 0,
        WerewolfRole.HUNTER: 1,
        WerewolfRole.GUARD: 1,
        WerewolfRole.VILLAGER: 2,
    }

    # 思考强度：核心角色高配思考，村民轻量思考
    _ROLE_EFFORT = {
        WerewolfRole.WEREWOLF: "high",
        WerewolfRole.SEER: "high",
        WerewolfRole.WITCH: "high",
        WerewolfRole.HUNTER: "medium",
        WerewolfRole.GUARD: "medium",
        WerewolfRole.VILLAGER: "low",
    }

    # 模型强度启发式：关键词命中计分，分高 = 更强
    _MODEL_STRONG_KEYWORDS = (
        "opus", "gpt-5", "gpt-4.1", "o3", "o4", "pro", "max", "grok-4",
        "deepseek-r1", "-r1", "glm-4.6", "glm-4.5", "kimi-k2", "qwen-max",
        "thinking", "reasoner", "ultra", "plus",
    )
    _MODEL_WEAK_KEYWORDS = (
        "mini", "flash", "lite", "nano", "small", "tiny", "-8b", "-7b", "-4b",
        "haiku", "instant", "-air", "turbo", "free", "spark",
    )

    @classmethod
    def _rank_model_strength(cls, model_id: str) -> tuple[int, str]:
        """Score a model id by keyword heuristics; higher = stronger."""
        normalized = (model_id or "").lower()
        score = 0
        for keyword in cls._MODEL_STRONG_KEYWORDS:
            if keyword in normalized:
                score += 2
        for keyword in cls._MODEL_WEAK_KEYWORDS:
            if keyword in normalized:
                score -= 2
        return (score, normalized)

    @staticmethod
    def _filter_candidate_models(
        candidates: Optional[List[str]] = None,
        blacklist: Optional[List[str]] = None,
        disabled_models: Optional[List[str]] = None,
    ) -> List[str]:
        """Normalize candidates and drop disabled ones.

        disabled_models: 精确匹配（前端模型列表勾选禁用，传完整模型 id）；
        blacklist: 兼容旧版关键字子串匹配。
        """
        # 兼容旧的实例调用签名 (candidates, blacklist)
        patterns = [
            str(item).strip().lower()
            for item in (blacklist or [])
            if str(item).strip()
        ]
        disabled = {
            str(item).strip().lower()
            for item in (disabled_models or [])
            if str(item).strip()
        }
        seen: set[str] = set()
        result: List[str] = []
        for item in candidates or []:
            model_id = str(item).strip()
            if not model_id:
                continue
            key = model_id.lower()
            if key in seen or key in disabled:
                continue
            if any(pattern in key or key in pattern for pattern in patterns):
                continue
            seen.add(key)
            result.append(model_id)
        return result

    def _plan_auto_models(self, roles: List[WerewolfRole]) -> Dict[int, Dict[str, Any]]:
        """Compute slot → {model, effort} mapping by role strength tier.

        Called from _create_agents after roles are known. Candidates are ranked
        strong→weak; tier-0 roles pick from the strongest end, tier-2 from the
        weakest end, tier-1 from the middle. When the pool is small the pool
        cycles so every player still gets a deterministic assignment.
        """
        plan = self.auto_model_plan or {}
        if not self.model_config:
            return {}
        candidates = self._filter_candidate_models(
            plan.get("candidates"),
            plan.get("blacklist"),
            plan.get("disabled_models"),
        )
        if not candidates:
            logger.warning(
                "Auto model plan for game %s has no usable candidates after blacklist filter",
                self.game_id,
            )
            return {}

        ranked = sorted(candidates, key=self._rank_model_strength, reverse=True)
        groups: Dict[int, List[int]] = {0: [], 1: [], 2: []}
        for idx, role in enumerate(roles):
            groups[self._ROLE_TIER[role]].append(idx)

        mid = len(ranked) // 3
        pools = {
            0: ranked,
            1: ranked[mid:] if len(ranked) >= 3 else ranked,
            2: list(reversed(ranked)),
        }
        cursors = {0: 0, 1: 0, 2: 0}
        assignment: Dict[int, Dict[str, Any]] = {}
        for tier in (0, 1, 2):
            pool = pools[tier]
            for idx in groups[tier]:
                effort = self._ROLE_EFFORT[roles[idx]] if plan.get("effort_by_role", True) else None
                if self.fast_mode:
                    # 快测模式压低思考强度，避免推理模型拖慢发言节奏
                    effort = "low"
                assignment[idx] = {
                    "model": pool[cursors[tier] % len(pool)],
                    "effort": effort,
                }
                cursors[tier] += 1
        logger.info(
            "Auto model plan for game %s: %s candidates -> %s slots assigned",
            self.game_id, len(ranked), len(assignment),
        )
        return assignment

    def _create_agents(self):
        """Create agents and assign roles."""
        # Get role distribution for player count
        role_dist = ROLE_DISTRIBUTION[self.player_count]

        # Build role list
        roles = []
        for role, count in role_dist.items():
            roles.extend([role] * count)

        # Shuffle roles
        random.shuffle(roles)

        # 智能模型分配：角色已定，按强度分档为每个槽位预选模型与思考强度
        auto_assignments = self._plan_auto_models(roles)

        # Create agent factory
        factory = AgentFactory()

        # Create agents with assigned roles
        for i, role in enumerate(roles):
            agent_id = f"werewolf_agent_{i+1}"

            # Per-slot model override: index i -> werewolf_agent_{i+1}
            per_agent_config = None
            if self.agent_model_configs and i < len(self.agent_model_configs):
                per_agent_config = self.agent_model_configs[i]
            effective_config = per_agent_config or self.model_config

            # 智能分配只在玩家未手动指定模型时生效
            auto_pick = auto_assignments.get(i)
            if auto_pick and per_agent_config is None and effective_config:
                effective_config = {
                    **effective_config,
                    "model": auto_pick["model"],
                }
                if auto_pick.get("effort"):
                    effective_config["extra_params"] = {
                        **(effective_config.get("extra_params") or {}),
                        "reasoning_effort": auto_pick["effort"],
                    }

            # Select MBTI and IQ based on role
            mbti_type, iq_level = self._select_personality_for_role(role)

            # 主题角色阵容：名字与 MBTI 由 roster 指定（名-MBTI-性别绑定）
            gender_note = ""
            agent_name = None
            if self.roster and i < len(self.roster):
                entry = self.roster[i]
                agent_name = entry["name"]
                mbti_type = entry["mbti"]
                gender_note = f"\n- 性别: {entry['gender']}（角色扮演时保持一致的性别气质）"

            # Create agent config
            config = AgentConfig(
                id=agent_id,
                mbti_type=mbti_type,
                iq_level=iq_level,
                word=None,  # No word in werewolf game
                name=agent_name or factory._generate_name(mbti_type)
            )

            # Create memory system
            memory_system = AgentMemorySystem(agent_id=agent_id, iq_level=iq_level)

            faction = get_faction(role)

            # Create agent
            role_name = get_role_name_cn(role)
            work_note = ""
            if self.roster_work and agent_name:
                work_note = (
                    f"\n- 角色出处: 你的名字「{agent_name}」来自作品《{self.roster_work}》。"
                    f"公开发言可以适度带入这个角色的经典气质、口头禅或比喻方式（符合大众对"
                    f"该角色的印象即可，不必考据原著），让发言更有辨识度；"
                    f"但狼人杀的局势判断、怀疑与投票逻辑必须基于场上信息，"
                    f"绝不能把原著情节当成对局里的事实。"
                )
            runtime_context = (
                "这是狼人杀游戏，不是《谁是卧底》。\n"
                f"- 真实角色: {role_name}\n"
                f"- 阵营: {faction.value}\n"
                "- 没有词语描述任务；所有发言、投票和夜间行动都围绕狼人杀局势推理。\n"
                "- 不要在公开发言中泄露只有自己阵营或神职才知道的私密信息，除非策略明确要求跳身份。"
                f"{gender_note}"
                f"{work_note}"
            )
            agent = Agent(
                config=config,
                memory_system=memory_system,
                model_config=effective_config,
                runtime_context=runtime_context,
            )
            self.agents[agent_id] = agent

            # Model label for the multi-model experiment HUD
            model_label = None
            if effective_config:
                provider = effective_config.get("provider")
                model_id = effective_config.get("model")
                if provider or model_id:
                    model_label = f"{provider or 'default'}/{model_id or ''}"

            # Create agent state
            agent_state = WerewolfAgentState(
                agent_id=agent_id,
                name=config.name,
                role=role,
                faction=faction,
                is_alive=True,
                is_possessed=False,
                mbti_type=mbti_type,
                iq_level=iq_level,
                model_label=model_label
            )

            # Initialize role-specific state
            if role == WerewolfRole.WITCH:
                agent_state.witch_potions = WitchPotions(antidote=True, poison=True)
            elif role == WerewolfRole.GUARD:
                agent_state.guard_last_protected = None
            elif role == WerewolfRole.SEER:
                agent_state.seer_checked_ids = []
                agent_state.seer_check_results = {}

            self.state.agents[agent_id] = agent_state

            logger.info(f"Created agent {agent_id} ({config.name}) - Role: {get_role_name_cn(role)}, Faction: {faction.value}")

    async def apply_llm_agent_names(self) -> int:
        """用 LLM 为每个玩家生成个性化昵称（多模型实验的观感增强）。

        - 每个玩家使用各自的 model_config 调用，保证「不同玩家不同模型」时
          昵称风格也来自对应模型；
        - 并发执行、单玩家失败不影响他人；
        - 成功后更新 AgentConfig 与对局状态并持久化回放；
        - 失败/超时/重名时保留角色库生成的名字作为兜底。

        Returns:
            成功改名的玩家数量
        """
        from services.llm_service import LLMService

        llm = LLMService()
        used_names = {a.config.name for a in self.agents.values() if a.config.name}

        async def _rename(agent_id: str, agent: Agent) -> bool:
            try:
                raw = await llm.generate_agent_name(
                    mbti_type=str(getattr(agent.config.mbti_type, "value", agent.config.mbti_type)),
                    iq_level=str(getattr(agent.config.iq_level, "value", agent.config.iq_level)),
                    session_id=f"{self.game_id}:{agent_id}",
                    model_config=agent.model_config,
                )
            except Exception as exc:
                logger.warning("LLM naming failed for %s: %s", agent_id, exc)
                return False

            name = (raw or "").strip().strip('"\'，。！？\n ')
            if not name or len(name) < 2 or len(name) > 15 or name in used_names:
                logger.info("LLM name %r rejected for %s, keeping fallback", name, agent_id)
                return False

            used_names.add(name)
            agent.config.name = name
            state = self.state.agents.get(agent_id)
            if state is not None:
                state.name = name
            return True

        results = await asyncio.gather(
            *[_rename(agent_id, agent) for agent_id, agent in self.agents.items()],
            return_exceptions=True,
        )
        renamed = sum(1 for ok in results if ok is True)
        if renamed:
            logger.info("LLM renamed %s/%s agents in game %s", renamed, len(self.agents), self.game_id)
            self._persist_replay()
        return renamed

    def _select_personality_for_role(self, role: WerewolfRole) -> tuple[str, str]:
        """Select appropriate MBTI and IQ for a role."""
        # Strategic roles get higher IQ
        if role in [WerewolfRole.SEER, WerewolfRole.WITCH]:
            mbti_options = ["INTJ", "ENTJ", "INTP"]
            iq = "High"
        elif role == WerewolfRole.WEREWOLF:
            mbti_options = ["ENTJ", "INTJ", "ENTP", "ESTP"]
            iq = random.choice(["High", "Mid"])
        elif role == WerewolfRole.HUNTER:
            mbti_options = ["ESTP", "ISTP", "ESTJ"]
            iq = "Mid"
        elif role == WerewolfRole.GUARD:
            mbti_options = ["ISTJ", "ISFJ", "ESTJ"]
            iq = "Mid"
        else:  # Villager
            mbti_options = ["INFP", "ENFP", "ISFP", "ESFP", "ISFJ"]
            iq = random.choice(["Mid", "Low"])

        return random.choice(mbti_options), iq

    def _record_event(
        self,
        event_type: GameEventType,
        data: Dict[str, Any],
        include_snapshot: bool = False
    ) -> GameEvent:
        """Record a game event for replay."""
        event = GameEvent(
            event_id=f"event_{len(self.game_events) + 1}",
            timestamp=datetime.now(),
            event_type=event_type,
            round=self.state.current_round,
            phase=self.state.phase,
            data=data,
            game_state_snapshot=self._create_state_snapshot() if include_snapshot else None
        )
        self.game_events.append(event)
        self._persist_replay()
        return event

    def _create_state_snapshot(self) -> Dict[str, Any]:
        """Create a snapshot of current game state."""
        return {
            "phase": self._enum_value(self.state.phase),
            "current_round": self.state.current_round,
            "alive_agents": [
                {
                    "agent_id": agent.agent_id,
                    "name": agent.name,
                    "is_alive": agent.is_alive,
                    "is_possessed": agent.is_possessed
                }
                for agent in self.state.agents.values()
            ],
            "alive_count": len([a for a in self.state.agents.values() if a.is_alive]),
            "werewolf_count": len([a for a in self.state.agents.values() if a.is_alive and a.role == WerewolfRole.WEREWOLF]),
            "good_count": len([a for a in self.state.agents.values() if a.is_alive and a.faction == WerewolfFaction.GOOD])
        }

    def get_agent_state(self, agent_id: str) -> Optional[WerewolfAgentState]:
        """Get agent state by ID."""
        return self.state.agents.get(agent_id)

    def get_alive_agents(self) -> List[WerewolfAgentState]:
        """Get all alive agents."""
        return [agent for agent in self.state.agents.values() if agent.is_alive]

    def get_alive_werewolves(self) -> List[WerewolfAgentState]:
        """Get all alive werewolves."""
        return [
            agent for agent in self.state.agents.values()
            if agent.is_alive and agent.role == WerewolfRole.WEREWOLF
        ]

    def get_alive_good_players(self) -> List[WerewolfAgentState]:
        """Get all alive good faction players."""
        return [
            agent for agent in self.state.agents.values()
            if agent.is_alive and agent.faction == WerewolfFaction.GOOD
        ]

    def record_night_action(
        self,
        actor_id: str,
        action_type: NightActionType,
        target_id: Optional[str] = None,
        result: Optional[str] = None
    ) -> NightAction:
        """Record a night action."""
        action = NightAction(
            actor_id=actor_id,
            action_type=action_type,
            target_id=target_id,
            result=result,
            round=self.state.current_round
        )
        self.state.night_actions.append(action)
        logger.info(f"Recorded night action: {action_type.value} by {actor_id} on {target_id}")
        return action

    def werewolf_kill(self, werewolf_id: str, target_id: str) -> Dict[str, Any]:
        """
        Werewolf kills a target.

        Args:
            werewolf_id: ID of the werewolf
            target_id: ID of the target

        Returns:
            Result dict with success status
        """
        # Validate werewolf
        werewolf = self.get_agent_state(werewolf_id)
        if not werewolf or werewolf.role != WerewolfRole.WEREWOLF or not werewolf.is_alive:
            raise ValueError(f"Invalid werewolf: {werewolf_id}")

        # Validate target
        target = self.get_agent_state(target_id)
        if not target or not target.is_alive:
            raise ValueError(f"Invalid target: {target_id}")

        if target.role == WerewolfRole.WEREWOLF:
            raise ValueError("Werewolves cannot kill each other")

        # Record kill target
        self.state.werewolf_kill_target = target_id

        # Record action
        self.record_night_action(werewolf_id, NightActionType.WEREWOLF_KILL, target_id)

        # Record event
        self._record_event(
            GameEventType.NIGHT_ACTION,
            {
                "action_type": "werewolf_kill",
                "actor_id": werewolf_id,
                "actor_name": werewolf.name,
                "target_id": target_id,
                "target_name": target.name
            }
        )

        logger.info(f"Werewolf {werewolf_id} targets {target_id} for kill")

        return {
            "success": True,
            "werewolf_id": werewolf_id,
            "target_id": target_id,
            "message": f"狼人选择击杀 {target.name}"
        }

    def seer_check(self, seer_id: str, target_id: str) -> Dict[str, Any]:
        """
        Seer checks a player's faction.

        Args:
            seer_id: ID of the seer
            target_id: ID of the target to check

        Returns:
            Result dict with faction information
        """
        # Validate seer
        seer = self.get_agent_state(seer_id)
        if not seer or seer.role != WerewolfRole.SEER or not seer.is_alive:
            raise ValueError(f"Invalid seer: {seer_id}")

        # Validate target
        target = self.get_agent_state(target_id)
        if not target or not target.is_alive:
            raise ValueError(f"Invalid target: {target_id}")

        if target_id == seer_id:
            raise ValueError("Seer cannot check themselves")

        # Check if already checked
        if target_id in seer.seer_checked_ids:
            raise ValueError(f"Seer already checked {target_id}")

        # Record check
        seer.seer_checked_ids.append(target_id)
        seer.seer_check_results[target_id] = target.faction

        # Record action
        self.record_night_action(
            seer_id,
            NightActionType.SEER_CHECK,
            target_id,
            result=self._enum_value(target.faction)
        )

        # Record event
        self._record_event(
            GameEventType.NIGHT_ACTION,
            {
                "action_type": "seer_check",
                "actor_id": seer_id,
                "actor_name": seer.name,
                "target_id": target_id,
                "target_name": target.name,
                "result": self._enum_value(target.faction)
            }
        )

        logger.info(f"Seer {seer_id} checks {target_id}: {self._enum_value(target.faction)}")

        return {
            "success": True,
            "seer_id": seer_id,
            "target_id": target_id,
            "target_name": target.name,
            "faction": self._enum_value(target.faction),
            "is_werewolf": target.faction == WerewolfFaction.WEREWOLF,
            "message": f"预言家查验 {target.name}：{'狼人' if target.faction == WerewolfFaction.WEREWOLF else '好人'}"
        }

    def witch_save(self, witch_id: str, target_id: str) -> Dict[str, Any]:
        """
        Witch uses antidote to save a player.

        Args:
            witch_id: ID of the witch
            target_id: ID of the player to save

        Returns:
            Result dict with success status
        """
        # Validate witch
        witch = self.get_agent_state(witch_id)
        if not witch or witch.role != WerewolfRole.WITCH or not witch.is_alive:
            raise ValueError(f"Invalid witch: {witch_id}")

        # Check if antidote is available
        if not witch.witch_potions or not witch.witch_potions.antidote:
            raise ValueError("Witch has already used antidote")

        # Validate target is the kill target
        if target_id != self.state.werewolf_kill_target:
            raise ValueError(f"Can only save the werewolf kill target")

        # Use antidote
        witch.witch_potions.antidote = False

        # Record action
        self.record_night_action(
            witch_id,
            NightActionType.WITCH_SAVE,
            target_id,
            result="saved"
        )

        logger.info(f"Witch {witch_id} saves {target_id}")

        return {
            "success": True,
            "witch_id": witch_id,
            "target_id": target_id,
            "message": f"女巫使用解药救了 {self.get_agent_state(target_id).name}"
        }

    def witch_poison(self, witch_id: str, target_id: str) -> Dict[str, Any]:
        """
        Witch uses poison to kill a player.

        Args:
            witch_id: ID of the witch
            target_id: ID of the player to poison

        Returns:
            Result dict with success status
        """
        # Validate witch
        witch = self.get_agent_state(witch_id)
        if not witch or witch.role != WerewolfRole.WITCH or not witch.is_alive:
            raise ValueError(f"Invalid witch: {witch_id}")

        # Check if poison is available
        if not witch.witch_potions or not witch.witch_potions.poison:
            raise ValueError("Witch has already used poison")

        # Validate target
        target = self.get_agent_state(target_id)
        if not target or not target.is_alive:
            raise ValueError(f"Invalid target: {target_id}")

        # Use poison
        witch.witch_potions.poison = False

        # Record action
        self.record_night_action(
            witch_id,
            NightActionType.WITCH_POISON,
            target_id,
            result="poisoned"
        )

        logger.info(f"Witch {witch_id} poisons {target_id}")

        return {
            "success": True,
            "witch_id": witch_id,
            "target_id": target_id,
            "message": f"女巫使用毒药毒杀 {target.name}"
        }

    def guard_protect(self, guard_id: str, target_id: str) -> Dict[str, Any]:
        """
        Guard protects a player.

        Args:
            guard_id: ID of the guard
            target_id: ID of the player to protect

        Returns:
            Result dict with success status
        """
        # Validate guard
        guard = self.get_agent_state(guard_id)
        if not guard or guard.role != WerewolfRole.GUARD or not guard.is_alive:
            raise ValueError(f"Invalid guard: {guard_id}")

        # Validate target
        target = self.get_agent_state(target_id)
        if not target or not target.is_alive:
            raise ValueError(f"Invalid target: {target_id}")

        # Check if protecting same person as last night
        if guard.guard_last_protected == target_id:
            raise ValueError("Guard cannot protect the same person two nights in a row")

        # Update last protected
        guard.guard_last_protected = target_id

        # Record action
        self.record_night_action(
            guard_id,
            NightActionType.GUARD_PROTECT,
            target_id,
            result="protected"
        )

        logger.info(f"Guard {guard_id} protects {target_id}")

        return {
            "success": True,
            "guard_id": guard_id,
            "target_id": target_id,
            "message": f"守卫守护 {target.name}"
        }

    def resolve_night(self) -> Dict[str, Any]:
        """
        Resolve night actions and determine deaths.

        Returns:
            Dict with death information
        """
        deaths = []
        saved_by_witch = False
        saved_by_guard = False

        # Check if werewolf kill target was saved
        kill_target = self.state.werewolf_kill_target

        if kill_target:
            # Check guard protection
            guard_actions = [
                action for action in self.state.night_actions
                if action.action_type == NightActionType.GUARD_PROTECT
                and action.target_id == kill_target
                and action.round == self.state.current_round
            ]
            if guard_actions:
                saved_by_guard = True
                logger.info(f"Guard saved {kill_target} from werewolf kill")

            # Check witch save
            witch_save_actions = [
                action for action in self.state.night_actions
                if action.action_type == NightActionType.WITCH_SAVE
                and action.target_id == kill_target
                and action.round == self.state.current_round
            ]
            if witch_save_actions:
                saved_by_witch = True
                logger.info(f"Witch saved {kill_target} from werewolf kill")

            # If not saved, add to deaths
            if not saved_by_guard and not saved_by_witch:
                deaths.append(kill_target)

        # Check witch poison
        poison_actions = [
            action for action in self.state.night_actions
            if action.action_type == NightActionType.WITCH_POISON
            and action.round == self.state.current_round
        ]
        for action in poison_actions:
            if action.target_id and action.target_id not in deaths:
                deaths.append(action.target_id)

        # Update agent states
        for agent_id in deaths:
            agent = self.get_agent_state(agent_id)
            if agent:
                agent.is_alive = False
                logger.info(f"Agent {agent_id} ({agent.name}) died tonight")

        self.state.death_tonight = deaths

        return {
            "deaths": deaths,
            "death_count": len(deaths),
            "saved_by_witch": saved_by_witch,
            "saved_by_guard": saved_by_guard,
            "kill_target": kill_target
        }

    def start_day_phase(self) -> Dict[str, Any]:
        """
        Start day phase and announce deaths.

        Returns:
            Dict with death announcements
        """
        self.state.phase = WerewolfPhase.DAWN

        death_info = []
        for agent_id in self.state.death_tonight:
            agent = self.get_agent_state(agent_id)
            if agent:
                death_info.append({
                    "agent_id": agent_id,
                    "name": agent.name,
                    "role": self._enum_value(agent.role),
                    "role_cn": get_role_name_cn(agent.role)
                })

        # Add to conversation history
        if death_info:
            death_msg = "昨晚死亡：" + "、".join([f"{d['name']}({d['role_cn']})" for d in death_info])
        else:
            death_msg = "昨晚是平安夜，无人死亡"

        self.state.conversation_history.append({
            "round": self.state.current_round,
            "agent_id": "system",
            "type": "dawn",
            "content": death_msg
        })

        # Record event
        self._record_event(
            GameEventType.DEATH_ANNOUNCEMENT,
            {
                "deaths": death_info,
                "message": death_msg
            },
            include_snapshot=True
        )

        # Record phase change
        self._record_event(
            GameEventType.PHASE_CHANGE,
            {
                "from_phase": "night",
                "to_phase": WerewolfPhase.DAWN.value
            }
        )

        logger.info(f"Day phase started - {death_msg}")

        return {
            "phase": WerewolfPhase.DAWN.value,
            "deaths": death_info,
            "message": death_msg
        }

    def start_discussion_phase(self):
        """Start discussion phase."""
        self.state.phase = WerewolfPhase.DAY_DISCUSSION
        self.state.speakers_this_round = []

        # Record event
        self._record_event(
            GameEventType.PHASE_CHANGE,
            {
                "from_phase": WerewolfPhase.DAWN.value,
                "to_phase": WerewolfPhase.DAY_DISCUSSION.value
            }
        )

        logger.info("Discussion phase started")

    def _format_player_list(self, agents: List[WerewolfAgentState]) -> str:
        return "\n".join(
            f"- {agent.agent_id}: {agent.name}（{get_role_name_cn(agent.role) if not agent.is_alive else '存活玩家'}）"
            for agent in agents
        ) or "（无）"

    def _format_alive_players(self, exclude_ids: Optional[set[str]] = None) -> str:
        exclude_ids = exclude_ids or set()
        alive_agents = [
            agent for agent in self.get_alive_agents()
            if agent.agent_id not in exclude_ids
        ]
        return "\n".join(f"- {agent.agent_id}: {agent.name}" for agent in alive_agents) or "（无）"

    def _format_recent_discussion(self) -> str:
        messages = [
            msg for msg in self.state.conversation_history[-12:]
            if msg.get("type") in {"dawn", "discussion", "vote", "elimination"}
        ]
        if not messages:
            return "暂无发言。"

        lines: List[str] = []
        for msg in messages:
            agent_id = msg.get("agent_id")
            if agent_id == "system":
                speaker = "系统"
            else:
                speaker = msg.get("agent_name") or self.state.agents.get(agent_id).name
            lines.append(f"- {speaker}: {msg.get('content', '')}")
        return "\n".join(lines)

    def _format_game_situation(self) -> str:
        alive_werewolves = len(self.get_alive_werewolves())
        alive_good = len(self.get_alive_good_players())
        return (
            f"当前回合：第 {self.state.current_round} 回合\n"
            f"存活总人数：{len(self.get_alive_agents())}\n"
            f"狼人数量：{alive_werewolves}\n"
            f"好人数量：{alive_good}\n"
            f"最近讨论：\n{self._format_recent_discussion()}"
        )

    def _format_death_info(self) -> str:
        deaths = [
            self.get_agent_state(agent_id)
            for agent_id in self.state.death_tonight
        ]
        death_lines = [f"- {agent.name}（{get_role_name_cn(agent.role)}）" for agent in deaths if agent]
        return "\n".join(death_lines) if death_lines else "昨晚平安夜，无人死亡。"

    def _sanitize_suspicion_scores(
        self,
        suspicion: Dict[str, Any],
        speaker_id: str,
    ) -> Dict[str, int]:
        sanitized: Dict[str, int] = {}
        for candidate_id, score in (suspicion or {}).items():
            if candidate_id == speaker_id:
                continue
            if candidate_id not in self.state.agents:
                continue
            try:
                value = int(score)
            except (TypeError, ValueError):
                continue
            sanitized[candidate_id] = max(0, min(10, value))
        return sanitized

    @staticmethod
    def _build_iq_profile(iq_level: Optional[str]) -> str:
        normalized = (iq_level or "").lower()
        if normalized == "high":
            return "IQ 表达层次：允许多步推理和布局，但仍要像真人发言，不能像论文或审讯记录。"
        if normalized == "low":
            return "IQ 表达层次：判断更直觉、更朴素，少用抽象术语，不要硬装深谋远虑。"
        return "IQ 表达层次：有基本分析和推进意识，表达自然，不故作高深。"

    @staticmethod
    def _build_personality_profile(mbti_type: str, iq_level: Optional[str] = None) -> str:
        return (
            f"{PersonalityPrompt.get_distinctive_prompt(mbti_type)}\n"
            f"- {WerewolfService._build_iq_profile(iq_level)}"
        )

    def _build_character_style(self, agent_state: WerewolfAgentState) -> str:
        """公开发言的风格要求：MBTI 人设 + 作品角色味道（若阵容来自作品）。"""
        parts = []
        if self.roster_work:
            parts.append(
                f"你的角色「{agent_state.name}」来自作品《{self.roster_work}》："
                f"发言的语气、口头禅或打比方的方式可以贴合大众对这个角色的印象"
                f"（绰号、经典台词风格、行事做派均可），让旁观者一读就觉得“像他”；"
                f"但局势判断必须基于本场信息，不能把原著情节当成对局事实。"
            )
        parts.append(
            "发言必须明显体现你的 MBTI 性格与 IQ 层次：强势的人带队施压、"
            "细腻的人犹豫观察、理性的人讲逻辑链、感性的人先讲感受；"
            "同一局里你的语气要保持稳定，不能每句话像换了一个灵魂。"
        )
        parts.append("严禁在发言中使用任何 emoji 表情或颜文字。")
        return "\n".join(f"- {p}" for p in parts)

    @staticmethod
    def _build_private_knowledge_rules(agent_state: WerewolfAgentState) -> str:
        role_name = get_role_name_cn(agent_state.role)
        base_rules = [
            "- `thought` 是你的私密内心独白，不是演戏台词，必须完全服从你的真实角色与真实已知信息。",
            "- 公开发言可以伪装、可以误导，但 `thought` 绝不能把自己写成另一个身份。",
            "- 不允许编造自己并未掌握的夜间信息、查验结果、药水状态、守护结果或狼队内部信息。",
            f"- 你现在的真实角色固定为 {role_name}，所有判断都必须从这个身份出发。",
            "- 先想“我这个身份此刻真实知道什么”，再写 thought；不知道的内容宁可怀疑，也不能写成确定事实。",
        ]

        if agent_state.role == WerewolfRole.WEREWOLF:
            base_rules.extend(
                [
                    "- 你可以在 `thought` 中提到狼人同伴、狼队策略、伪装计划。",
                    "- 但你不能在 `thought` 中把自己写成预言家、女巫、守卫、猎人或村民本人。",
                    "- 你可以说“我的狼人同伴”“只剩几狼”，因为这确实是你的私密知识。",
                    "- 但即使是狼人，也不能把未发生的查验/守护/用药结果写成既成事实。",
                ]
            )
        else:
            base_rules.extend(
                [
                    "- 你是好人阵营，`thought` 中绝不能出现“我是狼人 / 作为狼人 / 狼人同伴 / 狼队策略 / 保护狼队”之类内容。",
                    "- 你不能把任何玩家写成“我的狼人同伴”或“我的队友”。",
                    "- 你可以怀疑某人像狼、像神职，但不能写成“我知道某两人是狼人同伴”“狼队只剩两人”这类越权结论。",
                    "- 你不能把对狼人的推测写成确定事实，尤其不能写“某人作为狼人同伴在引导”“狼队昨晚选择了谁”“这是狼队合理策略”“某人在保护狼队利益”。",
                    "- 下面这些都属于错误示例：'诸葛亮和孙悟空是狼人同伴'、'只剩我和提利昂两个狼人'、'狼队想保谁'、'诸葛亮作为狼人同伴在引导注意力'、'狼队昨晚杀预言家是合理策略'。",
                ]
            )

        if agent_state.role == WerewolfRole.SEER:
            base_rules.extend(
                [
                    "- 你只能引用自己真实查验过的结果，不能临时捏造新的验人结论。",
                    "- 你可以说“我验过某人是狼人/好人”，但不能顺带知道狼队的同伴结构。",
                ]
            )
        elif agent_state.role == WerewolfRole.WITCH:
            base_rules.extend(
                [
                    "- 你只能根据真实药水剩余情况和今晚刀口信息做判断，不能虚构额外夜间情报。",
                    "- 你可以判断“今晚该不该救/毒”，但不能因此突然知道谁是狼人同伴。",
                ]
            )
        elif agent_state.role == WerewolfRole.GUARD:
            base_rules.extend(
                [
                    "- 你只能依据真实守护历史思考，不能伪造查验、毒药或狼队视角。",
                    "- 你可以说“我昨晚守了谁、我怀疑平安夜可能与守护有关”，但不能说“某两人是狼人同伴”。",
                ]
            )
        elif agent_state.role == WerewolfRole.HUNTER:
            base_rules.extend(
                [
                    "- 你只能从猎人的公开局势理解出发思考，不能凭空拥有预言家或狼人视角。",
                    "- 你可以基于投票和发言怀疑别人，但不能知道狼队内部结构。",
                ]
            )
        elif agent_state.role == WerewolfRole.VILLAGER:
            base_rules.extend(
                [
                    "- 你只有白天公开信息和个人观察，不能突然拥有神职或狼人私密信息。",
                    "- 你可以说“我感觉谁像狼”，不能说“我知道谁和谁是狼队”。",
                ]
            )

        return "\n".join(base_rules)

    @staticmethod
    def _build_night_persona_brief(agent_state: WerewolfAgentState) -> str:
        mbti = agent_state.mbti_type or "ISFJ"
        iq = agent_state.iq_level or "Mid"
        energy = "外放施压" if mbti.startswith("E") else "内敛审视"
        intuition = "偏看全局模式" if mbti[1:2] == "N" else "偏看现场细节"
        judgment = "先讲逻辑取舍" if mbti[2:3] == "T" else "先看人物状态"
        style = "计划性强" if mbti[3:4] == "J" else "临场应变快"
        iq_style = {
            "High": "可做两步以上推理，但表达仍像真人。",
            "Low": "判断更直觉朴素，不硬装深谋远虑。",
        }.get(iq, "推理清楚直接，不故作高深。")
        return f"{energy}，{intuition}，{judgment}，{style}。{iq_style}"

    def _build_night_private_brief(self, agent_state: WerewolfAgentState) -> str:
        if agent_state.role == WerewolfRole.WEREWOLF:
            teammates = [
                teammate.name
                for teammate in self.get_alive_werewolves()
                if teammate.agent_id != agent_state.agent_id
            ]
            teammate_text = "、".join(teammates) or "暂无"
            return f"你是狼人，可知道存活狼同伴：{teammate_text}。但不能伪造未发生的查验、守护、用药结果。"

        role_specific = {
            WerewolfRole.SEER: "你只能使用自己真实查验过的信息，不能捏造新的验人结果或狼队结构。",
            WerewolfRole.WITCH: "你只能依据真实刀口与真实药水剩余做判断，不能突然知道狼队内部信息。",
            WerewolfRole.GUARD: "你只能依据真实守护历史思考，不能伪造查验、毒药或狼队视角。",
            WerewolfRole.HUNTER: "你只有公开局势和个人判断，不能拥有预言家或狼队私密信息。",
            WerewolfRole.VILLAGER: "你只有公开信息和个人观察，不能写出神职或狼队私密信息。",
        }
        return role_specific.get(
            agent_state.role,
            "只能依据你的真实身份与真实已知信息思考，不能越权获得夜间私密信息。",
        )

    def _build_night_table_summary(self) -> str:
        alive_agents = self.get_alive_agents()
        alive_text = "、".join(f"{agent.name}({agent.agent_id})" for agent in alive_agents[:9]) or "无"
        return f"第{self.state.current_round}轮，存活玩家：{alive_text}。"

    @staticmethod
    def _sanitize_role_consistent_thought(agent_state: WerewolfAgentState, thought: Any) -> str:
        text = (thought or "").strip()
        if not text:
            return ""

        role_guards = {
            WerewolfRole.WEREWOLF: ["作为狼人", "我是狼人", "狼人同伴", "狼人队友"],
            WerewolfRole.SEER: ["作为预言家", "我是预言家"],
            WerewolfRole.WITCH: ["作为女巫", "我是女巫"],
            WerewolfRole.GUARD: ["作为守卫", "我是守卫"],
            WerewolfRole.HUNTER: ["作为猎人", "我是猎人"],
            WerewolfRole.VILLAGER: ["作为村民", "我是村民"],
        }
        conflicting_markers = []
        for role, markers in role_guards.items():
            if role == agent_state.role:
                continue
            conflicting_markers.extend(markers)

        if agent_state.role != WerewolfRole.WEREWOLF:
            conflicting_markers.extend([
                "狼人同伴",
                "狼人队友",
                "狼队同伴",
                "狼队队友",
                "狼队策略",
                "保护狼队",
                "狼队只剩",
                "只剩我和",
                "我的狼人同伴",
                "我是狼",
                "作为狼",
                "作为狼人同伴",
                "狼队昨晚",
                "狼队杀",
                "狼队合理策略",
                "对狼队有利",
                "保护狼队利益",
                "符合狼队策略",
                "这对狼队有利",
            ])

        if any(marker in text for marker in conflicting_markers):
            logger.warning(
                "Role-inconsistent thought detected for %s (%s): %s",
                agent_state.name,
                agent_state.role,
                text,
            )
            return "我需要继续根据自己的真实身份与公开信息谨慎判断局势。"
        return text

    async def _generate_json_decision(
        self,
        agent_id: str,
        prompt: str,
        *,
        system_prompt: Optional[str] = None,
        max_tokens: int = 480,
    ) -> Dict[str, Any]:
        agent = self.agents[agent_id]
        attempts = [
            {
                "prompt": prompt,
                "system_prompt": system_prompt or "你是狼人杀游戏中的决策助手。只返回一行合法 JSON。",
                "json_mode": False,
            },
            {
                "prompt": (
                    f"{prompt}\n\n再强调一次：必须返回完整 JSON 对象，且至少包含 thought、vote、confidence"
                    " 三个字段。即使犹豫，也必须填完字段，只输出 JSON 本身。"
                ),
                "system_prompt": (
                    f"{system_prompt}\n\n只返回一行完整 JSON，禁止任何额外文本。"
                    if system_prompt
                    else "只返回一行完整 JSON，禁止任何额外文本。"
                ),
                "json_mode": False,
            },
            {
                "prompt": prompt,
                "system_prompt": (
                    f"{system_prompt}\n\n你是狼人杀游戏中的决策助手。严格输出 JSON，不要解释。"
                    if system_prompt
                    else "你是狼人杀游戏中的决策助手。严格输出 JSON，不要解释。"
                ),
                "json_mode": True,
            },
        ]

        last_content = ""
        for attempt in attempts:
            content = await agent.llm_service.generate(
                prompt=attempt["prompt"],
                temperature=0.2,
                max_tokens=max_tokens,
                model_config=agent.model_config,
                system_prompt=attempt["system_prompt"],
                json_mode=attempt["json_mode"],
            )
            last_content = content or ""
            data = agent.llm_service._extract_json_from_text(last_content)
            if data is not None:
                return data

        raise ValueError(f"Could not parse JSON decision: {last_content[:200]}")

    @staticmethod
    def _normalize_choice_token(value: Any) -> str:
        text = str(value or "").strip().lower()
        return "".join(ch for ch in text if ch.isalnum() or ch in {"_", "-"})

    @classmethod
    def _resolve_structured_choice(
        cls,
        raw_value: Any,
        valid_ids: List[str],
        aliases: Optional[Dict[str, List[str]]] = None,
    ) -> Optional[str]:
        text = str(raw_value or "").strip()
        if not text:
            return None

        if text in valid_ids:
            return text

        normalized_text = cls._normalize_choice_token(text)
        alias_map = aliases or {}

        for valid_id in valid_ids:
            candidate_tokens = [valid_id, *alias_map.get(valid_id, [])]
            for candidate in candidate_tokens:
                if not candidate:
                    continue
                if text == candidate:
                    return valid_id
                normalized_candidate = cls._normalize_choice_token(candidate)
                if normalized_candidate and normalized_text == normalized_candidate:
                    return valid_id

        for valid_id in valid_ids:
            if valid_id and valid_id in text:
                return valid_id

        for valid_id in valid_ids:
            candidate_tokens = alias_map.get(valid_id, [])
            for candidate in candidate_tokens:
                normalized_candidate = cls._normalize_choice_token(candidate)
                if normalized_candidate and normalized_candidate in normalized_text:
                    return valid_id

        return None

    @staticmethod
    def _normalize_confidence(value: Any, default: float = 0.5) -> float:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return default
        return max(0.0, min(1.0, numeric))

    def _summarize_recent_public_history(self, limit: int = 8) -> str:
        recent_messages = [
            msg for msg in self.state.conversation_history[-limit:]
            if msg.get("type") in {"discussion", "vote"}
        ]
        if not recent_messages:
            return "暂无公开发言"

        lines = []
        for msg in recent_messages:
            speaker_name = msg.get("speaker_name") or msg.get("speaker_id") or "未知玩家"
            content = str(msg.get("content") or "").strip()
            if not content:
                continue
            lines.append(f"- {speaker_name}: {content}")
        return "\n".join(lines) or "暂无公开发言"

    async def _choose_target_via_vote_schema(
        self,
        chooser_id: str,
        valid_targets: List[WerewolfAgentState],
        *,
        action_name: str,
        action_summary: str,
        extra_context: str = "",
        temperature: float = 0.4,
    ) -> Dict[str, Any]:
        """Reuse the stable vote schema to pick a night target."""
        chooser_state = self.get_agent_state(chooser_id)
        if chooser_state is None:
            raise ValueError(f"Invalid chooser: {chooser_id}")

        valid_agent_ids = [target.agent_id for target in valid_targets]
        if not valid_agent_ids:
            raise ValueError(f"No valid targets for {action_name}")

        chooser_agent = self.agents[chooser_id]
        role_name = get_role_name_cn(chooser_state.role)
        target_text = "\n".join(
            f"- {target.agent_id}: {target.name}"
            for target in valid_targets
        ) or "（无）"
        memory_context = chooser_agent.memory_system.get_conversation_context(self.state.current_round)
        public_history = self._summarize_recent_public_history()
        system_prompt = prompt_registry.render("werewolf_night_prompt", {
            "chooser_name": chooser_state.name,
            "chooser_id": chooser_state.agent_id,
            "role_name": role_name,
            "mbti_type": chooser_state.mbti_type,
            "iq_level": chooser_state.iq_level,
            "persona_brief": self._build_night_persona_brief(chooser_state),
            "action_name": action_name,
            "action_summary": action_summary,
            "extra_context": extra_context or "暂无",
            "table_summary": self._build_night_table_summary(),
            "candidates_label": "候选目标",
            "candidates_text": target_text,
            "memory_context": memory_context or "暂无",
            "public_history": public_history,
            "private_brief": self._build_night_private_brief(chooser_state),
            "vote_target_label": "玩家ID",
        })
        decision = await self._generate_json_decision(
            chooser_id,
            f"请立即完成“{action_name}”决策，只能从候选目标中选择，并严格按 JSON 返回。",
            system_prompt=system_prompt,
            max_tokens=900,
        )
        aliases = {
            target.agent_id: [target.name]
            for target in valid_targets
        }
        resolved_target = self._resolve_structured_choice(
            decision.get("vote") or decision.get("target_id"),
            valid_agent_ids,
            aliases=aliases,
        )
        if resolved_target is None:
            raise ValueError(
                f"Invalid {action_name} target: {decision.get('vote') or decision.get('target_id')}"
            )
        thought = self._sanitize_role_consistent_thought(chooser_state, decision.get("thought"))
        confidence = self._normalize_confidence(decision.get("confidence"), default=temperature)
        chooser_agent.memory_system.add_memory(
            f"夜晚决策：{action_name} 选择了 {resolved_target}，置信度 {confidence}",
            self.state.current_round,
        )
        return {
            "target_id": resolved_target,
            "thought": thought,
            "confidence": confidence,
            "used_llm": True,
        }

    async def _choose_option_via_vote_schema(
        self,
        chooser_id: str,
        *,
        action_name: str,
        action_summary: str,
        options: Dict[str, str],
        extra_context: str = "",
        temperature: float = 0.3,
    ) -> Dict[str, Any]:
        """Reuse the vote schema for arbitrary structured night choices."""
        chooser_state = self.get_agent_state(chooser_id)
        if chooser_state is None:
            raise ValueError(f"Invalid chooser: {chooser_id}")

        valid_option_ids = list(options.keys())
        if not valid_option_ids:
            raise ValueError(f"No valid options for {action_name}")

        chooser_agent = self.agents[chooser_id]
        role_name = get_role_name_cn(chooser_state.role)
        option_text = "\n".join(
            f"- {option_id}: {label}"
            for option_id, label in options.items()
        ) or "（无）"
        memory_context = chooser_agent.memory_system.get_conversation_context(self.state.current_round)
        public_history = self._summarize_recent_public_history()
        system_prompt = prompt_registry.render("werewolf_night_prompt", {
            "chooser_name": chooser_state.name,
            "chooser_id": chooser_state.agent_id,
            "role_name": role_name,
            "mbti_type": chooser_state.mbti_type,
            "iq_level": chooser_state.iq_level,
            "persona_brief": self._build_night_persona_brief(chooser_state),
            "action_name": action_name,
            "action_summary": action_summary,
            "extra_context": extra_context or "暂无",
            "table_summary": self._build_night_table_summary(),
            "candidates_label": "可选项",
            "candidates_text": option_text,
            "memory_context": memory_context or "暂无",
            "public_history": public_history,
            "private_brief": self._build_night_private_brief(chooser_state),
            "vote_target_label": "可选项ID",
        })
        aliases: Dict[str, List[str]] = {}
        for option_id, label in options.items():
            alias_tokens = [label]
            if option_id not in {"save", "skip"} and option_id in self.state.agents:
                alias_tokens.append(self.state.agents[option_id].name)
            aliases[option_id] = alias_tokens

        decision = await self._generate_json_decision(
            chooser_id,
            f"请立即完成“{action_name}”决策，只能从可选项里选择，并严格按 JSON 返回。",
            system_prompt=system_prompt,
            max_tokens=900,
        )
        resolved_choice = self._resolve_structured_choice(
            decision.get("vote") or decision.get("choice"),
            valid_option_ids,
            aliases=aliases,
        )
        if resolved_choice is None:
            raise ValueError(
                f"Invalid {action_name} option: {decision.get('vote') or decision.get('choice')}"
            )
        thought = self._sanitize_role_consistent_thought(chooser_state, decision.get("thought"))
        confidence = self._normalize_confidence(decision.get("confidence"), default=temperature)
        chooser_agent.memory_system.add_memory(
            f"夜晚决策：{action_name} 选择了 {resolved_choice}，置信度 {confidence}",
            self.state.current_round,
        )
        return {
            "choice": resolved_choice,
            "thought": thought,
            "confidence": confidence,
            "used_llm": True,
        }

    async def decide_werewolf_kill(self) -> Dict[str, Any]:
        """Use LLM to decide the werewolf kill target."""
        alive_werewolves = self.get_alive_werewolves()
        if not alive_werewolves:
            return {"used_llm": False, "reason": "no_alive_werewolves"}

        candidates = self.get_alive_good_players()
        if not candidates:
            return {"used_llm": False, "reason": "no_good_targets"}

        werewolf = alive_werewolves[0]
        teammates = "、".join(agent.name for agent in alive_werewolves if agent.agent_id != werewolf.agent_id) or "暂无"
        extra_context = (
            f"- 狼人同伴：{teammates}\n"
            "- 目标必须是好人阵营存活玩家。\n"
            "- 优先考虑对狼队威胁更大的神职或带队玩家。"
        )

        try:
            decision = await self._choose_target_via_vote_schema(
                werewolf.agent_id,
                candidates,
                action_name="狼人夜间淘汰",
                action_summary="你需要从候选人中选出今晚要集火淘汰的一名目标。",
                extra_context=extra_context,
                temperature=0.3,
            )
            target_id = decision["target_id"]
            result = self.werewolf_kill(werewolf.agent_id, target_id)
            return {
                **result,
                "used_llm": decision.get("used_llm", True),
                "thought": decision.get("thought", ""),
                "reason": decision.get("thought", ""),
                "confidence": decision.get("confidence", 0.5),
            }
        except Exception as exc:
            logger.warning("Werewolf LLM decision failed, falling back to random target: %s", exc)
            target = random.choice(candidates)
            result = self.werewolf_kill(werewolf.agent_id, target.agent_id)
            return {**result, "used_llm": False, "fallback_reason": str(exc)}

    async def decide_seer_check(self) -> Dict[str, Any]:
        """Use LLM to decide the seer check target."""
        seer_agents = [
            agent for agent in self.state.agents.values()
            if agent.is_alive and agent.role == WerewolfRole.SEER
        ]
        if not seer_agents:
            return {"used_llm": False, "reason": "no_alive_seer"}

        seer = seer_agents[0]
        candidates = [
            agent for agent in self.get_alive_agents()
            if agent.agent_id != seer.agent_id and agent.agent_id not in seer.seer_checked_ids
        ]
        if not candidates:
            return {"used_llm": False, "reason": "no_seer_targets"}

        checked_results = "\n".join(
            f"- {self.state.agents[target_id].name}({target_id}): {'狼人' if faction == WerewolfFaction.WEREWOLF else '好人'}"
            for target_id, faction in seer.seer_check_results.items()
            if target_id in self.state.agents
        ) or "暂无已知结果"
        extra_context = (
            f"- 已查验结果：\n{checked_results}\n"
            "- 不能查验自己，也不能重复查验已经验过的玩家。\n"
            "- 优先查验最能帮助白天推进的信息位。"
        )

        try:
            decision = await self._choose_target_via_vote_schema(
                seer.agent_id,
                candidates,
                action_name="预言家夜间查验",
                action_summary="你需要选择今晚要查验的一名玩家，获取其阵营信息。",
                extra_context=extra_context,
                temperature=0.25,
            )
            target_id = decision["target_id"]
            result = self.seer_check(seer.agent_id, target_id)
            return {
                **result,
                "used_llm": decision.get("used_llm", True),
                "thought": decision.get("thought", ""),
                "reason": decision.get("thought", ""),
                "confidence": decision.get("confidence", 0.5),
            }
        except Exception as exc:
            logger.warning("Seer LLM decision failed, falling back to random target: %s", exc)
            target = random.choice(candidates)
            result = self.seer_check(seer.agent_id, target.agent_id)
            return {**result, "used_llm": False, "fallback_reason": str(exc)}

    async def decide_witch_action(self) -> Dict[str, Any]:
        """Use LLM to decide whether the witch saves and/or poisons."""
        witch_agents = [
            agent for agent in self.state.agents.values()
            if agent.is_alive and agent.role == WerewolfRole.WITCH and agent.witch_potions
        ]
        if not witch_agents:
            return {"used_llm": False, "reason": "no_alive_witch"}

        witch = witch_agents[0]
        decisions: Dict[str, Any] = {"used_llm": False}
        kill_target_id = self.state.werewolf_kill_target
        kill_target = self.get_agent_state(kill_target_id) if kill_target_id else None

        if witch.witch_potions.antidote and kill_target:
            try:
                decision = await self._choose_option_via_vote_schema(
                    witch.agent_id,
                    action_name="女巫是否使用解药",
                    action_summary="你需要决定今晚是否使用解药救下被狼人击杀的玩家。",
                    options={
                        "save": f"使用解药，救 {kill_target.name}({kill_target.agent_id})",
                        "skip": "不使用解药，选择观望",
                    },
                    extra_context=(
                        f"- 今晚被刀的人：{kill_target.name}({kill_target.agent_id})\n"
                        f"- 解药：可用\n- 毒药：{'可用' if witch.witch_potions.poison else '不可用'}"
                    ),
                    temperature=0.2,
                )
                decisions["save_decision"] = decision
                decisions["used_llm"] = decisions["used_llm"] or decision.get("used_llm", False)
                if decision["choice"] == "save":
                    decisions["save_result"] = self.witch_save(witch.agent_id, kill_target.agent_id)
            except Exception as exc:
                logger.warning("Witch save decision failed: %s", exc)
                decisions["save_error"] = str(exc)

        if witch.witch_potions.poison:
            candidates = [
                agent for agent in self.get_alive_agents()
                if agent.agent_id != witch.agent_id and agent.agent_id != kill_target_id
            ]
            if candidates:
                try:
                    options = {"skip": "不使用毒药，选择观望"}
                    options.update({
                        agent.agent_id: f"使用毒药毒杀 {agent.name}({agent.agent_id})"
                        for agent in candidates
                    })
                    decision = await self._choose_option_via_vote_schema(
                        witch.agent_id,
                        action_name="女巫是否使用毒药",
                        action_summary="你需要决定今晚是否使用毒药，以及如果使用，要毒杀哪名玩家。",
                        options=options,
                        extra_context=(
                            f"- 解药：{'可用' if witch.witch_potions.antidote else '已用'}\n"
                            "- 毒药：可用\n"
                            "- 如果信息不足，可以选择 skip。"
                        ),
                        temperature=0.25,
                    )
                    decisions["poison_decision"] = decision
                    decisions["used_llm"] = decisions["used_llm"] or decision.get("used_llm", False)
                    if decision["choice"] != "skip":
                        decisions["poison_result"] = self.witch_poison(witch.agent_id, decision["choice"])
                except Exception as exc:
                    logger.warning("Witch poison decision failed: %s", exc)
                    decisions["poison_error"] = str(exc)

        return decisions

    async def decide_guard_protect(self) -> Dict[str, Any]:
        """Use LLM to decide the guard protection target."""
        guard_agents = [
            agent for agent in self.state.agents.values()
            if agent.is_alive and agent.role == WerewolfRole.GUARD
        ]
        if not guard_agents:
            return {"used_llm": False, "reason": "no_alive_guard"}

        guard = guard_agents[0]
        candidates = [
            agent for agent in self.get_alive_agents()
            if agent.agent_id != guard.guard_last_protected
        ]
        if not candidates:
            return {"used_llm": False, "reason": "no_guard_targets"}

        extra_context = (
            f"- 上一晚守护：{guard.guard_last_protected or '无'}\n"
            "- 不能连续两晚守护同一名玩家。\n"
            "- 优先保护你认为更可能是神职、带队位、或狼人夜里更想处理的人。"
        )

        try:
            decision = await self._choose_target_via_vote_schema(
                guard.agent_id,
                candidates,
                action_name="守卫夜间守护",
                action_summary="你需要选择今晚要守护的一名玩家，使其免受狼人击杀。",
                extra_context=extra_context,
                temperature=0.25,
            )
            target_id = decision["target_id"]
            result = self.guard_protect(guard.agent_id, target_id)
            return {
                **result,
                "used_llm": decision.get("used_llm", True),
                "thought": decision.get("thought", ""),
                "reason": decision.get("thought", ""),
                "confidence": decision.get("confidence", 0.5),
            }
        except Exception as exc:
            logger.warning("Guard vote-schema decision failed, falling back to random target: %s", exc)
            target = random.choice(candidates)
            result = self.guard_protect(guard.agent_id, target.agent_id)
            return {**result, "used_llm": False, "fallback_reason": str(exc)}

    def _build_discussion_prompt(self, agent_state: WerewolfAgentState) -> str:
        """渲染完整讨论提示词（兼容旧调用：静态 + 动态拼回）。"""
        static_text, dynamic_text = self._build_discussion_prompt_parts(agent_state)
        return f"{static_text}\n\n{dynamic_text}".strip()

    def _build_discussion_prompt_parts(self, agent_state: WerewolfAgentState) -> tuple:
        """缓存友好拆分：(每局稳定前缀, 本轮局势简报)。"""
        role_name = get_role_name_cn(agent_state.role)
        teammates = [
            teammate for teammate in self.get_alive_werewolves()
            if teammate.agent_id != agent_state.agent_id
        ]
        teammate_text = "、".join(teammate.name for teammate in teammates) or "暂无"
        seer_results = "暂无"
        if agent_state.role == WerewolfRole.SEER and agent_state.seer_check_results:
            seer_results = "\n".join(
                f"- {self.state.agents[target_id].name}: {'狼人' if faction == WerewolfFaction.WEREWOLF else '好人'}"
                for target_id, faction in agent_state.seer_check_results.items()
                if target_id in self.state.agents
            )

        return prompt_registry.render_split("werewolf_discussion_prompt", {
            "agent_id": agent_state.agent_id,
            "agent_name": agent_state.name,
            "role_name": role_name,
            "mbti_type": agent_state.mbti_type,
            "iq_level": agent_state.iq_level,
            "personality_profile": self._build_personality_profile(agent_state.mbti_type, agent_state.iq_level),
            "character_style": self._build_character_style(agent_state),
            "teammate_text": teammate_text,
            "seer_results": seer_results,
            "death_info": self._format_death_info(),
            "alive_players": self._format_alive_players(),
            "recent_discussion": self._format_recent_discussion(),
            "private_rules": self._build_private_knowledge_rules(agent_state),
        })

    def _build_opening_prompt(self, agent_state: WerewolfAgentState) -> str:
        return prompt_registry.render("werewolf_opening_prompt", {
            "agent_id": agent_state.agent_id,
            "agent_name": agent_state.name,
            "role_name": get_role_name_cn(agent_state.role),
            "mbti_type": agent_state.mbti_type,
            "iq_level": agent_state.iq_level,
            "personality_profile": self._build_personality_profile(agent_state.mbti_type, agent_state.iq_level),
            "character_style": self._build_character_style(agent_state),
            "alive_players": self._format_alive_players(),
            "private_rules": self._build_private_knowledge_rules(agent_state),
        })

    def _build_chat_prompt(self, agent_state: WerewolfAgentState) -> str:
        """渲染完整群聊提示词（兼容旧调用：静态 + 动态拼回）。"""
        static_text, dynamic_text = self._build_chat_prompt_parts(agent_state)
        return f"{static_text}\n\n{dynamic_text}".strip()

    def _build_chat_prompt_parts(self, agent_state: WerewolfAgentState) -> tuple:
        """缓存友好拆分：(每局稳定前缀, 本轮局势简报)。"""
        role_name = get_role_name_cn(agent_state.role)
        teammates = [
            teammate for teammate in self.get_alive_werewolves()
            if teammate.agent_id != agent_state.agent_id
        ]
        teammate_text = "、".join(teammate.name for teammate in teammates) or "暂无"
        seer_results = "暂无"
        if agent_state.role == WerewolfRole.SEER and agent_state.seer_check_results:
            seer_results = "\n".join(
                f"- {self.state.agents[target_id].name}: {'狼人' if faction == WerewolfFaction.WEREWOLF else '好人'}"
                for target_id, faction in agent_state.seer_check_results.items()
                if target_id in self.state.agents
            )

        return prompt_registry.render_split("werewolf_chat_prompt", {
            "agent_id": agent_state.agent_id,
            "agent_name": agent_state.name,
            "role_name": role_name,
            "mbti_type": agent_state.mbti_type,
            "iq_level": agent_state.iq_level,
            "personality_profile": self._build_personality_profile(agent_state.mbti_type, agent_state.iq_level),
            "character_style": self._build_character_style(agent_state),
            "teammate_text": teammate_text,
            "seer_results": seer_results,
            "death_info": self._format_death_info(),
            "alive_players": self._format_alive_players(),
            "recent_discussion": self._format_recent_discussion(),
            "private_rules": self._build_private_knowledge_rules(agent_state),
        })

    def _build_voting_prompt(self, agent_state: WerewolfAgentState, valid_agent_ids: List[str]) -> str:
        """渲染完整投票提示词（兼容旧调用：静态 + 动态拼回）。"""
        static_text, dynamic_text = self._build_voting_prompt_parts(agent_state, valid_agent_ids)
        return f"{static_text}\n\n{dynamic_text}".strip()

    def _build_voting_prompt_parts(self, agent_state: WerewolfAgentState, valid_agent_ids: List[str]) -> tuple:
        """缓存友好拆分：(每局稳定前缀, 本轮投票简报)。"""
        role_name = get_role_name_cn(agent_state.role)
        suspicion_scores = self.agents[agent_state.agent_id].suspicion_scores
        suspicion_text = "\n".join(
            f"- {self.state.agents[target_id].name}({target_id}): {score}"
            for target_id, score in suspicion_scores.items()
            if target_id in self.state.agents
        ) or "暂无明确怀疑。"
        votable_players = "\n".join(
            f"- {target_id}: {self.state.agents[target_id].name}"
            for target_id in valid_agent_ids
            if target_id in self.state.agents
        ) or "（无）"

        return prompt_registry.render_split("werewolf_voting_prompt", {
            "agent_id": agent_state.agent_id,
            "agent_name": agent_state.name,
            "role_name": role_name,
            "mbti_type": agent_state.mbti_type,
            "iq_level": agent_state.iq_level,
            "personality_profile": self._build_personality_profile(agent_state.mbti_type, agent_state.iq_level),
            "character_style": self._build_character_style(agent_state),
            "recent_discussion": self._format_recent_discussion(),
            "votable_players": votable_players,
            "suspicion_text": suspicion_text,
            "private_rules": self._build_private_knowledge_rules(agent_state),
        })

    def _normalize_name_references(self, text: str) -> str:
        """兜底清洗：把模型回复中漏网的玩家 ID（werewolf_agent_6 / agent_2）
        与座位号（6号）替换成对应角色名，保证对局文本里不出现编码名。"""
        if not text:
            return text

        import re as _re

        id_to_name = {
            agent_id: (state.name or agent_id)
            for agent_id, state in self.state.agents.items()
        }
        if not id_to_name:
            return text

        def _replace_id(match: "_re.Match") -> str:
            token = match.group(0)
            if token in id_to_name:
                return id_to_name[token]
            # agent_4 ↔ werewolf_agent_4 双向补全
            alt = (
                f"werewolf_{token}" if not token.startswith("werewolf_")
                else token.replace("werewolf_", "", 1)
            )
            return id_to_name.get(alt, token)

        def _replace_seat(match: "_re.Match") -> str:
            n = int(match.group(1))
            return id_to_name.get(f"werewolf_agent_{n}", match.group(0))

        text = _re.sub(r"(?:werewolf_)?agent_\d+", _replace_id, text)
        # 座位号称呼（4号、6号…），排除「号位/号房」等复合名词
        text = _re.sub(r"(\d{1,2})\s*号(?![位房间屋])", _replace_seat, text)
        return text

    def submit_player_speech(self, agent_id: str, content: str) -> Dict[str, Any]:
        """夺席模式：玩家为被接管的 agent 提交公开发言（在下一轮该 agent
        发言时由事件流消费，替代 LLM 生成）。"""
        agent_state = self.get_agent_state(agent_id)
        if not agent_state or not agent_state.is_alive:
            raise ValueError(f"Invalid speaker: {agent_id}")
        text = (content or "").strip()
        if not text:
            raise ValueError("发言内容不能为空")
        if len(text) > 500:
            text = text[:500]
        self.pending_player_speeches[agent_id] = text
        return {"success": True, "agent_id": agent_id, "queued": True}

    def consume_player_speech(self, agent_id: str) -> Optional[str]:
        """取走（若有）玩家为该 agent 预先提交的发言。"""
        return self.pending_player_speeches.pop(agent_id, None)

    def is_player_agent(self, agent_id: str) -> bool:
        """该席位是否由真人玩家接管（参与模式）。"""
        return self.player_mode == "participate" and agent_id == self.player_agent_id

    async def wait_for_player_speech(self, agent_id: str, timeout: float = 240.0) -> Optional[str]:
        """等待玩家为该席位提交公开发言；超时返回 None（由事件流回退 LLM）。"""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while loop.time() < deadline:
            text = self.pending_player_speeches.pop(agent_id, None)
            if text is not None:
                return text
            await asyncio.sleep(0.5)
        return None

    async def wait_for_player_vote(self, agent_id: str, timeout: float = 240.0) -> bool:
        """等待玩家通过 /vote 为该席位提交投票；返回是否在超时前完成。"""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while loop.time() < deadline:
            if agent_id in self.state.votes_this_round:
                return True
            await asyncio.sleep(0.5)
        return False

    async def run_opening_turn(self, agent_id: str) -> Dict[str, Any]:
        """Generate one opening speech (game start, before the first night)."""
        agent_state = self.get_agent_state(agent_id)
        if not agent_state or not agent_state.is_alive:
            raise ValueError(f"Invalid speaker: {agent_id}")

        agent = self.agents[agent_id]
        response = await agent.generate_description(
            system_prompt=self._build_opening_prompt(agent_state),
            conversation_history=self.state.conversation_history[-12:],
            current_round=self.state.current_round,
        )
        speech = (response.get("speech") or "").strip() or f"{agent_state.name} 已入座。"
        speech = self._normalize_name_references(speech)
        thought = self._sanitize_role_consistent_thought(agent_state, response.get("thought", ""))
        suspicion = self._sanitize_suspicion_scores(
            response.get("suspicion", {}),
            speaker_id=agent_id,
        )

        message = {
            "round": self.state.current_round,
            "agent_id": agent_id,
            "agent_name": agent_state.name,
            "type": "opening",
            "content": speech,
            "thought": thought,
            "suspicion": suspicion,
        }
        self.state.conversation_history.append(message)

        self._record_event(
            GameEventType.DISCUSSION,
            {
                "agent_id": agent_id,
                "agent_name": agent_state.name,
                "speech": speech,
                "thought": thought,
                "suspicion": suspicion,
                "stage": "opening",
            },
        )
        return message

    async def run_discussion_turn(
        self, agent_id: str, override_content: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate one discussion turn using the agent's LLM.

        override_content: 夺席模式下玩家代打的发言文本；提供时跳过 LLM，
        直接以该文本作为本回合公开发言。
        群聊模式（chat_style=group_chat）下由 LLM 生成多条短消息气泡。
        """
        agent_state = self.get_agent_state(agent_id)
        if not agent_state or not agent_state.is_alive:
            raise ValueError(f"Invalid speaker: {agent_id}")

        bubbles: List[str] = []
        if override_content:
            bubbles = [self._normalize_name_references(override_content.strip())]
            thought = ""
            suspicion: Dict[str, Any] = {}
        elif self.chat_style == "group_chat":
            agent = self.agents[agent_id]
            static_text, dynamic_text = self._build_chat_prompt_parts(agent_state)
            history = list(self.state.conversation_history[-20:])
            if dynamic_text:
                # 局势简报作为对话末尾的 user 消息，保持 system 前缀稳定以利用提示词缓存
                history.append({"role": "user", "content": dynamic_text})
            chat = await agent.generate_chat_messages(
                system_prompt=static_text,
                conversation_history=history,
                current_round=self.state.current_round,
            )
            bubbles = [
                self._normalize_name_references((bubble or "").strip())
                for bubble in (chat.get("messages") or [])
            ]
            bubbles = [bubble for bubble in bubbles if bubble] or ["……"]
            thought = self._sanitize_role_consistent_thought(agent_state, chat.get("thought", ""))
            suspicion = self._sanitize_suspicion_scores(
                chat.get("suspicion", {}),
                speaker_id=agent_id,
            )
        else:
            agent = self.agents[agent_id]
            static_text, dynamic_text = self._build_discussion_prompt_parts(agent_state)
            history = list(self.state.conversation_history[-12:])
            if dynamic_text:
                # 局势简报作为对话末尾的 user 消息，保持 system 前缀稳定以利用提示词缓存
                history.append({"role": "user", "content": dynamic_text})
            response = await agent.generate_description(
                system_prompt=static_text,
                conversation_history=history,
                current_round=self.state.current_round,
            )
            speech = (response.get("speech") or "").strip() or f"{agent_state.name} 暂时没有明确判断。"
            bubbles = [self._normalize_name_references(speech)]
            thought = self._sanitize_role_consistent_thought(agent_state, response.get("thought", ""))
            suspicion = self._sanitize_suspicion_scores(
                response.get("suspicion", {}),
                speaker_id=agent_id,
            )

        self.state.speakers_this_round.append(agent_id)

        # 群聊模式：每条气泡单独写入对话历史，后续回合把群聊记录作为上下文
        if len(bubbles) > 1:
            for bubble_index, bubble in enumerate(bubbles):
                self.state.conversation_history.append({
                    "round": self.state.current_round,
                    "agent_id": agent_id,
                    "agent_name": agent_state.name,
                    "type": "discussion",
                    "content": bubble,
                    "thought": thought if bubble_index == 0 else "",
                    "suspicion": suspicion if bubble_index == 0 else {},
                    "bubble_index": bubble_index + 1,
                    "bubble_total": len(bubbles),
                })
        else:
            self.state.conversation_history.append({
                "round": self.state.current_round,
                "agent_id": agent_id,
                "agent_name": agent_state.name,
                "type": "discussion",
                "content": bubbles[0],
                "thought": thought,
                "suspicion": suspicion,
            })

        speech = " / ".join(bubbles)
        message = {
            "round": self.state.current_round,
            "agent_id": agent_id,
            "agent_name": agent_state.name,
            "type": "discussion",
            "content": speech,
            "speech": speech,
            "bubbles": bubbles,
            "thought": thought,
            "suspicion": suspicion,
        }

        self._record_event(
            GameEventType.DISCUSSION,
            {
                "agent_id": agent_id,
                "agent_name": agent_state.name,
                "speech": speech,
                "bubbles": bubbles,
                "thought": thought,
                "suspicion": suspicion,
            },
        )
        return message

    async def run_voting_turn(self, agent_id: str) -> Dict[str, Any]:
        """Generate one voting turn using the agent's LLM."""
        agent_state = self.get_agent_state(agent_id)
        if not agent_state or not agent_state.is_alive:
            raise ValueError(f"Invalid voter: {agent_id}")

        valid_agent_ids = [
            candidate.agent_id
            for candidate in self.get_alive_agents()
            if candidate.agent_id != agent_id
        ]
        if not valid_agent_ids:
            raise ValueError("No valid voting targets")

        agent = self.agents[agent_id]
        static_text, dynamic_text = self._build_voting_prompt_parts(agent_state, valid_agent_ids)
        history = list(self.state.conversation_history[-12:])
        if dynamic_text:
            # 投票简报作为对话末尾的 user 消息，保持 system 前缀稳定以利用提示词缓存
            history.append({"role": "user", "content": dynamic_text})
        response = await agent.generate_vote(
            system_prompt=static_text,
            conversation_history=history,
            valid_agent_ids=valid_agent_ids,
            current_round=self.state.current_round,
        )
        thought = self._normalize_name_references(
            self._sanitize_role_consistent_thought(agent_state, response.get("thought", ""))
        )

        vote_target = response["vote"]
        vote_result = self.record_vote(agent_id, vote_target)
        vote_message = {
            "round": self.state.current_round,
            "agent_id": "system",
            "type": "vote",
            "content": f"{agent_state.name} 投票给 {vote_result['target_name']}",
            "thought": thought,
            "confidence": response.get("confidence", 0.5),
            "used_llm": response.get("used_llm", True),
        }
        self.state.conversation_history.append(vote_message)
        return {
            **vote_result,
            "thought": thought,
            "confidence": response.get("confidence", 0.5),
            "used_llm": response.get("used_llm", True),
        }

    def start_voting_phase(self):
        """Start voting phase."""
        self.state.phase = WerewolfPhase.DAY_VOTING
        self.state.votes_this_round = {}

        # Record event
        self._record_event(
            GameEventType.PHASE_CHANGE,
            {
                "from_phase": WerewolfPhase.DAY_DISCUSSION.value,
                "to_phase": WerewolfPhase.DAY_VOTING.value
            }
        )

        logger.info("Voting phase started")

    def record_vote(self, voter_id: str, target_id: str) -> Dict[str, Any]:
        """
        Record a vote.

        Args:
            voter_id: ID of the voting agent
            target_id: ID of the target being voted for

        Returns:
            Vote result dict
        """
        # Validate voter
        voter = self.get_agent_state(voter_id)
        if not voter or not voter.is_alive:
            raise ValueError(f"Invalid voter: {voter_id}")

        # Validate target
        target = self.get_agent_state(target_id)
        if not target or not target.is_alive:
            raise ValueError(f"Invalid vote target: {target_id}")

        # Record vote
        self.state.votes_this_round[voter_id] = target_id

        # Update vote history
        voter.vote_history.append({
            "round": self.state.current_round,
            "voted_for": target_id,
            "phase": "day"
        })

        # Record event
        self._record_event(
            GameEventType.VOTE,
            {
                "voter_id": voter_id,
                "voter_name": voter.name,
                "target_id": target_id,
                "target_name": target.name
            }
        )

        logger.info(f"{voter.name} votes for {target.name}")

        return {
            "voter_id": voter_id,
            "voter_name": voter.name,
            "target_id": target_id,
            "target_name": target.name
        }

    def resolve_voting(self) -> Dict[str, Any]:
        """
        Resolve voting and eliminate player with most votes.

        Returns:
            Elimination result dict
        """
        if not self.state.votes_this_round:
            return {
                "eliminated": False,
                "message": "无人投票"
            }

        # Count votes
        vote_counts: Dict[str, int] = {}
        for target_id in self.state.votes_this_round.values():
            vote_counts[target_id] = vote_counts.get(target_id, 0) + 1

        # Find player with most votes
        max_votes = max(vote_counts.values())
        candidates = [agent_id for agent_id, count in vote_counts.items() if count == max_votes]

        # Handle tie - random selection
        eliminated_id = random.choice(candidates)
        eliminated = self.get_agent_state(eliminated_id)

        # Eliminate player
        eliminated.is_alive = False

        logger.info(f"Voting resolved - {eliminated.name} eliminated with {max_votes} votes")

        # Add to conversation history
        self.state.conversation_history.append({
            "round": self.state.current_round,
            "agent_id": "system",
            "type": "elimination",
            "content": f"{eliminated.name} 被投票淘汰，角色：{get_role_name_cn(eliminated.role)}"
        })

        # Record event
        self._record_event(
            GameEventType.ELIMINATION,
            {
                "eliminated_id": eliminated_id,
                "eliminated_name": eliminated.name,
                "eliminated_role": self._enum_value(eliminated.role),
                "eliminated_role_cn": get_role_name_cn(eliminated.role),
                "vote_count": max_votes,
                "votes": vote_counts
            },
            include_snapshot=True
        )

        return {
            "eliminated": True,
            "eliminated_id": eliminated_id,
            "eliminated_name": eliminated.name,
            "eliminated_role": self._enum_value(eliminated.role),
            "eliminated_role_cn": get_role_name_cn(eliminated.role),
            "vote_count": max_votes,
            "votes": vote_counts
        }

    def check_win_condition(self) -> Optional[Dict[str, Any]]:
        """
        Check if game has ended.

        Returns:
            Win result dict if game ended, None otherwise
        """
        alive_werewolves = self.get_alive_werewolves()
        alive_good = self.get_alive_good_players()

        # Werewolves win if good players <= werewolves
        if len(alive_good) <= len(alive_werewolves):
            self.state.phase = WerewolfPhase.GAME_OVER
            self.state.winner = WerewolfFaction.WEREWOLF
            self.state.game_over_reason = "狼人数量 >= 好人数量"

            # Record event
            self._record_event(
                GameEventType.GAME_OVER,
                {
                    "winner": WerewolfFaction.WEREWOLF.value,
                    "reason": self.state.game_over_reason
                },
                include_snapshot=True
            )

            logger.info("Game over - Werewolves win")

            return {
                "game_over": True,
                "winner": WerewolfFaction.WEREWOLF.value,
                "reason": self.state.game_over_reason,
                "message": "狼人阵营获胜！"
            }

        # Good players win if all werewolves eliminated
        if len(alive_werewolves) == 0:
            self.state.phase = WerewolfPhase.GAME_OVER
            self.state.winner = WerewolfFaction.GOOD
            self.state.game_over_reason = "所有狼人被淘汰"

            # Record event
            self._record_event(
                GameEventType.GAME_OVER,
                {
                    "winner": WerewolfFaction.GOOD.value,
                    "reason": self.state.game_over_reason
                },
                include_snapshot=True
            )

            logger.info("Game over - Good faction wins")

            return {
                "game_over": True,
                "winner": WerewolfFaction.GOOD.value,
                "reason": self.state.game_over_reason,
                "message": "好人阵营获胜！"
            }

        return None

    def advance_to_next_round(self):
        """Advance to next round."""
        self.state.current_round += 1
        self.state.phase = WerewolfPhase.NIGHT
        self.state.night_actions = []
        self.state.death_tonight = []
        self.state.werewolf_kill_target = None
        self.state.votes_this_round = {}
        self.state.speakers_this_round = []
        self.state.updated_at = datetime.now()
        self._persist_replay()

        logger.info(f"Advanced to round {self.state.current_round}")

    def get_game_state(self) -> WerewolfGameState:
        """Get current game state."""
        self.state.updated_at = datetime.now()
        return self.state

    def to_replay_dict(self) -> Dict[str, Any]:
        """Export replay payload for API responses and persistence."""
        alive_count = len([agent for agent in self.state.agents.values() if agent.is_alive])
        return {
            "game_id": self.game_id,
            "events": [
                {
                    "event_id": event.event_id,
                    "timestamp": event.timestamp.isoformat(),
                    "event_type": self._enum_value(event.event_type),
                    "round": event.round,
                    "phase": self._enum_value(event.phase),
                    "data": event.data,
                    "game_state_snapshot": event.game_state_snapshot,
                }
                for event in self.game_events
            ],
            "total_events": len(self.game_events),
            "player_count": self.player_count,
            "alive_count": alive_count,
            "agents": {
                agent_id: {
                    "agent_id": agent_state.agent_id,
                    "name": agent_state.name,
                    "role": self._enum_value(agent_state.role),
                    "role_cn": get_role_name_cn(agent_state.role),
                    "faction": self._enum_value(agent_state.faction),
                    "mbti_type": agent_state.mbti_type,
                    "iq_level": self._enum_value(agent_state.iq_level),
                    "is_alive": agent_state.is_alive,
                }
                for agent_id, agent_state in self.state.agents.items()
            },
            "current_round": self.state.current_round,
            "current_phase": self._enum_value(self.state.phase),
            "winner": self._enum_value(self.state.winner),
            "game_over_reason": self.state.game_over_reason,
            "started_at": self.state.created_at.isoformat(),
            "updated_at": self.state.updated_at.isoformat(),
        }

    def _persist_replay(self) -> None:
        """Persist replay payload so historical games remain replayable."""
        try:
            werewolf_replay_store.save_replay(self.to_replay_dict())
        except Exception as exc:
            logger.warning("Failed to persist werewolf replay for %s: %s", self.game_id, exc)

    def to_dict(self) -> Dict[str, Any]:
        """Convert game to dictionary for serialization."""
        return {
            "game_id": self.game_id,
            "player_count": self.player_count,
            "state": self._model_dump(self.state),
            "agents": {
                agent_id: agent.to_dict()
                for agent_id, agent in self.agents.items()
            }
        }
