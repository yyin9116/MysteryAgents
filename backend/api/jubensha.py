"""
Jubensha (剧本杀) API endpoints.

- 剧本包导入 / 校验 / 列表（ScriptPack JSON，兼容 ThinkThrice 数据结构）
- 对局创建 / 状态 / 删除 / 导出
- 夺席代打与玩家投票
"""

import json
import logging
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from models.jubensha import (
    JubenshaPhase,
    ScriptPack,
    normalize_script_pack,
    script_pack_to_json,
    validate_script_pack,
)
from services.jubensha_service import JubenshaService, _get_replay_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/jubensha", tags=["jubensha"])

# Active games（与狼人杀 active_werewolf_games 同模式）
active_jubensha_games: Dict[str, JubenshaService] = {}

# 内置剧本目录：backend/scripts/
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


def _scan_builtin_scripts() -> List[Dict[str, Any]]:
    """扫描内置剧本目录，返回轻量 meta 列表。"""
    items: List[Dict[str, Any]] = []
    if not SCRIPTS_DIR.exists():
        return items
    for file_path in sorted(SCRIPTS_DIR.glob("*.json")):
        try:
            raw = json.loads(file_path.read_text(encoding="utf-8"))
            pack = ScriptPack(**raw)
            items.append({
                "script_id": pack.script_id,
                "title": pack.meta.title,
                "player_count": pack.meta.player_count,
                "difficulty": pack.meta.difficulty,
                "estimated_minutes": pack.meta.estimated_minutes,
                "tags": pack.meta.tags,
                "source": pack.meta.source,
                "builtin": True,
            })
        except Exception as exc:
            logger.warning("Skip invalid builtin script %s: %s", file_path.name, exc)
    return items


def _load_script_pack(script_id: str) -> ScriptPack:
    """按 script_id 加载剧本：内置目录优先，其次用户导入（内存注册）。"""
    safe = Path(script_id).name
    file_path = SCRIPTS_DIR / f"{safe}.json"
    if file_path.exists():
        raw = json.loads(file_path.read_text(encoding="utf-8"))
        return normalize_script_pack(raw)
    registered = _imported_scripts.get(script_id)
    if registered:
        return registered
    raise HTTPException(status_code=404, detail=f"Script not found: {script_id}")


# 用户导入的剧本（内存注册；重启后需重新导入，内置剧本持久化在 scripts/ 目录）
_imported_scripts: Dict[str, ScriptPack] = {}


def _register_imported_script(pack: ScriptPack, save: bool) -> Optional[str]:
    """Register an imported pack without replacing existing built-in content."""
    script_id = pack.script_id
    if Path(script_id).name != script_id or script_id in {".", ".."}:
        raise HTTPException(status_code=400, detail="script_id 只能包含文件名字符")
    if script_id in _imported_scripts or (SCRIPTS_DIR / f"{script_id}.json").exists():
        raise HTTPException(status_code=409, detail=f"Script already exists: {script_id}")

    saved_path = None
    if save:
        SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
        out = SCRIPTS_DIR / f"{script_id}.json"
        out.write_text(script_pack_to_json(pack), encoding="utf-8")
        saved_path = str(out)
    _imported_scripts[script_id] = pack
    return saved_path


# ---------------------------------------------------------------------- #
# Requests
# ---------------------------------------------------------------------- #

class ImportScriptRequest(BaseModel):
    """导入剧本包：pack 为 ScriptPack JSON；save=True 时同时落盘到内置目录。"""
    pack: Dict[str, Any]
    save: bool = False


class AutoModelAssignRequest(BaseModel):
    candidates: List[str] = Field(default_factory=list)
    disabled_models: List[str] = Field(default_factory=list)
    effort_by_role: bool = True


class CreateGameRequest(BaseModel):
    script_id: str
    model_config_data: Optional[Dict[str, Any]] = None
    agent_model_configs: Optional[List[Optional[Dict[str, Any]]]] = None
    chat_style: str = Field("speech", pattern="^(speech|group_chat)$")
    runtime: str = Field("agentscope", pattern="^(legacy|agentscope)$")
    auto_model_assign: Optional[AutoModelAssignRequest] = None
    player_mode: str = Field("spectate", pattern="^(spectate|participate)$")
    player_char_id: Optional[str] = None


