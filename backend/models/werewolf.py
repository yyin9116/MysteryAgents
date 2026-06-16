"""
Werewolf game data models.
狼人杀游戏数据模型
"""

from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime


class WerewolfRole(str, Enum):
    """狼人杀角色"""
    WEREWOLF = "werewolf"      # 狼人
    VILLAGER = "villager"      # 村民
    SEER = "seer"              # 预言家
    WITCH = "witch"            # 女巫
    HUNTER = "hunter"          # 猎人
    GUARD = "guard"            # 守卫


class WerewolfFaction(str, Enum):
    """阵营"""
    WEREWOLF = "werewolf"      # 狼人阵营
    GOOD = "good"              # 好人阵营


class WerewolfPhase(str, Enum):
    """游戏阶段"""
    NIGHT = "night"                    # 夜晚
    DAWN = "dawn"                      # 天亮（公布死亡）
    DAY_DISCUSSION = "day_discussion"  # 白天讨论
    DAY_VOTING = "day_voting"          # 白天投票
    GAME_OVER = "game_over"            # 游戏结束


class NightActionType(str, Enum):
    """夜晚行动类型"""
    WEREWOLF_KILL = "werewolf_kill"    # 狼人击杀
    SEER_CHECK = "seer_check"          # 预言家查验
    WITCH_SAVE = "witch_save"          # 女巫救人
    WITCH_POISON = "witch_poison"      # 女巫毒人
    GUARD_PROTECT = "guard_protect"    # 守卫守护


class NightAction(BaseModel):
    """夜晚行动记录"""
    actor_id: str = Field(..., description="行动者 ID")
    action_type: NightActionType = Field(..., description="行动类型")
    target_id: Optional[str] = Field(None, description="目标 ID")
    result: Optional[str] = Field(None, description="行动结果")
    round: int = Field(..., description="回合数")


class WitchPotions(BaseModel):
    """女巫药水状态"""
    antidote: bool = Field(True, description="解药是否可用")
    poison: bool = Field(True, description="毒药是否可用")


class WerewolfAgentState(BaseModel):
    """狼人杀 Agent 状态"""
    agent_id: str = Field(..., description="Agent ID")
    name: Optional[str] = Field(None, description="显示名称")
    role: WerewolfRole = Field(..., description="角色")
    faction: WerewolfFaction = Field(..., description="阵营")
    is_alive: bool = Field(True, description="是否存活")
    is_possessed: bool = Field(False, description="是否被用户附身")

    # 角色特定状态
    witch_potions: Optional[WitchPotions] = Field(None, description="女巫药水状态")
    guard_last_protected: Optional[str] = Field(None, description="守卫上一晚守护的人")
    seer_checked_ids: List[str] = Field(default_factory=list, description="预言家已查验的人")
    seer_check_results: Dict[str, WerewolfFaction] = Field(
        default_factory=dict, description="预言家查验结果"
    )

    # 游戏数据
    vote_history: List[Dict[str, Any]] = Field(default_factory=list, description="投票历史")
    mbti_type: str = Field("INTJ", description="MBTI 类型")
    iq_level: str = Field("Mid", description="IQ 等级")


class WerewolfGameConfig(BaseModel):
    """游戏配置"""
    player_count: int = Field(8, ge=6, le=12, description="玩家数量")
    model_config_data: Optional[Dict[str, Any]] = Field(None, description="模型配置")


class WerewolfGameState(BaseModel):
    """狼人杀游戏状态"""
    model_config = ConfigDict(use_enum_values=True)

    game_id: str = Field(..., description="游戏 ID")
    phase: WerewolfPhase = Field(WerewolfPhase.NIGHT, description="当前阶段")
    current_round: int = Field(1, description="当前回合")

    # Agent 状态
    agents: Dict[str, WerewolfAgentState] = Field(default_factory=dict, description="所有 Agent 状态")

    # 夜晚行动
    night_actions: List[NightAction] = Field(default_factory=list, description="当晚行动记录")
    werewolf_kill_target: Optional[str] = Field(None, description="狼人击杀目标")

    # 对话历史
    conversation_history: List[Dict[str, Any]] = Field(default_factory=list, description="对话历史")

    # 死亡信息
    death_tonight: List[str] = Field(default_factory=list, description="今晚死亡名单")

    # 投票信息
    votes_this_round: Dict[str, str] = Field(default_factory=dict, description="本轮投票记录")
    speakers_this_round: List[str] = Field(default_factory=list, description="本轮已发言者")

    # 游戏结果
    winner: Optional[WerewolfFaction] = Field(None, description="获胜阵营")
    game_over_reason: Optional[str] = Field(None, description="游戏结束原因")

    # 时间戳
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")

