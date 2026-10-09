"""
Jubensha (剧本杀) data models.

ScriptPack 是剧本杀模式的核心数据格式：
- 每局一个 JSON 包，兼容 ThinkThrice Jubensha Dataset 的 characters/clues/truth 结构；
- truth / characters[].script / secret_knowledge 属私密数据，运行时按 char_id 隔离注入，
  SSE 永不广播；
- clues[].distribution.pool 省略时对全员可见。

另提供导入校验（validate_script_pack）与规范化（normalize_script_pack）。
"""

from enum import Enum
from typing import Any, Dict, List, Optional
import json

from pydantic import BaseModel, Field, ValidationError


class JubenshaPhase(str, Enum):
    LOBBY = "lobby"          # 已创建待开始
    READING = "reading"      # 读本
    CLUE = "clue"            # 线索发放
    DISCUSSION = "discussion"
    VOTE = "vote"
    REVEAL = "reveal"        # 复盘结算


class CharacterCamp(str, Enum):
    CIVILIAN = "civilian"
    MURDERER = "murderer"


class TimelineEntry(BaseModel):
    time: str = ""
    event: str


class Truth(BaseModel):
    """上帝视角：仅主持人/结算可见，绝不进入玩家 agent 的公开上下文。"""
    murderer: Optional[str] = None          # 真凶 char_id（开放结局可空）
    timeline: List[TimelineEntry] = Field(default_factory=list)
    case_replay: str = ""                    # 完整案件复盘文本


class HostStage(BaseModel):
    stage_id: str
    type: str = Field(..., pattern="^(reading|clue_round|discussion|vote)$")
    rounds: Optional[int] = None             # discussion 阶段轮数
    clues_per_player: Optional[int] = None   # clue_round 阶段每人线索数
    note: str = ""


class HostManual(BaseModel):
    intro: str = ""
    stages: List[HostStage] = Field(default_factory=list)


class CharacterScript(BaseModel):
    char_id: str
    name: str
    age: Optional[int] = None
    mbti: Optional[str] = None               # 可选，接入现有 persona 体系
    public_profile: str = ""                 # 公开身份（全员可见）
    script: str = ""                         # 私密剧本（仅本人可见）
    mission: str = ""                        # 本人任务
    camp: CharacterCamp = CharacterCamp.CIVILIAN
    secret_knowledge: List[str] = Field(default_factory=list)  # 已知秘密


class ClueDistribution(BaseModel):
    round: int = 1
    pool: Optional[str] = None               # 逗号分隔 char_id；空 = 全员


class Clue(BaseModel):
    clue_id: str
    title: str = ""
    content: str
    media: Dict[str, Any] = Field(default_factory=lambda: {"type": "text", "url": None})
    distribution: ClueDistribution = Field(default_factory=ClueDistribution)


class ScriptMeta(BaseModel):
    title: str
    player_count: int = Field(..., ge=2, le=20)
    difficulty: str = Field("standard", pattern="^(easy|standard|hard)$")
    estimated_minutes: int = 60
    tags: List[str] = Field(default_factory=list)
    language: str = "zh"
    source: str = "local"


class ScriptPack(BaseModel):
    script_id: str = Field(..., min_length=2, max_length=64)
    schema_version: int = 1
    meta: ScriptMeta
    truth: Truth = Field(default_factory=Truth)
    host_manual: HostManual = Field(default_factory=HostManual)
    characters: List[CharacterScript]
    clues: List[Clue] = Field(default_factory=list)


# ---------------------------------------------------------------------- #
# 导入校验
# ---------------------------------------------------------------------- #

def validate_script_pack(raw: Dict[str, Any]) -> Dict[str, Any]:
    """校验剧本包 JSON，返回 {ok, errors, warnings, script_id}。

    errors 非空表示不可导入；warnings 仅提示。
    """
    errors: List[str] = []
    warnings: List[str] = []

    pack: Optional[ScriptPack] = None
    try:
        pack = ScriptPack(**(raw or {}))
    except ValidationError as exc:
        for err in exc.errors():
            loc = ".".join(str(p) for p in err.get("loc", []))
            errors.append(f"{loc or 'root'}: {err.get('msg', 'invalid')}")
        return {"ok": False, "errors": errors, "warnings": warnings, "script_id": str((raw or {}).get("script_id") or "")}

    characters = pack.characters
    char_ids = [c.char_id for c in characters]

    # 角色校验
    if len(set(char_ids)) != len(char_ids):
        errors.append("characters: char_id 重复")
    if len(set(c.name for c in characters)) != len(characters):
        errors.append("characters: 角色名重复")
    murderers = [c for c in characters if c.camp == CharacterCamp.MURDERER]
    if len(murderers) > 1:
        errors.append("characters: murderer 阵营角色超过 1 名")
    if pack.meta.player_count != len(characters):
        warnings.append(
            f"meta.player_count={pack.meta.player_count} 与角色数 {len(characters)} 不一致，以角色数为准"
        )

    # truth.murderer 必须指向存在且为 murderer 阵营的角色
    if pack.truth.murderer:
        if pack.truth.murderer not in char_ids:
            errors.append(f"truth.murderer: 指向不存在的角色 {pack.truth.murderer}")
        elif next(c for c in characters if c.char_id == pack.truth.murderer).camp != CharacterCamp.MURDERER:
            errors.append("truth.murderer: 该角色不是 murderer 阵营")
    elif murderers:
        warnings.append("truth.murderer 未指定，但存在 murderer 阵营角色；结算将无法校验凶手")

    # 线索池引用校验
    valid_ids = set(char_ids)
    for clue in pack.clues:
        pool = clue.distribution.pool
        if pool:
            for token in [t.strip() for t in pool.split(",") if t.strip()]:
                if token not in valid_ids:
                    errors.append(f"clues[{clue.clue_id}].distribution.pool: 未知角色 {token}")

    # 线索量提示
    clue_rounds = sorted({c.distribution.round for c in pack.clues})
    if not pack.clues:
        warnings.append("没有任何线索：对局将跳过线索阶段")
    total_round_clues = len(pack.clues)
    if characters and total_round_clues < len(characters):
        warnings.append(f"线索数量（{total_round_clues}）少于角色数（{len(characters)}），部分玩家可能拿不到线索")

    # host_manual 阶段校验
    stage_types = [s.type for s in pack.host_manual.stages]
    if "discussion" not in stage_types:
        warnings.append("host_manual 缺少 discussion 阶段，将使用默认流程")
    if "vote" not in stage_types:
        warnings.append("host_manual 缺少 vote 阶段，将使用默认流程")

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "script_id": pack.script_id,
    }


def normalize_script_pack(raw: Dict[str, Any]) -> ScriptPack:
    """规范化剧本包：以实际角色数覆盖 player_count。"""
    pack = ScriptPack(**(raw or {}))
    if pack.meta.player_count != len(pack.characters):
        pack.meta.player_count = len(pack.characters)
    return pack


def script_pack_to_json(pack: ScriptPack) -> str:
    """导出为可直接再导入的 JSON 文本。"""
    return json.dumps(pack.model_dump(mode="json"), ensure_ascii=False, indent=2)