class PlayerSpeechRequest(BaseModel):
    game_id: str
    char_id: str
    content: str = Field(..., min_length=1, max_length=500)


class PlayerVoteRequest(BaseModel):
    game_id: str
    char_id: str
    target_char_id: str
    reason: str = Field("", max_length=500)


# ---------------------------------------------------------------------- #
# Scripts
# ---------------------------------------------------------------------- #

@router.post("/import")
async def import_script(request: ImportScriptRequest):
    """导入并校验剧本包，返回校验报告；save=True 时持久化到内置目录。"""
    report = validate_script_pack(request.pack)
    if not report["ok"]:
        raise HTTPException(status_code=400, detail={"message": "剧本包校验失败", **report})
    pack = normalize_script_pack(request.pack)
    saved_path = _register_imported_script(pack, request.save)
    return {"success": True, "report": report, "saved_path": saved_path}


@router.get("/scripts")
async def list_scripts():
    """剧本列表 = 内置目录 + 本次运行中导入的剧本。"""
    items = _scan_builtin_scripts()
    seen = {item["script_id"] for item in items}
    for script_id, pack in _imported_scripts.items():
        if script_id in seen:
            continue
        items.append({
            "script_id": pack.script_id,
            "title": pack.meta.title,
            "player_count": pack.meta.player_count,
            "difficulty": pack.meta.difficulty,
            "estimated_minutes": pack.meta.estimated_minutes,
            "tags": pack.meta.tags,
            "source": pack.meta.source,
            "builtin": False,
        })
    return {"scripts": items, "total": len(items)}


@router.get("/scripts/{script_id}")
async def get_script(script_id: str):
    """剧本详情；公开接口始终隐藏真相与角色私密剧本。"""
    pack = _load_script_pack(script_id)
    data = pack.model_dump(mode="json")
    data["truth"] = {"murderer": None, "timeline": [], "case_replay": ""}
    # 私密剧本永不批量下发
    for char in data.get("characters", []):
        char["script"] = ""
        char["secret_knowledge"] = []
    return data


@router.delete("/scripts/{script_id}")
async def delete_script(script_id: str):
    """删除用户导入的剧本（内置剧本不可删）。"""
    safe = Path(script_id).name
    file_path = SCRIPTS_DIR / f"{safe}.json"
    if file_path.exists():
        raise HTTPException(status_code=400, detail="内置剧本不可删除")
    if script_id in _imported_scripts:
        del _imported_scripts[script_id]
        return {"success": True, "script_id": script_id}
    raise HTTPException(status_code=404, detail=f"Script not found: {script_id}")


# ---------------------------------------------------------------------- #
# Games
# ---------------------------------------------------------------------- #

@router.post("/create")
async def create_game(request: CreateGameRequest):
    """创建剧本杀对局（LOBBY 阶段，等待事件流启动）。"""
    try:
        pack = _load_script_pack(request.script_id)
        game_id = f"jubensha_{uuid.uuid4().hex[:8]}"
        service = JubenshaService(
            game_id=game_id,
            script_pack=pack,
            model_config=request.model_config_data,
            agent_model_configs=request.agent_model_configs,
            game_config={"chat_style": request.chat_style, "runtime": request.runtime},
            auto_model_plan=request.auto_model_assign.model_dump() if request.auto_model_assign else None,
            player_mode=request.player_mode,
            player_char_id=request.player_char_id,
        )
        active_jubensha_games[game_id] = service
        state = service.get_game_state()
        # 返回玩家自己的私密剧本（参与模式）
        my_script = None
        if service.player_mode == "participate" and service.player_char_id:
            runtime = service.get_runtime(service.player_char_id)
            if runtime:
                my_script = {
                    "char_id": runtime.char_id,
                    "name": runtime.name,
                    "public_profile": runtime.char.public_profile,
                    "script": runtime.char.script,
                    "mission": runtime.char.mission,
                    "secret_knowledge": runtime.char.secret_knowledge,
                    "camp": runtime.char.camp.value,
                }
        return {"success": True, "game_id": game_id, **state, "my_script": my_script}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to create jubensha game")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/game/{game_id}")
