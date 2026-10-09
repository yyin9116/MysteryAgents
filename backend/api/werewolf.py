"""
Werewolf game API endpoints.
狼人杀游戏 API
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from typing import Dict, Optional, Any, List
import json
import logging
import uuid

from services.werewolf_service import WerewolfService
from services.werewolf_report_service import werewolf_report_service
from services.werewolf_replay_store import werewolf_replay_store
from services.game_broker import game_broker
from models.werewolf import (
    WerewolfGameConfig, WerewolfGameState, NightActionType,
    WerewolfPhase, WerewolfRole
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/werewolf", tags=["werewolf"])

# Active games storage
active_werewolf_games: Dict[str, WerewolfService] = {}


def _enum_value(value: Any) -> Any:
    """Return enum value when present, otherwise raw value."""
    return value.value if hasattr(value, "value") else value


class RosterEntry(BaseModel):
    """主题角色阵容中的单个角色（名字 + MBTI + 性别绑定）。"""
    name: str = Field(..., min_length=1, max_length=15)
    mbti: str = Field(..., min_length=4, max_length=4)
    gender: str = Field("男", max_length=4)


class AutoModelAssignRequest(BaseModel):
    """智能模型分配计划：候选模型 + 黑名单 + 按角色注入思考强度。

    candidates 来自前端实时拉取的在线模型列表（通常已应用黑名单预览），
    后端在开局时按角色强度分档分配（狼人/神职最强 → 猎人/守卫 → 村民），
    并对推理系模型按角色注入 reasoning_effort（high/medium/low）。
    """
    candidates: List[str] = Field(default_factory=list, description="候选模型列表（在线目录）")
    disabled_models: List[str] = Field(default_factory=list, description="禁用模型列表（完整模型 id，精确匹配）")
    blacklist: List[str] = Field(default_factory=list, description="旧版关键字黑名单（子串匹配，兼容保留）")
    effort_by_role: bool = Field(True, description="是否按角色注入思考强度")


class CreateGameRequest(BaseModel):
    """Request to create a new werewolf game."""
    player_count: int = Field(..., ge=6, le=12, description="玩家数量 (6-12)")
    model_config_data: Optional[Dict[str, Any]] = Field(None, description="模型配置（全场默认）")
    agent_model_configs: Optional[List[Optional[Dict[str, Any]]]] = Field(
        None,
        description="按玩家槽位覆盖模型配置；index i 对应 werewolf_agent_{i+1}，null 表示继承全场默认",
    )
    llm_naming: bool = Field(False, description="是否用 LLM 生成个性化昵称（前端默认开启）")
    fast_mode: bool = Field(False, description="是否启用快测模式")
    discussion_turn_limit: Optional[int] = Field(None, ge=1, le=12, description="每个白天最多发言人数")
    chat_style: str = Field(
        "speech",
        pattern="^(speech|group_chat)$",
        description="讨论风格：speech=圆桌完整发言；group_chat=QQ/微信群聊短消息气泡",
    )
    auto_model_assign: Optional[AutoModelAssignRequest] = Field(
        None,
        description="智能模型分配计划；提供时按角色自动挑选候选模型并注入思考强度",
    )
    roster: Optional[List[RosterEntry]] = Field(
        None,
        description="主题角色阵容（来自 /roster/preview）；提供时玩家名字与 MBTI 按此绑定，并跳过 LLM 改名",
    )
    roster_work: Optional[str] = Field(
        None,
        description="阵容角色来源作品名（如 西游记）；用于让公开发言带入角色经典气质",
    )
    player_mode: str = Field(
        "spectate",
        pattern="^(spectate|participate)$",
        description="参与模式：spectate=围观 AI 对局；participate=玩家接管一个席位参与",
    )
    player_agent_id: Optional[str] = Field(
        None,
        description="参与模式下玩家接管的席位 ID；缺省为 werewolf_agent_1",
    )


class CreateGameResponse(BaseModel):
    """Response for game creation."""
    game_id: str
    player_count: int
    agents: List[Dict[str, Any]]
    message: str


class NightActionRequest(BaseModel):
    """Request for night action."""
    game_id: str = Field(..., description="游戏 ID")
    agent_id: str = Field(..., description="行动者 ID")
    action_type: NightActionType = Field(..., description="行动类型")
    target_id: Optional[str] = Field(None, description="目标 ID")


class VoteRequest(BaseModel):
    """Request for voting."""
    game_id: str = Field(..., description="游戏 ID")
    voter_id: str = Field(..., description="投票者 ID")
    target_id: str = Field(..., description="投票目标 ID")


class PlayerSpeechRequest(BaseModel):
    """Request for a player-controlled (夺席) speech."""
    game_id: str = Field(..., description="游戏 ID")
    agent_id: str = Field(..., description="被接管的玩家 ID")
    content: str = Field(..., min_length=1, max_length=500, description="玩家代打的公开发言内容")


class GameStateResponse(BaseModel):
    """Response with game state."""
    game_id: str
    phase: str
    current_round: int
    agents: Dict[str, Any]
    alive_count: int


class RosterPreviewRequest(BaseModel):
    """Request to preview a themed roster for the given work."""
    work: str = Field(..., min_length=1, max_length=50, description="作品名，如 西游记 / 荒野大镖客 2")
    count: int = Field(..., ge=6, le=12, description="角色数量")
    model_config_data: Optional[Dict[str, Any]] = Field(None, description="用于生成阵容的模型配置")


@router.post("/roster/preview")
async def preview_roster(request: RosterPreviewRequest):
    """按用户输入的作品生成主题角色阵容（名字 + MBTI + 性别绑定）。"""
    from services.llm_service import LLMService

    try:
        llm = LLMService()
        roster = await llm.generate_themed_roster(
            work=request.work,
            count=request.count,
            session_id=f"roster:{uuid.uuid4().hex[:6]}",
            model_config=request.model_config_data,
        )
        return {"success": True, "work": request.work.strip(), "roster": roster}
    except Exception as exc:
        logger.error("Failed to preview roster: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/create", response_model=CreateGameResponse)
async def create_game(request: CreateGameRequest):
    """
    Create a new werewolf game.

    Creates agents with assigned roles based on player count.
    """
    try:
        # Generate game ID
        game_id = f"werewolf_{uuid.uuid4().hex[:8]}"

        # Create game service
        roster_payload = [entry.model_dump() for entry in request.roster] if request.roster else None
        game_service = WerewolfService(
            game_id=game_id,
            player_count=request.player_count,
            model_config=request.model_config_data,
            agent_model_configs=request.agent_model_configs,
            game_config={
                "fast_mode": request.fast_mode,
                "discussion_turn_limit": request.discussion_turn_limit,
                "chat_style": request.chat_style,
            },
            roster=roster_payload,
            roster_work=request.roster_work,
            auto_model_plan=request.auto_model_assign.model_dump() if request.auto_model_assign else None,
            player_mode=request.player_mode,
            player_agent_id=request.player_agent_id,
        )

        # LLM 个性化昵称：并发生成，失败自动回落角色库名字；
        # 主题阵容已带统一命名的角色（名-MBTI 绑定），跳过改名避免破坏主题
        if request.llm_naming and not roster_payload:
            try:
                await game_service.apply_llm_agent_names()
            except Exception as exc:
                logger.warning("LLM agent naming skipped for %s: %s", game_id, exc)

        # Store game
        active_werewolf_games[game_id] = game_service

        # Build agent list for response (without revealing roles)
        agents = []
        for agent_id, agent_state in game_service.state.agents.items():
            agents.append({
                "agent_id": agent_id,
                "name": agent_state.name,
                "mbti_type": agent_state.mbti_type,
                "iq_level": agent_state.iq_level,
                "model_label": agent_state.model_label,
                "is_alive": agent_state.is_alive
                # Note: role is NOT included to keep it secret
            })

        logger.info(f"Created werewolf game {game_id} with {request.player_count} players")

        return CreateGameResponse(
            game_id=game_id,
            player_count=request.player_count,
            agents=agents,
            message=f"狼人杀游戏创建成功，{request.player_count}名玩家"
        )

    except Exception as e:
        logger.error(f"Failed to create werewolf game: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/night-action")
async def night_action(request: NightActionRequest):
    """
    Execute a night action.

    Supports:
    - Werewolf kill
    - Seer check
    - Witch save/poison
    - Guard protect
    """
    try:
        # Get game
        game_service = active_werewolf_games.get(request.game_id)
        if not game_service:
            raise HTTPException(status_code=404, detail=f"Game not found: {request.game_id}")

        # Validate phase
        if game_service.state.phase != WerewolfPhase.NIGHT:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot perform night action in phase: {_enum_value(game_service.state.phase)}"
            )

        # Execute action based on type
        result = None

        if request.action_type == NightActionType.WEREWOLF_KILL:
            if not request.target_id:
                raise HTTPException(status_code=400, detail="Target ID required for werewolf kill")
            result = game_service.werewolf_kill(request.agent_id, request.target_id)

        elif request.action_type == NightActionType.SEER_CHECK:
            if not request.target_id:
                raise HTTPException(status_code=400, detail="Target ID required for seer check")
            result = game_service.seer_check(request.agent_id, request.target_id)

        elif request.action_type == NightActionType.WITCH_SAVE:
            if not request.target_id:
                raise HTTPException(status_code=400, detail="Target ID required for witch save")
            result = game_service.witch_save(request.agent_id, request.target_id)

        elif request.action_type == NightActionType.WITCH_POISON:
            if not request.target_id:
                raise HTTPException(status_code=400, detail="Target ID required for witch poison")
            result = game_service.witch_poison(request.agent_id, request.target_id)

        elif request.action_type == NightActionType.GUARD_PROTECT:
            if not request.target_id:
                raise HTTPException(status_code=400, detail="Target ID required for guard protect")
            result = game_service.guard_protect(request.agent_id, request.target_id)

        else:
            raise HTTPException(status_code=400, detail=f"Unknown action type: {request.action_type}")

        return {
            "success": True,
            "action_type": request.action_type.value,
            "result": result
        }

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Night action failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/dawn")
async def dawn(game_id: str):
    """
    Resolve night and announce deaths.

    Transitions from night to dawn phase.
    """
    try:
        # Get game
        game_service = active_werewolf_games.get(game_id)
        if not game_service:
            raise HTTPException(status_code=404, detail=f"Game not found: {game_id}")

        # Resolve night actions
        night_result = game_service.resolve_night()

        # Start day phase
        day_result = game_service.start_day_phase()

        # Check win condition
        win_result = game_service.check_win_condition()

        return {
            "success": True,
            "phase": WerewolfPhase.DAWN.value,
            "night_result": night_result,
            "day_result": day_result,
            "win_result": win_result
        }

    except Exception as e:
        logger.error(f"Dawn phase failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/discuss")
async def start_discussion(game_id: str):
    """
    Start discussion phase.

    Agents can speak and share information.
    """
    try:
        # Get game
        game_service = active_werewolf_games.get(game_id)
        if not game_service:
            raise HTTPException(status_code=404, detail=f"Game not found: {game_id}")

        # Start discussion
        game_service.start_discussion_phase()

        return {
            "success": True,
            "phase": WerewolfPhase.DAY_DISCUSSION.value,
            "message": "讨论阶段开始"
        }

    except Exception as e:
        logger.error(f"Discussion phase failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/player-speech")
async def player_speech(request: PlayerSpeechRequest):
    """夺席模式：玩家为被接管的 agent 提交公开发言，事件流轮到该 agent 时采用。"""
    game_service = active_werewolf_games.get(request.game_id)
    if not game_service:
        raise HTTPException(status_code=404, detail=f"Game not found: {request.game_id}")
    try:
        return game_service.submit_player_speech(request.agent_id, request.content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/vote")
async def vote(request: VoteRequest):
    """
    Record a vote during voting phase.
    """
    try:
        # Get game
        game_service = active_werewolf_games.get(request.game_id)
        if not game_service:
            raise HTTPException(status_code=404, detail=f"Game not found: {request.game_id}")

        # Validate phase
        if game_service.state.phase != WerewolfPhase.DAY_VOTING:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot vote in phase: {_enum_value(game_service.state.phase)}"
            )

        # Record vote
        result = game_service.record_vote(request.voter_id, request.target_id)

        return {
            "success": True,
            "vote": result
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Vote failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/resolve-vote")
async def resolve_vote(game_id: str):
    """
    Resolve voting and eliminate player.
    """
    try:
        # Get game
        game_service = active_werewolf_games.get(game_id)
        if not game_service:
            raise HTTPException(status_code=404, detail=f"Game not found: {game_id}")

        # Resolve voting
        elimination_result = game_service.resolve_voting()

        # Check win condition
        win_result = game_service.check_win_condition()

        # If game not over, advance to next round
        if not win_result:
            game_service.advance_to_next_round()

        return {
            "success": True,
            "elimination": elimination_result,
            "win_result": win_result,
            "next_round": game_service.state.current_round if not win_result else None
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Vote resolution failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/state/{game_id}", response_model=GameStateResponse)
async def get_game_state(game_id: str):
    """
    Get current game state.
    """
    try:
        # Get game
        game_service = active_werewolf_games.get(game_id)
        if not game_service:
            raise HTTPException(status_code=404, detail=f"Game not found: {game_id}")

        state = game_service.get_game_state()

        # Build agent info (without revealing roles to non-owners)
        agents_info = {}
        for agent_id, agent_state in state.agents.items():
            agents_info[agent_id] = {
                "agent_id": agent_id,
                "name": agent_state.name,
                "is_alive": agent_state.is_alive,
                "is_possessed": agent_state.is_possessed,
                "mbti_type": agent_state.mbti_type,
                "iq_level": agent_state.iq_level
                # Role is hidden
            }

        alive_count = len([a for a in state.agents.values() if a.is_alive])

        return GameStateResponse(
            game_id=game_id,
            phase=_enum_value(state.phase),
            current_round=state.current_round,
            agents=agents_info,
            alive_count=alive_count
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get game state failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agent-role/{game_id}/{agent_id}")
async def get_agent_role(game_id: str, agent_id: str):
    """
    Get agent's role (for the agent's own view).

    This endpoint reveals the role to the specific agent.
    """
    try:
        # Get game
        game_service = active_werewolf_games.get(game_id)
        if not game_service:
            raise HTTPException(status_code=404, detail=f"Game not found: {game_id}")

        # Get agent state
        agent_state = game_service.get_agent_state(agent_id)
        if not agent_state:
            raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")

        # Return role information
        from models.werewolf import get_role_name_cn

        result = {
            "agent_id": agent_id,
            "name": agent_state.name,
            "role": _enum_value(agent_state.role),
            "role_cn": get_role_name_cn(agent_state.role),
            "faction": _enum_value(agent_state.faction),
            "is_alive": agent_state.is_alive
        }

        # Add role-specific info
        if agent_state.role == WerewolfRole.WITCH and agent_state.witch_potions:
            result["witch_potions"] = {
                "antidote": agent_state.witch_potions.antidote,
                "poison": agent_state.witch_potions.poison
            }
        elif agent_state.role == WerewolfRole.SEER:
            result["seer_check_results"] = agent_state.seer_check_results
        elif agent_state.role == WerewolfRole.GUARD:
            result["guard_last_protected"] = agent_state.guard_last_protected

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get agent role failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/game/{game_id}/terminate")
async def terminate_game(game_id: str):
    """终止对局：立即中断后台对局任务（包括进行中的模型调用），
    标记对局为「用户终止」并保留回放，可正常查看复盘。"""
    game_service = active_werewolf_games.get(game_id)
    if not game_service:
        raise HTTPException(status_code=404, detail=f"Game not found: {game_id}")

    cancelled = game_broker.cancel(game_id)
    game_service.state.phase = WerewolfPhase.GAME_OVER
    game_service.state.winner = "aborted"
    game_service.state.game_over_reason = "用户终止对局"
    game_service._persist_replay()
    # 延迟导入避免与 werewolf_stream 的循环依赖
    from api.werewolf_stream import stream_controls
    stream_controls.pop(game_id, None)
    logger.info("Terminated werewolf game %s (task was running: %s)", game_id, cancelled)
    return {"success": True, "game_id": game_id, "was_running": cancelled}


@router.delete("/game/{game_id}")
async def delete_game(game_id: str):
    """
    Delete a game. Also cancels the background game loop immediately
    (中断进行中的模型调用，不再继续消耗 token)。
    """
    try:
        if game_id in active_werewolf_games:
            game_broker.discard(game_id)
            from api.werewolf_stream import stream_controls
            stream_controls.pop(game_id, None)
            del active_werewolf_games[game_id]
            logger.info(f"Deleted werewolf game {game_id}")
            return {"success": True, "message": f"Game {game_id} deleted"}
        else:
            # 对局可能已结束并从内存移除，但后台任务/backlog 需要一并清理
            if game_broker.has_game(game_id):
                game_broker.discard(game_id)
                from api.werewolf_stream import stream_controls
                stream_controls.pop(game_id, None)
                return {"success": True, "message": f"Game {game_id} deleted"}
            raise HTTPException(status_code=404, detail=f"Game not found: {game_id}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete game failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/games")
async def list_games():
    """
    List all active werewolf games.
    """
    try:
        games = []
        for game_id, game_service in active_werewolf_games.items():
            state = game_service.state
            games.append({
                "game_id": game_id,
                "player_count": game_service.player_count,
                "phase": _enum_value(state.phase),
                "current_round": state.current_round,
                "alive_count": len([a for a in state.agents.values() if a.is_alive]),
                "created_at": state.created_at.isoformat()
            })

        return {
            "games": games,
            "total": len(games)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"List games failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/replays")
async def list_replays(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(5, ge=1, le=50, description="Items per page"),
    search: str = Query("", description="Search by game_id"),
    status: str = Query("all", pattern="^(all|active|finished)$", description="Replay status filter"),
    sort_by: str = Query("updated_at", pattern="^(updated_at|started_at|total_events)$", description="Replay sort field"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$", description="Replay sort order"),
):
    """List persisted werewolf replays for historical playback."""
    try:
        replay_items = {
            item["game_id"]: item
            for item in werewolf_replay_store.list_replays()
        }

        for game_id, game_service in active_werewolf_games.items():
            replay_items[game_id] = {
                "game_id": game_id,
                "total_events": len(game_service.game_events),
                "player_count": game_service.player_count,
                "alive_count": len([agent for agent in game_service.state.agents.values() if agent.is_alive]),
                "current_round": game_service.state.current_round,
                "current_phase": _enum_value(game_service.state.phase),
                "winner": _enum_value(game_service.state.winner),
                "game_over_reason": game_service.state.game_over_reason,
                "updated_at": game_service.state.updated_at.isoformat(),
                "started_at": game_service.state.created_at.isoformat(),
                "is_active": True,
            }

        normalized_search = search.strip().lower()
        filtered_replays = [
            item for item in replay_items.values()
            if (
                (not normalized_search or normalized_search in item["game_id"].lower())
                and (
                    status == "all"
                    or (status == "active" and item.get("is_active"))
                    or (status == "finished" and not item.get("is_active"))
                )
            )
        ]

        sort_key_map = {
            "updated_at": lambda item: item.get("updated_at") or "",
            "started_at": lambda item: item.get("started_at") or "",
            "total_events": lambda item: item.get("total_events") or 0,
        }
        replays = sorted(
            filtered_replays,
            key=sort_key_map[sort_by],
            reverse=(sort_order == "desc"),
        )
        total = len(replays)
        start = (page - 1) * page_size
        end = start + page_size
        stats = {
            "total": total,
            "active": len([item for item in filtered_replays if item.get("is_active")]),
            "finished": len([item for item in filtered_replays if not item.get("is_active")]),
        }
        return {
            "replays": replays[start:end],
            "total": total,
            "page": page,
            "page_size": page_size,
            "sort_by": sort_by,
            "sort_order": sort_order,
            "stats": stats,
        }
    except Exception as e:
        logger.error(f"List replays failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/replay/{game_id}")
async def delete_replay(game_id: str):
    """Delete a persisted replay and any active in-memory game with the same id."""
    try:
        active_werewolf_games.pop(game_id, None)
        game_broker.discard(game_id)
        from api.werewolf_stream import stream_controls
        stream_controls.pop(game_id, None)
        deleted = werewolf_replay_store.delete_replay(game_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Replay not found: {game_id}")
        return {"success": True, "game_id": game_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete replay failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/replays/finished")
async def delete_finished_replays():
    """Delete all persisted finished replays while keeping active games untouched."""
    try:
        active_game_ids = set(active_werewolf_games.keys())
        finished_replay_ids = [
            item["game_id"]
            for item in werewolf_replay_store.list_replays()
            if item["game_id"] not in active_game_ids
        ]
        deleted_count = werewolf_replay_store.delete_replays(finished_replay_ids)
        return {
            "success": True,
            "deleted_count": deleted_count,
            "deleted_game_ids": finished_replay_ids[:deleted_count],
        }
    except Exception as e:
        logger.error(f"Delete finished replays failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/replay/{game_id}")
async def get_game_replay(game_id: str):
    """
    Get complete game history for replay.

    Returns all game events with timestamps, types, and data for timeline replay.
    """
    try:
        # Get game
        game_service = active_werewolf_games.get(game_id)
        if game_service:
            return game_service.to_replay_dict()

        return werewolf_replay_store.load_replay(game_id)

    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Game not found: {game_id}")
    except Exception as e:
        logger.error(f"Get game replay failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/replay/{game_id}/export")
async def export_game_replay(game_id: str):
    """Export replay payload as downloadable JSON."""
    try:
        game_service = active_werewolf_games.get(game_id)
        replay_data = game_service.to_replay_dict() if game_service else werewolf_replay_store.load_replay(game_id)
        return Response(
            content=json.dumps(replay_data, ensure_ascii=False, indent=2),
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="{game_id}-replay.json"'
            },
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Game not found: {game_id}")
    except Exception as e:
        logger.error(f"Export game replay failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/replay/{game_id}/export/markdown")
async def export_game_replay_markdown(game_id: str):
    """Export replay report as downloadable markdown."""
    try:
        game_service = active_werewolf_games.get(game_id)
        replay_data = game_service.to_replay_dict() if game_service else werewolf_replay_store.load_replay(game_id)
        markdown = werewolf_report_service.build_markdown(replay_data)
        return Response(
            content=markdown,
            media_type="text/markdown; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{game_id}-report.md"'
            },
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Game not found: {game_id}")
    except Exception as e:
        logger.error(f"Export game replay markdown failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/replay/{game_id}/export/pdf")
async def export_game_replay_pdf(game_id: str):
    """Export replay report as downloadable PDF."""
    try:
        game_service = active_werewolf_games.get(game_id)
        replay_data = game_service.to_replay_dict() if game_service else werewolf_replay_store.load_replay(game_id)
        pdf_bytes = werewolf_report_service.build_pdf(replay_data)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{game_id}-report.pdf"'
            },
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Game not found: {game_id}")
    except Exception as e:
        logger.error(f"Export game replay PDF failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
