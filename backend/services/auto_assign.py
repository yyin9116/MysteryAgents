"""跨游戏共享的角色阵容与智能模型分配助手。

狼人杀 / 谁是卧底 / 辩论会统一使用：
- apply_roster: 把主题阵容（名字+MBTI+性别）套到已创建的 agents 上
- apply_auto_assign: 按强度分档自动分配模型 + 思考强度

tier 约定：0 = 最强推理（核心角色），1 = 中等，2 = 轻量。
狼人杀按角色分档（见 WerewolfService._ROLE_TIER）；
卧底/辩论没有角色体系，按 IQ 分档（High→0，Mid→1，Low→2）。
"""

import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

_IQ_TIER = {"High": 0, "Mid": 1, "Low": 2}
_TIER_EFFORT = {0: "high", 1: "medium", 2: "low"}


def normalize_roster(roster: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """复用狼人杀的阵容规范化（去 emoji、统一译名分隔符、剔重名/坏 MBTI）。"""
    from services.werewolf_service import WerewolfService

    return WerewolfService._normalize_roster(roster)


def apply_roster(agents: List[Any], roster: Optional[List[Dict[str, Any]]]) -> int:
    """把阵容套到 agents 上（名字 + MBTI），返回成功覆盖的数量。

    agents 顺序即阵容顺序；roster 比 agents 短时只覆盖前缀。
    """
    if not roster:
        return 0
    applied = 0
    for i, agent in enumerate(agents):
        if i >= len(roster):
            break
        entry = roster[i]
        try:
            agent.config.name = entry["name"]
            agent.config.mbti_type = entry["mbti"]
            applied += 1
        except AttributeError:
            logger.warning("apply_roster: agent at index %s has no config, skipped", i)
    logger.info("Roster applied to %s/%s agents", applied, len(agents))
    return applied


def apply_auto_assign(
    agents: List[Any],
    plan: Optional[Dict[str, Any]],
    base_config: Optional[Dict[str, Any]],
    tier_of: Callable[[Any], int],
) -> int:
    """按 tier 分档给 agents 分配模型 + 思考强度，返回成功分配的数量。

    plan: {candidates, disabled_models, blacklist, effort_by_role}
    与狼人杀同一套强度排序与分档池：tier0 从最强端取，tier2 从最弱端取，
    tier1 取中段；池子不够时循环取用。
    """
    from services.werewolf_service import WerewolfService

    if not plan or not base_config:
        return 0
    candidates = WerewolfService._filter_candidate_models(
        plan.get("candidates"),
        plan.get("blacklist"),
        plan.get("disabled_models"),
    )
    if not candidates:
        logger.warning("Auto assign skipped: no usable candidates after filtering")
        return 0

    ranked = sorted(candidates, key=WerewolfService._rank_model_strength, reverse=True)
    mid = len(ranked) // 3
    pools: Dict[int, List[str]] = {
        0: ranked,
        1: ranked[mid:] if len(ranked) >= 3 else ranked,
        2: list(reversed(ranked)),
    }
    effort_by_role = bool(plan.get("effort_by_role", True))
    cursors = {0: 0, 1: 0, 2: 0}
    applied = 0
    for agent in agents:
        try:
            tier = tier_of(agent)
        except Exception:
            tier = 1
        tier = max(0, min(2, tier))
        pool = pools[tier]
        model = pool[cursors[tier] % len(pool)]
        cursors[tier] += 1

        merged = dict(base_config)
        merged["model"] = model
        if effort_by_role:
            extra = dict(merged.get("extra_params") or {})
            extra["reasoning_effort"] = _TIER_EFFORT[tier]
            merged["extra_params"] = extra
        agent.model_config = merged
        applied += 1
    logger.info("Auto assign applied to %s agents", applied)
    return applied


def iq_tier_of(agent: Any) -> int:
    """卧底/辩论的默认分档：按 IQ 等级。"""
    value = getattr(getattr(agent, "config", None), "iq_level", None)
    raw = getattr(value, "value", value)
    return _IQ_TIER.get(str(raw), 1)