async def get_game_state(game_id: str):
    service = active_jubensha_games.get(game_id)
    if not service:
        raise HTTPException(status_code=404, detail=f"Game not found: {game_id}")
    return {"success": True, **service.get_game_state()}


@router.delete("/game/{game_id}")
async def delete_game(game_id: str):
    from services.game_broker import game_broker

    if game_id in active_jubensha_games:
        game_broker.discard(game_id)
        del active_jubensha_games[game_id]
        return {"success": True, "game_id": game_id}
    if game_broker.has_game(game_id):
        game_broker.discard(game_id)
        return {"success": True, "game_id": game_id}
    raise HTTPException(status_code=404, detail=f"Game not found: {game_id}")


@router.post("/player-speech")
async def player_speech(request: PlayerSpeechRequest):
    """夺席：玩家为接管的角色提交公开发言。"""
    service = active_jubensha_games.get(request.game_id)
    if not service:
        raise HTTPException(status_code=404, detail=f"Game not found: {request.game_id}")
    try:
        return service.submit_player_speech(request.char_id, request.content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/player-vote")
async def player_vote(request: PlayerVoteRequest):
    """参与模式：玩家为接管的角色提交投票。"""
    service = active_jubensha_games.get(request.game_id)
    if not service:
        raise HTTPException(status_code=404, detail=f"Game not found: {request.game_id}")
    if not service.get_runtime(request.char_id):
        raise HTTPException(status_code=400, detail=f"Invalid voter: {request.char_id}")
    if not service.get_runtime(request.target_char_id):
        raise HTTPException(status_code=400, detail=f"Invalid target: {request.target_char_id}")
    service.votes[request.char_id] = {
        "target": request.target_char_id,
        "reason": request.reason or "（由玩家本人指认）",
        "confidence": 1.0,
    }
    return {"success": True, "queued": True}


# ---------------------------------------------------------------------- #
# Replay / Export
# ---------------------------------------------------------------------- #

@router.get("/replay/{game_id}")
async def get_replay(game_id: str):
    service = active_jubensha_games.get(game_id)
    if service:
        return service.to_replay_dict()
    try:
        return _get_replay_store().load_replay(game_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Game not found: {game_id}")


@router.get("/replay/{game_id}/export")
async def export_replay(game_id: str):
    """导出对局回放 JSON（含 ScriptPack 元信息，可作为数据集样本）。"""
    service = active_jubensha_games.get(game_id)
    try:
        replay = service.to_replay_dict() if service else _get_replay_store().load_replay(game_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Game not found: {game_id}")
    return Response(
        content=json.dumps(replay, ensure_ascii=False, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{game_id}-replay.json"'},
    )


@router.get("/replays")
async def list_replays():
    store = _get_replay_store()
    items = store.list_replays()
    for item in items:
        item["is_active"] = item["game_id"] in active_jubensha_games
    return {"replays": items, "total": len(items)}


# ---------------------------------------------------------------------- #
# 智能体评估（MIRAGE 风格指标）
# ---------------------------------------------------------------------- #

@router.post("/game/{game_id}/evaluate")
async def evaluate_game(game_id: str):
    """对本局生成评估报告：TII/CIC/ICI/MRR 统计指标 + LLM 五维能力与 SCI 打分。"""
    from services.jubensha_eval import run_evaluation

    service = active_jubensha_games.get(game_id)
    if not service:
        raise HTTPException(status_code=404, detail=f"Game not found or already cleaned: {game_id}")
    if not service.agents:
        raise HTTPException(status_code=400, detail="No agents to evaluate")
    if service.evaluation:
        return {"success": True, "cached": True, "evaluation": service.evaluation}
    evaluation = await run_evaluation(service)
    service.evaluation = evaluation
    service._persist_replay()
    return {"success": True, "cached": False, "evaluation": evaluation}


# ---------------------------------------------------------------------- #
# AI 即兴创作（improv）
# ---------------------------------------------------------------------- #

class ImprovRequest(BaseModel):
    idea: str = Field(..., min_length=2, max_length=600, description="玩家的天马行空设定")
    player_count: int = Field(6, ge=3, le=10)
    model_config_data: Optional[Dict[str, Any]] = None
    save: bool = True


_IMPROV_SYSTEM = (
    "你是资深剧本杀编剧。根据用户的设定，创作一个可直接开局的剧本杀剧本包。"
    "要求：单一真凶；每个角色有私密剧本（背景故事+案发当晚行动+需要隐瞒的秘密）；"
    "真凶剧本需含作案手法但不直白认罪；线索要能渐进逼近真相；文案有代入感。"
)

_IMPROV_PROMPT = """用户设定：{idea}
玩家人数：{n}

请输出 JSON（不要其他文字）：
{{
  "meta": {{"title": "剧本名（8字内）", "difficulty": "standard", "estimated_minutes": 60,
             "tags": ["2-4个标签"], "language": "zh", "source": "improv"}},
  "truth": {{"murderer": "<真凶角色名，必须与characters中的name完全一致>",
              "timeline": [{{"time": "时间", "event": "事件"}}],
              "case_replay": "完整案件复盘（150-300字）"}},
  "host_manual": {{"intro": "开场白（100字内，交代背景与命案）", "stages": []}},
  "characters": [
    {{"name": "角色名", "age": 30, "public_profile": "公开身份一句话",
      "script": "私密剧本（250-500字：背景/性格/与他人关系/案发当晚行动）",
      "mission": "本局任务", "camp": "civilian 或 murderer（恰好1名murderer）",
      "secret_knowledge": ["知道的秘密1", "..."]}}
  ],
  "clues": [
    {{"clue_id": "clue_001", "title": "线索名", "content": "线索描述（可被搜出指认真相）",
      "distribution": {{"round": 1, "pool": null}}}}
  ]
}}

硬性要求：
- 恰好 {n} 个角色，char 索引从 01 开始生成 char_id："c01"..."c{n:02d}"；
- clues 至少 {clue_min} 条，clue_id 唯一；
- truth.murderer 必须是某角色的 name；camp 为 murderer 的角色恰好 1 名且与 truth.murderer 一致；
- distribution.pool 留 null（公共池），round 用 1 或 2。"""


@router.post("/improv")
async def improv_script(request: ImprovRequest):
    """AI 即兴创作：根据玩家想法生成 ScriptPack，校验通过后可直接开局。"""
    from services.llm_service import LLMService

    llm = LLMService()
    clue_min = request.player_count * 2
    prompt = _IMPROV_PROMPT.format(
        idea=request.idea, n=request.player_count, clue_min=clue_min,
    )
    last_errors: List[str] = []
    for attempt in range(3):
        try:
            raw = await llm.generate(
                prompt if attempt == 0 else prompt + "\n\n注意：上次输出未通过校验：" + "；".join(last_errors[:3]),
                system_prompt=_IMPROV_SYSTEM,
                model_config=request.model_config_data,
                temperature=0.9 if attempt == 0 else 0.6,
                max_tokens=8000,
                session_id="improv",
            )
            pack_raw = llm._extract_json_from_text(raw) if isinstance(raw, str) else raw
            if isinstance(pack_raw, str):
                pack_raw = json.loads(pack_raw)
            if not isinstance(pack_raw, dict):
                raise ValueError("model did not return a JSON object")
            # 补齐生成器易漏的骨架字段
            pack_raw.setdefault("script_id", f"improv_{uuid.uuid4().hex[:8]}")
            pack_raw.setdefault("schema_version", 1)
            pack_raw.setdefault("host_manual", {"intro": "", "stages": []})
            for i, ch in enumerate(pack_raw.get("characters", [])):
                ch.setdefault("char_id", f"c{i + 1:02d}")
            report = validate_script_pack(pack_raw)
            if not report["ok"]:
                last_errors = report["errors"]
                continue
            pack = normalize_script_pack(pack_raw)
            break
        except Exception as exc:
            last_errors = [str(exc)]
            continue
    else:
        raise HTTPException(status_code=502, detail={"message": "AI 创作未能生成合法剧本，请调整设定后重试", "errors": last_errors})

    saved_path = _register_imported_script(pack, request.save)
    summary = {
        "script_id": pack.script_id,
        "title": pack.meta.title,
        "player_count": pack.meta.player_count,
        "difficulty": pack.meta.difficulty,
        "tags": pack.meta.tags,
        "source": pack.meta.source,
        "builtin": False,
    }
    return {"success": True, "report": report, "saved_path": saved_path, "script": summary}
