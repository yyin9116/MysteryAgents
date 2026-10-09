"""
Jubensha (剧本杀) game service.

对齐 WerewolfService 的写法：
- 内存态 JubenshaGameState + game_events 回放事件；
- 复用 Agent / AgentMemorySystem / LLMService / prompt_registry；
- 私密剧本按 char_id 隔离注入，SSE 永不广播 truth / 私密内容；
- 阶段机：LOBBY → READING → CLUE → DISCUSSION(×N) → VOTE → REVEAL。
"""

import logging
import random
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from models.agent import Agent, AgentConfig
from models.jubensha import (
    CharacterCamp,
    CharacterScript,
    Clue,
    JubenshaPhase,
    ScriptPack,
)
from models.personality import PersonalityPrompt
from services.agent_factory import AgentFactory
from services.memory_service import AgentMemorySystem
from services import prompt_registry
from services.werewolf_replay_store import WerewolfReplayStore

logger = logging.getLogger(__name__)

# 剧本杀回放落盘：复用 WerewolfReplayStore 的通用 JSON 存取逻辑
from config.settings import settings as _settings


class _JubenshaReplayStore:
    def __init__(self) -> None:
        self.storage_path = _settings.get_storage_path() / "jubensha_replays"
        self.storage_path.mkdir(parents=True, exist_ok=True)

    save_replay = WerewolfReplayStore.save_replay
    load_replay = WerewolfReplayStore.load_replay
    delete_replay = WerewolfReplayStore.delete_replay
    list_replays = WerewolfReplayStore.list_replays


_jubensha_replay_store: Optional[_JubenshaReplayStore] = None


def _get_replay_store() -> "_JubenshaReplayStore":
    global _jubensha_replay_store
    if _jubensha_replay_store is None:
        _jubensha_replay_store = _JubenshaReplayStore()
    return _jubensha_replay_store


class JubenshaAgentRuntime:
    """一个角色席位的运行时状态。"""

    def __init__(self, char: CharacterScript, agent: Agent, iq_level: str) -> None:
        self.char = char
        self.agent = agent
        self.iq_level = iq_level
        self.received_clues: List[Clue] = []
        self.is_alive = True  # 剧本杀角色不会中途出局（保留扩展位）

    @property
    def char_id(self) -> str:
        return self.char.char_id

    @property
    def name(self) -> str:
        return self.char.name