# 角色分配配置
ROLE_DISTRIBUTION = {
    6: {WerewolfRole.WEREWOLF: 2, WerewolfRole.SEER: 1, WerewolfRole.WITCH: 1, WerewolfRole.VILLAGER: 2},
    7: {WerewolfRole.WEREWOLF: 2, WerewolfRole.SEER: 1, WerewolfRole.WITCH: 1, WerewolfRole.HUNTER: 1, WerewolfRole.VILLAGER: 2},
    8: {WerewolfRole.WEREWOLF: 2, WerewolfRole.SEER: 1, WerewolfRole.WITCH: 1, WerewolfRole.HUNTER: 1, WerewolfRole.GUARD: 1, WerewolfRole.VILLAGER: 2},
    9: {WerewolfRole.WEREWOLF: 3, WerewolfRole.SEER: 1, WerewolfRole.WITCH: 1, WerewolfRole.HUNTER: 1, WerewolfRole.GUARD: 1, WerewolfRole.VILLAGER: 2},
    10: {WerewolfRole.WEREWOLF: 3, WerewolfRole.SEER: 1, WerewolfRole.WITCH: 1, WerewolfRole.HUNTER: 1, WerewolfRole.GUARD: 1, WerewolfRole.VILLAGER: 3},
    11: {WerewolfRole.WEREWOLF: 3, WerewolfRole.SEER: 1, WerewolfRole.WITCH: 1, WerewolfRole.HUNTER: 1, WerewolfRole.GUARD: 1, WerewolfRole.VILLAGER: 4},
    12: {WerewolfRole.WEREWOLF: 4, WerewolfRole.SEER: 1, WerewolfRole.WITCH: 1, WerewolfRole.HUNTER: 1, WerewolfRole.GUARD: 1, WerewolfRole.VILLAGER: 4},
}


def get_faction(role: WerewolfRole) -> WerewolfFaction:
    """获取角色所属阵营"""
    if role == WerewolfRole.WEREWOLF:
        return WerewolfFaction.WEREWOLF
    return WerewolfFaction.GOOD


def get_role_name_cn(role: WerewolfRole) -> str:
    """获取角色中文名"""
    names = {
        WerewolfRole.WEREWOLF: "狼人",
        WerewolfRole.VILLAGER: "村民",
        WerewolfRole.SEER: "预言家",
        WerewolfRole.WITCH: "女巫",
        WerewolfRole.HUNTER: "猎人",
        WerewolfRole.GUARD: "守卫",
    }
    return names.get(role, "未知")


class GameEventType(str, Enum):
    """游戏事件类型"""
    PHASE_CHANGE = "phase_change"
    NIGHT_ACTION = "night_action"
    DISCUSSION = "discussion"
    VOTE = "vote"
    ELIMINATION = "elimination"
    DEATH_ANNOUNCEMENT = "death_announcement"
    GAME_OVER = "game_over"


class GameEvent(BaseModel):
    """游戏事件"""
    event_id: str = Field(..., description="事件 ID")
    timestamp: datetime = Field(..., description="事件时间戳")
    event_type: GameEventType = Field(..., description="事件类型")
    round: int = Field(..., description="回合数")
    phase: WerewolfPhase = Field(..., description="阶段")
    data: Dict[str, Any] = Field(default_factory=dict, description="事件数据")
    game_state_snapshot: Optional[Dict[str, Any]] = Field(None, description="游戏状态快照")
