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
import uuid
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
    ):
        """
        Initialize werewolf game.

        Args:
            game_id: Unique game identifier
            player_count: Number of players (6-12)
            model_config: Optional model configuration for agents
        """
        if player_count not in ROLE_DISTRIBUTION:
            raise ValueError(f"Invalid player count: {player_count}. Must be 6-12.")

        self.game_id = game_id
        self.player_count = player_count
        self.model_config = model_config
        self.game_config = game_config or {}
        self.fast_mode = bool(self.game_config.get("fast_mode", False))
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

        # Create agent factory
        factory = AgentFactory()

        # Create agents with assigned roles
        for i, role in enumerate(roles):
            agent_id = f"werewolf_agent_{i+1}"

            # Select MBTI and IQ based on role
            mbti_type, iq_level = self._select_personality_for_role(role)

            # Create agent config
            config = AgentConfig(
                id=agent_id,
                mbti_type=mbti_type,
                iq_level=iq_level,
                word=None,  # No word in werewolf game
                name=factory._generate_name(mbti_type)
            )

            # Create memory system
            memory_system = AgentMemorySystem(agent_id=agent_id, iq_level=iq_level)

            faction = get_faction(role)

            # Create agent
            role_name = get_role_name_cn(role)
            runtime_context = (
                "这是狼人杀游戏，不是《谁是卧底》。\n"
                f"- 真实角色: {role_name}\n"
                f"- 阵营: {faction.value}\n"
                "- 没有词语描述任务；所有发言、投票和夜间行动都围绕狼人杀局势推理。\n"
                "- 不要在公开发言中泄露只有自己阵营或神职才知道的私密信息，除非策略明确要求跳身份。"
            )
            agent = Agent(
                config=config,
                memory_system=memory_system,
                model_config=self.model_config,
                runtime_context=runtime_context,
            )
            self.agents[agent_id] = agent

            # Create agent state
            agent_state = WerewolfAgentState(
                agent_id=agent_id,
                name=config.name,
                role=role,
                faction=faction,
                is_alive=True,
                is_possessed=False,
                mbti_type=mbti_type,
                iq_level=iq_level
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
        system_prompt = f"""你正在参与狼人杀夜晚决策。
身份：{chooser_state.name}({chooser_state.agent_id})，真实角色={role_name}，MBTI={chooser_state.mbti_type}，IQ={chooser_state.iq_level}。
人设：{self._build_night_persona_brief(chooser_state)}
任务：{action_name}。{action_summary}
额外信息：{extra_context or '暂无'}
局势：{self._build_night_table_summary()}
候选目标：
{target_text}
记忆：{memory_context or '暂无'}
最近公开发言：{public_history}
私密边界：{self._build_night_private_brief(chooser_state)}
输出要求：
1. 只输出一行 JSON：{{"thought":"...","vote":"玩家ID","confidence":0.75}}
2. vote 只能填写候选目标里的玩家 ID。
3. thought 必须像这个角色本人在夜里权衡，带一点 MBTI 气质，不要模板句。
4. 好人不能写狼队视角；狼人也不能把自己写成别的真实身份。
5. confidence 必须是 0 到 1 的数字。"""
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
        system_prompt = f"""你正在参与狼人杀夜晚决策。
身份：{chooser_state.name}({chooser_state.agent_id})，真实角色={role_name}，MBTI={chooser_state.mbti_type}，IQ={chooser_state.iq_level}。
人设：{self._build_night_persona_brief(chooser_state)}
任务：{action_name}。{action_summary}
额外信息：{extra_context or '暂无'}
局势：{self._build_night_table_summary()}
可选项：
{option_text}
记忆：{memory_context or '暂无'}
最近公开发言：{public_history}
私密边界：{self._build_night_private_brief(chooser_state)}
输出要求：
1. 只输出一行 JSON：{{"thought":"...","vote":"可选项ID","confidence":0.75}}
2. vote 只能填写可选项里的 ID。
3. thought 必须像这个角色本人在夜里取舍，带一点 MBTI 气质，不要模板句。
4. 好人不能写狼队视角；狼人也不能把自己写成别的真实身份。
5. confidence 必须是 0 到 1 的数字。"""
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

        return f"""你正在参与一局狼人杀白天讨论，请根据你的身份和场上信息发言。

## 你的身份
- 玩家 ID: {agent_state.agent_id}
- 名字: {agent_state.name}
- 公开身份: 未知
- 真实角色: {role_name}
- MBTI: {agent_state.mbti_type}
- IQ: {agent_state.iq_level}

## 你的人设约束
{self._build_personality_profile(agent_state.mbti_type, agent_state.iq_level)}

## 你的已知信息
- 狼人同伴: {teammate_text}
- 预言家查验结果: {seer_results}
- 今晚死亡情况:
{self._format_death_info()}

## 当前存活玩家
{self._format_alive_players()}

## 最近的讨论
{self._format_recent_discussion()}

## 私密思考边界
{self._build_private_knowledge_rules(agent_state)}

## 发言要求
1. 说 2-4 句自然中文，建议 80-180 字。
2. 你可以提到别人的名字，但不要泄露“你是 AI”或输出解释。
3. 狼人要伪装，好人要尽量分析。
4. 发言尽量包含：你对局势的判断、你怀疑或信任的人、以及你建议今天怎么推进。
5. 发言必须明显符合你的 MBTI 人设、说话风格和 IQ 层次，不能所有人都像同一种语气。
6. 同一个角色应保持稳定口吻：强势的人更像带队，细腻的人更犹豫，理性的人更注重逻辑，感性的人更注重情绪与关系。
7. 你的公开发言必须有一个鲜明的个人语言动作，例如下判断、追问漏洞、安抚情绪、回忆细节、反问挑刺、强调规则中的一种，不能只是平铺直叙。
8. 禁止使用泛化模板，比如“先听听大家发言”“我觉得有点可疑”“大家不要乱投”这类任何角色都能说的话，除非你把它说得非常符合你的人设。
9. 要让旁观者不看标签也能听出你更像带队者、观察者、照顾者、辩手、艺术型直觉派或行动派。
10. `thought` 必须严格符合你的真实角色和已知信息，不能把自己写成别的身份；只有狼人能在内心提到狼人同伴，好人阵营不能假装自己是狼人。
11. 好人阵营在 `thought` 中不能出现“狼人同伴/狼队策略/保护狼队/我是狼人”等措辞；狼人阵营也不能把自己写成神职或村民本人。
12. suspicion 的 key 必须使用玩家 ID。
13. 如果你不是狼人，涉及狼人动机时只能写“可能/像/怀疑/更像”，不能写成“我知道/明显/就是/合理策略”。
14. 下笔前先自检：哪些是“已知事实”，哪些只是“个人推测”；推测必须保留不确定语气。
15. 只输出 JSON。

JSON 格式:
{{
  "thought": "你的内心分析",
  "speech": "你的公开发言",
  "suspicion": {{"玩家ID": 0}}
}}"""

    def _build_voting_prompt(self, agent_state: WerewolfAgentState, valid_agent_ids: List[str]) -> str:
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

        return f"""你正在参与狼人杀投票阶段，请根据今天的发言投票。

## 你的身份
- 玩家 ID: {agent_state.agent_id}
- 名字: {agent_state.name}
- 真实角色: {role_name}
- MBTI: {agent_state.mbti_type}
- IQ: {agent_state.iq_level}

## 你的人设约束
{self._build_personality_profile(agent_state.mbti_type, agent_state.iq_level)}

## 今天的讨论
{self._format_recent_discussion()}

## 可投票玩家
{votable_players}

## 你的怀疑分
{suspicion_text}

## 私密思考边界
{self._build_private_knowledge_rules(agent_state)}

## 投票要求
1. vote 必须是可投票玩家的 ID。
2. confidence 取 0 到 1。
3. thought 必须体现你的 MBTI 性格和思维方式。
4. 投票理由要像这个角色本人会说的话，不要千篇一律。
5. 你的投票分析必须带有鲜明的人设动作，例如控场、拆逻辑、凭细节记忆、凭关系敏感、凭规则或凭直觉，而不是统一模板。
6. 禁止使用“信息还不够所以先随便投/先跟着大家走”这种偷懒式空话，除非这正是你的人设弱点并明确写出来。
7. `thought` 必须严格符合你的真实角色和已知信息，不能把自己写成别的身份。
8. 好人阵营不能在 `thought` 中拥有狼队视角；狼人也不能把自己的私密独白写成神职自白。
9. 如果你不是狼人，分析狼人时只能写推测，不能把“狼队在想什么/狼队昨晚怎么做/某人在保护狼队利益”写成确定事实。
10. 写 thought 前先区分“已知事实”和“个人推测”，推测要保留不确定语气。
11. 只输出 JSON。

JSON 格式:
{{
  "thought": "你的投票分析",
  "vote": "玩家ID",
  "confidence": 0.75
}}"""

    async def run_discussion_turn(self, agent_id: str) -> Dict[str, Any]:
        """Generate one discussion turn using the agent's LLM."""
        agent_state = self.get_agent_state(agent_id)
        if not agent_state or not agent_state.is_alive:
            raise ValueError(f"Invalid speaker: {agent_id}")

        agent = self.agents[agent_id]
        response = await agent.generate_description(
            system_prompt=self._build_discussion_prompt(agent_state),
            conversation_history=self.state.conversation_history[-12:],
            current_round=self.state.current_round,
        )
        speech = (response.get("speech") or "").strip() or f"{agent_state.name} 暂时没有明确判断。"
        thought = self._sanitize_role_consistent_thought(agent_state, response.get("thought", ""))
        suspicion = self._sanitize_suspicion_scores(
            response.get("suspicion", {}),
            speaker_id=agent_id,
        )

        self.state.speakers_this_round.append(agent_id)
        message = {
            "round": self.state.current_round,
            "agent_id": agent_id,
            "agent_name": agent_state.name,
            "type": "discussion",
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
        response = await agent.generate_vote(
            system_prompt=self._build_voting_prompt(agent_state, valid_agent_ids),
            conversation_history=self.state.conversation_history[-12:],
            valid_agent_ids=valid_agent_ids,
            current_round=self.state.current_round,
        )
        thought = self._sanitize_role_consistent_thought(agent_state, response.get("thought", ""))

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