class JubenshaService:
    """剧本杀对局服务：一局 = 一个 ScriptPack + N 个角色 agent。"""

    # 阵营 → 模型/思考分档：凶手需要最强推理
    _CAMP_TIER = {CharacterCamp.MURDERER: 0, CharacterCamp.CIVILIAN: 1}
    _CAMP_EFFORT = {CharacterCamp.MURDERER: "high", CharacterCamp.CIVILIAN: "medium"}

    # 模型强度启发式（与狼人杀一致）
    _MODEL_STRONG_KEYWORDS = (
        "opus", "gpt-5", "gpt-4.1", "o3", "o4", "pro", "max", "grok-4",
        "deepseek-r1", "-r1", "glm-4.6", "glm-4.5", "kimi-k2", "qwen-max",
        "thinking", "reasoner", "ultra", "plus",
    )
    _MODEL_WEAK_KEYWORDS = (
        "mini", "flash", "lite", "nano", "small", "tiny", "-8b", "-7b", "-4b",
        "haiku", "instant", "-air", "turbo", "free", "spark",
    )

    _NAME_SEPARATOR_VARIANTS = str.maketrans({"・": "·", "‧": "·", "•": "·", "∙": "·", "⋅": "·"})
    _EMOJI_RE = re.compile(
        "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF\u2B00-\u2BFF\uFE0F]"
    )

    def __init__(
        self,
        game_id: str,
        script_pack: ScriptPack,
        model_config: Optional[Dict[str, Any]] = None,
        agent_model_configs: Optional[List[Optional[Dict[str, Any]]]] = None,
        game_config: Optional[Dict[str, Any]] = None,
        auto_model_plan: Optional[Dict[str, Any]] = None,
        player_mode: str = "spectate",
        player_char_id: Optional[str] = None,
    ) -> None:
        self.game_id = game_id
        self.script_pack = script_pack
        self.model_config = model_config
        self.agent_model_configs = agent_model_configs
        self.auto_model_plan = auto_model_plan or {}
        self.game_config = game_config or {}
        self.fast_mode = bool(self.game_config.get("fast_mode", False))
        self.chat_style = self.game_config.get("chat_style") or "speech"
        # 智能体执行框架：agentscope（ReActAgent + 原生压缩 + MsgHub 群聊）为默认，
        # legacy（litellm 直连）保留为回退。
        self.runtime = (self.game_config.get("runtime") or "agentscope").lower()
        if self.runtime not in ("legacy", "agentscope"):
            self.runtime = "agentscope"
        # MsgHub 群聊组（agentscope 运行时下首个讨论回合惰性创建）
        self._msg_hub: Optional[Any] = None
        self.player_mode = player_mode if player_mode in ("spectate", "participate") else "spectate"
        self.player_char_id = player_char_id
        # 夺席代打发言：char_id -> 文本
        self.pending_player_speeches: Dict[str, str] = {}

        # ---- 阶段与回合 ----
        self.phase = JubenshaPhase.LOBBY
        self.current_round = 0              # 讨论轮次（0 = 未开始）
        self.discussion_rounds = self._resolve_discussion_rounds()
        self.clue_rounds_done = 0

        # ---- 运行时 ----
        self.agents: Dict[str, JubenshaAgentRuntime] = {}
        self.conversation_history: List[Dict[str, Any]] = []
        self.votes: Dict[str, Dict[str, Any]] = {}   # voter_char_id -> {target, reason, confidence}
        self.reveal_result: Optional[Dict[str, Any]] = None
        self.evaluation: Optional[Dict[str, Any]] = None   # MIRAGE 风格评估报告（按需生成）
        self.winner: Optional[str] = None            # civilian | murderer | aborted
        self.game_over_reason: str = ""
        self.created_at = datetime.now()
        self.updated_at = datetime.now()

        self.game_events: List[Dict[str, Any]] = []

        self._create_agents()
        self._persist_replay()

        logger.info(
            "Created jubensha game %s with script %s (%s characters)",
            game_id, script_pack.script_id, len(script_pack.characters),
        )

    # ------------------------------------------------------------------ #
    # 初始化
    # ------------------------------------------------------------------ #

    def _resolve_discussion_rounds(self) -> int:
        for stage in self.script_pack.host_manual.stages:
            if stage.type == "discussion" and stage.rounds:
                return max(1, min(int(stage.rounds), 5))
        return 2

    @classmethod
    def _clean_character_name(cls, name: str) -> str:
        name = cls._EMOJI_RE.sub("", name)
        name = name.translate(cls._NAME_SEPARATOR_VARIANTS)
        return re.sub(r"\s+", "", name) or name

    @classmethod
    def _rank_model_strength(cls, model_id: str) -> Tuple[int, str]:
        normalized = (model_id or "").lower()
        score = 0
        for keyword in cls._MODEL_STRONG_KEYWORDS:
            if keyword in normalized:
                score += 2
        for keyword in cls._MODEL_WEAK_KEYWORDS:
            if keyword in normalized:
                score -= 2
        return (score, normalized)

    def _filter_candidate_models(self, candidates: List[str], disabled_models: List[str]) -> List[str]:
        disabled = {str(m).strip().lower() for m in (disabled_models or []) if str(m).strip()}
        seen: set = set()
        result: List[str] = []
        for item in candidates or []:
            key = str(item).strip().lower()
            if not key or key in seen or key in disabled:
                continue
            seen.add(key)
            result.append(str(item).strip())
        return result

    def _plan_auto_models(self, camps: List[CharacterCamp]) -> Dict[int, Dict[str, Any]]:
        plan = self.auto_model_plan or {}
        if not self.model_config:
            return {}
        candidates = self._filter_candidate_models(
            plan.get("candidates"), plan.get("disabled_models"),
        )
        if not candidates:
            return {}
        ranked = sorted(candidates, key=self._rank_model_strength, reverse=True)
        mid = len(ranked) // 2
        groups: Dict[int, List[int]] = {0: [], 1: []}
        for idx, camp in enumerate(camps):
            groups[self._CAMP_TIER[camp]].append(idx)
        pools = {0: ranked, 1: ranked[mid:] if len(ranked) >= 2 else ranked}
        cursors = {0: 0, 1: 0}
        assignment: Dict[int, Dict[str, Any]] = {}
        for tier in (0, 1):
            for idx in groups[tier]:
                effort = self._CAMP_EFFORT[camps[idx]] if plan.get("effort_by_role", True) else None
                if self.fast_mode:
                    effort = "low"
                assignment[idx] = {"model": pools[tier][cursors[tier] % len(pools[tier])], "effort": effort}
                cursors[tier] += 1
        return assignment

    def _create_agents(self) -> None:
        chars = self.script_pack.characters
        camps = [c.camp for c in chars]
        auto_assignments = self._plan_auto_models(camps)
        used_names: set = set()

        for i, char in enumerate(chars):
            name = self._clean_character_name(char.name) or char.char_id
            if name in used_names:
                name = f"{name}·{i + 1}"
            used_names.add(name)
            char.name = name

            mbti = (char.mbti or "").upper()
            if mbti not in {
                "ENTJ", "INFP", "ISTP", "ENFJ", "INTP", "ESTJ", "ISFP", "ENTP",
                "ISFJ", "ESFP", "INTJ", "ESFJ", "ESTP", "INFJ", "ENFP", "ISTJ",
            }:
                mbti = random.choice(["INTJ", "ENTP", "ISTP", "INFP", "ESTJ", "ENFP"])

            iq_level = "High" if char.camp == CharacterCamp.MURDERER else "Mid"

            effective_config = None
            if self.agent_model_configs and i < len(self.agent_model_configs):
                effective_config = self.agent_model_configs[i]
            effective_config = effective_config or self.model_config
            auto_pick = auto_assignments.get(i)
            if auto_pick and effective_config:
                effective_config = {
                    **effective_config,
                    "model": auto_pick["model"],
                }
                if auto_pick.get("effort"):
                    effective_config["extra_params"] = {
                        **(effective_config.get("extra_params") or {}),
                        "reasoning_effort": auto_pick["effort"],
                    }

            agent_id = char.char_id
            config = AgentConfig(
                id=agent_id,
                mbti_type=mbti,
                iq_level=iq_level,
                word=None,
                name=name,
            )
            memory_system = AgentMemorySystem(agent_id=agent_id, iq_level=iq_level)
            secret_text = "\n".join(f"- {s}" for s in char.secret_knowledge) or "暂无"
            runtime_context = (
                "这是剧本杀游戏，不是狼人杀或谁是卧底。\n"
                f"- 你的角色: {name}\n"
                f"- 阵营: {'凶手' if char.camp == CharacterCamp.MURDERER else '平民'}\n"
                "- 你的私密剧本和秘密只有你自己知道，公开发言必须遵守保密边界。\n"
                f"- 你已知的秘密:\n{secret_text}"
            )
            llm_backend: Optional[Any] = None
            if self.runtime == "agentscope":
                # 每个角色一个 AgentScope 后端（模型按该角色的 effective_config 绑定），
                # 常驻会话由原生 CompressionConfig 自动压缩上下文；
                # 讨论阶段这些会话会组成 MsgHub 群聊组（见 _ensure_group_hub）。
                from services.agentscope_runtime import AgentscopeRuntime

                llm_backend = AgentscopeRuntime(model_config=effective_config)
            else:
                # legacy 回退：显式指定 litellm 直连（Agent 默认已是 AgentScope）
                from services.llm_service import LLMService

                llm_backend = LLMService()
            agent = Agent(
                config=config,
                memory_system=memory_system,
                model_config=effective_config,
                runtime_context=runtime_context,
                llm_service=llm_backend,
            )
            self.agents[agent_id] = JubenshaAgentRuntime(char=char, agent=agent, iq_level=iq_level)

            # 参与模式：玩家席位（仅状态标记）
            if self.player_mode == "participate" and not self.player_char_id:
                self.player_char_id = char.char_id
        if self.player_mode == "participate":
            if self.player_char_id not in self.agents:
                self.player_char_id = next(iter(self.agents))

    # ------------------------------------------------------------------ #
    # 状态与回放
    # ------------------------------------------------------------------ #

    @property
    def state(self) -> "JubenshaService":
        """兼容以 service.state 形式访问。"""
        return self

    @property
    def player_count(self) -> int:
        return len(self.agents)

    def get_runtime(self, char_id: str) -> Optional[JubenshaAgentRuntime]:
        return self.agents.get(char_id)

    def get_alive_runtimes(self) -> List[JubenshaAgentRuntime]:
        return [r for r in self.agents.values() if r.is_alive]

    def is_player_agent(self, char_id: str) -> bool:
        return self.player_mode == "participate" and char_id == self.player_char_id

    def _record_event(self, event_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        event = {
            "event_id": f"event_{len(self.game_events) + 1}",
            "timestamp": datetime.now(),
            "event_type": event_type,
            "round": self.current_round,
            "phase": self.phase.value,
            "data": data,
        }
        self.game_events.append(event)
        self.updated_at = datetime.now()
        self._persist_replay()
        return event

    def _persist_replay(self) -> None:
        try:
            _get_replay_store().save_replay(self.to_replay_dict())
        except Exception as exc:
            logger.warning("Persist jubensha replay failed: %s", exc)

    def to_replay_dict(self) -> Dict[str, Any]:
        """回放序列化：包含公共事件与结果，不包含未揭晓的私密剧本。"""
        return {
            "game_id": self.game_id,
            "mode": "jubensha",
            "script_id": self.script_pack.script_id,
            "title": self.script_pack.meta.title,
            "player_count": self.player_count,
            "alive_count": len(self.get_alive_runtimes()),
            "current_round": self.current_round,
            "current_phase": self.phase.value,
            "winner": self.winner,
            "game_over_reason": self.game_over_reason,
            "evaluation": self.evaluation,
            "started_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "total_events": len(self.game_events),
            "characters": [
                {
                    "char_id": r.char_id,
                    "name": r.name,
                    "camp": r.char.camp.value,
                    "model_label": (
                        f"{r.agent.model_config.get('provider')}/{r.agent.model_config.get('model')}"
                        if r.agent.model_config and r.agent.model_config.get("model") else None
                    ),
                }
                for r in self.agents.values()
            ],
            "events": [
                {
                    "event_id": e["event_id"],
                    "timestamp": e["timestamp"].isoformat(),
                    "event_type": e["event_type"],
                    "round": e["round"],
                    "phase": e["phase"],
                    **e["data"],
                }
                for e in self.game_events
            ],
        }

    # ------------------------------------------------------------------ #
    # Prompt 构建（缓存友好：静态身份 + 动态局势简报）
    # ------------------------------------------------------------------ #

    def _personality_profile(self, runtime: JubenshaAgentRuntime) -> str:
        mbti = runtime.agent.config.mbti_type
        iq = runtime.iq_level
        return (
            f"{PersonalityPrompt.get_distinctive_prompt(mbti)}"
        )

    def _build_static_discussion(self, runtime: JubenshaAgentRuntime) -> Dict[str, str]:
        char = runtime.char
        secret_text = "\n".join(f"- {s}" for s in char.secret_knowledge) or "暂无"
        return {
            "char_id": char.char_id,
            "char_name": char.name,
            "public_profile": char.public_profile or "未知",
            "personality_profile": self._personality_profile(runtime),
            "character_style": f"符合 {runtime.agent.config.mbti_type} 的说话方式",
            "mission": char.mission or "找出真凶",
            "private_script": char.script or "（无）",
            "secret_knowledge": secret_text,
        }

    def _received_clues_text(self, runtime: JubenshaAgentRuntime) -> str:
        if not runtime.received_clues:
            return "暂无"
        return "\n".join(f"- 《{c.title or '线索'}》: {c.content}" for c in runtime.received_clues)

    def _alive_players_text(self) -> str:
        return "\n".join(f"- {r.char_id}: {r.name}" for r in self.get_alive_runtimes())

    def _recent_discussion_text(self, limit: int = 12) -> str:
        msgs = [
            msg for msg in self.conversation_history[-limit:]
            if msg.get("type") in ("reading", "discussion")
        ]
        return "\n".join(f"【{m['agent_name']}】{m['content']}" for m in msgs) or "（讨论尚未开始）"

    def _votable_players_text(self, voter_id: str) -> str:
        return "\n".join(
            f"- {r.char_id}: {r.name}"
            for r in self.get_alive_runtimes()
            if r.char_id != voter_id
        ) or "（无）"

    def _build_reading_prompt(self, runtime: JubenshaAgentRuntime) -> str:
        return prompt_registry.render("jubensha_reading_prompt", {
            "char_id": runtime.char_id,
            "char_name": runtime.name,
            "public_profile": runtime.char.public_profile or "未知",
            "personality_profile": self._personality_profile(runtime),
            "character_style": f"符合 {runtime.agent.config.mbti_type} 的说话方式",
        })

    def _build_discussion_parts(self, runtime: JubenshaAgentRuntime) -> Tuple[str, str]:
        static_vars = self._build_static_discussion(runtime)
        dynamic_vars = {
            "received_clues": self._received_clues_text(runtime),
            "alive_players": self._alive_players_text(),
            "recent_discussion": self._recent_discussion_text(),
        }
        key = "jubensha_chat_prompt" if self.chat_style == "group_chat" else "jubensha_discussion_prompt"
        return prompt_registry.render_split(key, {**static_vars, **dynamic_vars})

    def _build_vote_parts(self, runtime: JubenshaAgentRuntime) -> Tuple[str, str]:
        return prompt_registry.render_split("jubensha_vote_prompt", {
            "char_id": runtime.char_id,
            "char_name": runtime.name,
            "personality_profile": self._personality_profile(runtime),
            "mission": runtime.char.mission or "找出真凶",
            "received_clues": self._received_clues_text(runtime),
            "votable_players": self._votable_players_text(runtime.char_id),
            "recent_discussion": self._recent_discussion_text(),
        })

    def _normalize_name_references(self, text: str) -> str:
        if not text:
            return text
        id_to_name = {r.char_id: r.name for r in self.agents.values()}
        def _replace(match: "re.Match") -> str:
            return id_to_name.get(match.group(0), match.group(0))
        return re.sub(r"char_\d+", _replace, text)

    # ------------------------------------------------------------------ #
    # 阶段流程
    # ------------------------------------------------------------------ #

    def start_reading(self) -> None:
        self.phase = JubenshaPhase.READING
        self._record_event("phase_change", {"message": "读本阶段开始"})

    async def run_reading_turn(
        self, char_id: str, override_content: Optional[str] = None
    ) -> Dict[str, Any]:
        """读本阶段：基于公开身份做一段自我介绍（不透露私密内容）。"""
        runtime = self.get_runtime(char_id)
        if not runtime:
            raise ValueError(f"Invalid character: {char_id}")
        if override_content is not None:
            speech = self._normalize_name_references(override_content.strip())
            thought = ""
        else:
            response = await runtime.agent.generate_description(
                system_prompt=self._build_reading_prompt(runtime),
                conversation_history=[],
                current_round=0,
            )
            speech = self._normalize_name_references(
                (response.get("speech") or "").strip() or f"{runtime.name} 已就座。"
            )
            thought = self._normalize_name_references(response.get("thought", ""))
        message = {
            "round": 0,
            "char_id": char_id,
            "agent_id": char_id,
            "agent_name": runtime.name,
            "type": "reading",
            "content": speech,
            "thought": thought,
            "player_controlled": override_content is not None,
            "suspicion": {},
        }
        self.conversation_history.append(message)
        self._record_event("reading", {
            "agent_id": char_id,
            "agent_name": runtime.name,
            "speech": speech,
            "thought": message["thought"],
            "player_controlled": message["player_controlled"],
        })
        return message

    def start_clue_round(self) -> None:
        self.phase = JubenshaPhase.CLUE
        self._record_event("phase_change", {"message": "线索发放阶段"})

    def grant_clue_round(self) -> List[Dict[str, Any]]:
        """发放下一轮线索：私有内容入各自上下文，公开只广播「谁获得了线索」。"""
        self.clue_rounds_done += 1
        grants: List[Dict[str, Any]] = []
        for clue in self.script_pack.clues:
            if clue.distribution.round != self.clue_rounds_done:
                continue
            pool_ids = [
                t.strip() for t in (clue.distribution.pool or "").split(",") if t.strip()
            ]
            recipients = (
                [self.agents[t] for t in pool_ids if t in self.agents]
                if pool_ids else self.get_alive_runtimes()
            )
            for runtime in recipients:
                runtime.received_clues.append(clue)
                runtime.agent.memory_system.add_memory(
                    f"获得线索《{clue.title or '线索'}》: {clue.content}", self.clue_rounds_done
                )
            grants.append({
                "clue_id": clue.clue_id,
                "title": clue.title,
                "recipients": [r.char_id for r in recipients],
                "recipient_names": [r.name for r in recipients],
            })
        self.phase = JubenshaPhase.DISCUSSION
        self._record_event("clue_granted", {"grants": grants, "clue_round": self.clue_rounds_done})
        return grants

    def start_discussion(self) -> None:
        self.phase = JubenshaPhase.DISCUSSION
        if self.current_round < 1:
            self.current_round = 1

    # ------------------------------------------------------------------ #
    # MsgHub 群聊广播
    # ------------------------------------------------------------------ #

    def _ensure_group_hub(self) -> None:
        """把各角色的常驻 AgentScope 会话组成 MsgHub 群聊组（幂等）。

        会话在读本阶段首次生成时创建；讨论开始时全部就绪。auto_broadcast
        保持关闭——模型按协议输出 JSON，广播原始回复会污染其他角色的记忆，
        改由 _broadcast_speech 广播净化后的发言。
        """
        if self._msg_hub is not None or self.runtime != "agentscope":
            return
        try:
            from agentscope.pipeline import MsgHub

            from services.agentscope_runtime import AgentscopeRuntime, is_agentscope_available

            if not is_agentscope_available():
                return
            participants = []
            for rt in self.agents.values():
                backend = rt.agent.llm_service
                if isinstance(backend, AgentscopeRuntime):
                    agent = backend.get_agent(rt.char_id)
                    if agent is not None:
                        participants.append(agent)
            if len(participants) >= 2:
                self._msg_hub = MsgHub(
                    participants=participants,
                    enable_auto_broadcast=False,
                    name=f"jubensha-{self.game_id}",
                )
                logger.info(
                    "MsgHub group ready for game %s with %d participants",
                    self.game_id, len(participants),
                )
        except Exception:
            logger.warning("MsgHub setup failed; falls back to history feeding", exc_info=True)

    async def _broadcast_speech(self, speaker: JubenshaAgentRuntime, bubbles: List[str]) -> None:
        """经 MsgHub 把发言广播给其他角色的常驻会话。

        广播内容与上层历史喂送的格式化结果一致（"char_id: 内容"），并用同一
        哈希去重，两条路径谁先到谁生效、绝不重复入记忆。
        """
        self._ensure_group_hub()
        if self._msg_hub is None:
            return
        try:
            from services.agentscope_runtime import AgentscopeRuntime, _content_hash

            speaker_agent = None
            speaker_backend = speaker.agent.llm_service
            if isinstance(speaker_backend, AgentscopeRuntime):
                speaker_agent = speaker_backend.get_agent(speaker.char_id)
            contents = [f"{speaker.char_id}: {b}" for b in bubbles if b]
            for rt in self.agents.values():
                if rt.char_id == speaker.char_id:
                    continue
                backend = rt.agent.llm_service
                if not isinstance(backend, AgentscopeRuntime):
                    continue
                target_agent = backend.get_agent(rt.char_id)
                if target_agent is None or target_agent is speaker_agent:
                    continue
                for item in contents:
                    await backend.observe_broadcast(
                        rt.char_id,
                        item,
                        speaker=speaker.name,
                        digest=_content_hash("user", item),
                    )
        except Exception:
            logger.debug("hub broadcast failed (ignored)", exc_info=True)

    async def run_discussion_turn(
        self, char_id: str, override_content: Optional[str] = None
    ) -> Dict[str, Any]:
        """一个讨论回合；群聊风格下生成多条短消息。"""
        runtime = self.get_runtime(char_id)
        if not runtime:
            raise ValueError(f"Invalid speaker: {char_id}")

        bubbles: List[str] = []
        if override_content:
            bubbles = [self._normalize_name_references(override_content.strip())]
            thought = ""
            suspicion: Dict[str, Any] = {}
        else:
            static_text, dynamic_text = self._build_discussion_parts(runtime)
            history = list(self.conversation_history[-20:])
            if dynamic_text:
                history.append({"role": "user", "content": dynamic_text})
            if self.chat_style == "group_chat":
                chat = await runtime.agent.generate_chat_messages(
                    system_prompt=static_text,
                    conversation_history=history,
                    current_round=self.current_round,
                )
                bubbles = [
                    self._normalize_name_references((b or "").strip())
                    for b in (chat.get("messages") or [])
                ]
                bubbles = [b for b in bubbles if b] or ["……"]
                thought = self._normalize_name_references(chat.get("thought", ""))
                suspicion = chat.get("suspicion", {}) or {}
            else:
                response = await runtime.agent.generate_description(
                    system_prompt=static_text,
                    conversation_history=history,
                    current_round=self.current_round,
                )
                speech = (response.get("speech") or "").strip() or f"{runtime.name} 沉默不语。"
                bubbles = [self._normalize_name_references(speech)]
                thought = self._normalize_name_references(response.get("thought", ""))
                suspicion = response.get("suspicion", {}) or {}

        speech = " / ".join(bubbles)
        message = {
            "round": self.current_round,
            "char_id": char_id,
            "agent_id": char_id,
            "agent_name": runtime.name,
            "type": "discussion",
            "content": speech,
            "speech": speech,
            "bubbles": bubbles,
            "thought": thought,
            "suspicion": suspicion,
            "player_controlled": override_content is not None,
        }
        for idx, bubble in enumerate(bubbles):
            self.conversation_history.append({
                "round": self.current_round,
                "char_id": char_id,
                "agent_id": char_id,
                "agent_name": runtime.name,
                "type": "discussion",
                "content": bubble,
                "thought": thought if idx == 0 else "",
                "bubble_index": idx + 1,
                "bubble_total": len(bubbles),
            })
        # MsgHub 群聊：发言即时广播到其他角色的常驻记忆（与历史喂送哈希幂等）
        await self._broadcast_speech(runtime, bubbles)
        self._record_event("discussion", {
            "agent_id": char_id,
            "agent_name": runtime.name,
            "speech": speech,
            "bubbles": bubbles,
            "thought": thought,
            "suspicion": suspicion,
            "player_controlled": override_content is not None,
        })
        return message

    def start_voting(self) -> None:
        self.phase = JubenshaPhase.VOTE
        self.votes = {}
        self._record_event("phase_change", {"message": "投票指认阶段"})

    async def run_vote_turn(self, char_id: str, player_reason: Optional[str] = None) -> Dict[str, Any]:
        """一个投票回合：LLM 生成指认；玩家代打时 player_reason 直接采用。"""
        runtime = self.get_runtime(char_id)
        if not runtime:
            raise ValueError(f"Invalid voter: {char_id}")
        votable = [r.char_id for r in self.get_alive_runtimes() if r.char_id != char_id]
        if not votable:
            raise ValueError("No valid voting targets")

        if player_reason is not None:
            thought = self._normalize_name_references(player_reason)
            target = player_reason if player_reason in votable else None
            confidence = 1.0
            used_llm = False
            if target is None:
                # player_reason 为理由文本时，目标由前端单独传 target_char_id
                target = votable[0]
        else:
            static_text, dynamic_text = self._build_vote_parts(runtime)
            history = list(self.conversation_history[-12:])
            if dynamic_text:
                history.append({"role": "user", "content": dynamic_text})
            response = await runtime.agent.generate_vote(
                system_prompt=static_text,
                conversation_history=history,
                valid_agent_ids=votable,
                current_round=self.current_round,
            )
            thought = self._normalize_name_references(response.get("thought", ""))
            target = response.get("vote")
            if target not in votable:
                # 兼容模型输出名字而非 ID
                target = next(
                    (r.char_id for r in self.get_alive_runtimes()
                     if r.char_id != char_id and (r.name in str(target) or str(target) in r.name)),
                    votable[0],
                )
            confidence = float(response.get("confidence", 0.5) or 0.5)
            used_llm = True

        self.votes[char_id] = {"target": target, "reason": thought, "confidence": confidence}
        self.conversation_history.append({
            "round": self.current_round,
            "agent_id": "system",
            "type": "vote",
            "content": f"{runtime.name} 投票指认 {self.agents[target].name}",
            "thought": thought,
        })
        result = {
            "voter_id": char_id,
            "voter_name": runtime.name,
            "target_id": target,
            "target_name": self.agents[target].name,
            "reason": thought,
            "confidence": confidence,
            "used_llm": used_llm,
        }
        self._record_event("vote", result)
        return result

    # ------------------------------------------------------------------ #
    # 结算
    # ------------------------------------------------------------------ #

    def reveal(self) -> Dict[str, Any]:
        """结算：真凶揭晓 + 阵营胜负 + 演示级评分。"""
        if self.phase == JubenshaPhase.REVEAL and self.reveal_result:
            return self.reveal_result
        self.phase = JubenshaPhase.REVEAL

        truth = self.script_pack.truth
        murderer_id = truth.murderer

        tally: Dict[str, int] = {}
        for vote in self.votes.values():
            tally[vote["target"]] = tally.get(vote["target"], 0) + 1
        top_target = max(tally, key=lambda k: tally[k]) if tally else None
        correct_accusation = bool(murderer_id and top_target == murderer_id)

        if murderer_id:
            self.winner = "civilian" if correct_accusation else "murderer"
        else:
            self.winner = "civilian"

        scores: List[Dict[str, Any]] = []
        for runtime in self.agents.values():
            cid = runtime.char_id
            my_votes = tally.get(cid, 0)
            my_vote = self.votes.get(cid, {}).get("target")
            voted_correct = bool(murderer_id and my_vote == murderer_id)
            is_murderer = runtime.char.camp == CharacterCamp.MURDERER
            score = 0
            if not is_murderer and voted_correct:
                score += 3      # 平民投中真凶
            if is_murderer and my_votes > 0 and not correct_accusation:
                score += 3      # 凶手逃过指认
            if is_murderer and my_votes > 0 and correct_accusation:
                score -= 1
            scores.append({
                "char_id": cid,
                "name": runtime.name,
                "camp": runtime.char.camp.value,
                "is_murderer": is_murderer,
                "votes_received": my_votes,
                "voted_for": my_vote,
                "voted_correctly": voted_correct,
                "score": score,
            })

        self.reveal_result = {
            "murderer_id": murderer_id,
            "murderer_name": self.agents[murderer_id].name if murderer_id in self.agents else None,
            "correct_accusation": correct_accusation,
            "top_voted_id": top_target,
            "top_voted_name": self.agents[top_target].name if top_target in self.agents else None,
            "tally": tally,
            "winner": self.winner,
            "scores": scores,
            "timeline": [t.model_dump(mode="json") for t in truth.timeline],
            "case_replay": truth.case_replay,
            "message": (
                f"真相揭晓：真凶是 {self.agents[murderer_id].name}。" if murderer_id in self.agents
                else "真相揭晓。"
            ),
        }
        self.game_over_reason = (
            "平民成功指认真凶" if self.winner == "civilian" and correct_accusation
            else "凶手逃脱指认" if self.winner == "murderer"
            else "对局结束"
        )
        self._record_event("game_over", {
            "winner": self.winner,
            "reason": self.game_over_reason,
            **{k: self.reveal_result[k] for k in ("murderer_id", "murderer_name", "correct_accusation", "tally", "scores")},
        })
        return self.reveal_result

    # ------------------------------------------------------------------ #
    # 参与模式等待
    # ------------------------------------------------------------------ #

    async def wait_for_player_speech(self, char_id: str, timeout: float = 240.0) -> Optional[str]:
        import asyncio
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while loop.time() < deadline:
            text = self.pending_player_speeches.pop(char_id, None)
            if text is not None:
                return text
            await asyncio.sleep(0.5)
        return None

    async def wait_for_player_vote(self, char_id: str, timeout: float = 240.0) -> bool:
        import asyncio
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while loop.time() < deadline:
            if char_id in self.votes:
                return True
            await asyncio.sleep(0.5)
        return False

    def submit_player_speech(self, char_id: str, content: str) -> Dict[str, Any]:
        runtime = self.get_runtime(char_id)
        if not runtime:
            raise ValueError(f"Invalid speaker: {char_id}")
        text = (content or "").strip()
        if not text:
            raise ValueError("发言内容不能为空")
        self.pending_player_speeches[char_id] = text[:500]
        return {"success": True, "char_id": char_id, "queued": True}

    def get_game_state(self) -> Dict[str, Any]:
        """公开状态（不含私密剧本与 truth）。"""
        return {
            "game_id": self.game_id,
            "script_id": self.script_pack.script_id,
            "title": self.script_pack.meta.title,
            "phase": self.phase.value,
            "current_round": self.current_round,
            "discussion_rounds": self.discussion_rounds,
            "clue_rounds_done": self.clue_rounds_done,
            "player_mode": self.player_mode,
            "player_char_id": self.player_char_id,
            "characters": [
                {
                    "char_id": r.char_id,
                    "name": r.name,
                    "public_profile": r.char.public_profile,
                    "camp": r.char.camp.value if self.phase == JubenshaPhase.REVEAL else None,
                    "model_label": (
                        f"{r.agent.model_config.get('provider')}/{r.agent.model_config.get('model')}"
                        if r.agent.model_config and r.agent.model_config.get("model") else None
                    ),
                }
                for r in self.agents.values()
            ],
            "conversation_history": self.conversation_history,
            "votes": {
                voter: {"target": v["target"], "target_name": self.agents[v["target"]].name if v["target"] in self.agents else v["target"]}
                for voter, v in self.votes.items()
            } if self.phase in (JubenshaPhase.VOTE, JubenshaPhase.REVEAL) else {},
            "reveal": self.reveal_result,
            "winner": self.winner,
        }
