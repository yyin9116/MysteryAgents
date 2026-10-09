"""
Werewolf game streaming API using Server-Sent Events (SSE).
狼人杀游戏实时流式推送

架构（game_broker）：对局主循环在后台任务中驱动，SSE 连接只是订阅者。
- 终止对局：broker.cancel() 立即中断（包括进行中的模型调用）；
- 用户退出/断线：对局继续在后台推进并落盘回放，重连后按 seq 续播；
- SSE 重连永不重启对局（旧实现重连会从头再跑一遍主循环）。
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import asyncio
import json
import logging

logger = logging.getLogger(__name__)

from api.werewolf import active_werewolf_games
from models.werewolf import WerewolfPhase, get_role_name_cn
from services.game_broker import game_broker

router = APIRouter(prefix="/api/werewolf/stream", tags=["werewolf-stream"])


def _enum_value(value):
    return value.value if hasattr(value, "value") else value


def _sse(data: dict) -> str:
    """Serialize an SSE payload."""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


class StartStreamRequest(BaseModel):
    """Request to start game stream."""
    game_id: str


class StreamControlRequest(BaseModel):
    """Pacing control for a running werewolf stream.

    - mode: 'auto' = 按节奏自动推进；'manual' = 每个事件后暂停等待放行
    - speed: 自动模式倍速（0.5 更慢，2/4 更快）
    - action: 'advance' = 手动模式下放行下一步
    """
    mode: str | None = None
    speed: float | None = None
    action: str | None = None


class StreamControl:
    """Per-game pacing gate shared across SSE reconnects."""

    def __init__(self) -> None:
        self.auto = True
        self.speed = 1.0
        self._advance = asyncio.Event()

    def apply(self, *, mode: str | None = None, speed: float | None = None, action: str | None = None) -> dict:
        if mode in ("auto", "manual"):
            self.auto = mode == "auto"
            # 切模式时清掉残留的放行信号，避免手动模式一进来就跳步
            self._advance.clear()
        if speed is not None:
            self.speed = max(0.25, min(6.0, float(speed)))
        if action == "advance":
            self._advance.set()
        return {"auto": self.auto, "speed": self.speed}

    async def gate(self, base_seconds: float, delay_scale: float, *, reading_chars: int = 0) -> None:
        """Block until the client allows the next beat.

        auto: sleep base delay, extended by content length so long speeches
        stay readable; manual: wait for an explicit advance signal.
        """
        if self.auto:
            # speed 为播放倍速：2x = 等待减半（更快），0.5x = 等待加倍（更慢）
            seconds = base_seconds * delay_scale / self.speed
            if reading_chars:
                # 阅读时长：约 12 字/秒，封顶 8s 基础值，让长发言不被瞬间翻页
                seconds = max(seconds, min(reading_chars / 12.0, 8.0) * delay_scale / self.speed)
            await asyncio.sleep(max(0.0, seconds))
        else:
            # 等待显式放行；提前点下的下一步会在这里被立即消费（最多积压一次）
            await self._advance.wait()
            self._advance.clear()


# game_id -> StreamControl（随对局生命周期管理）
stream_controls: dict[str, StreamControl] = {}


def get_stream_control(game_id: str) -> StreamControl:
    return stream_controls.setdefault(game_id, StreamControl())


@router.post("/{game_id}/control")
async def control_werewolf_stream(game_id: str, request: StreamControlRequest):
    """Set pacing mode / speed, or release the next step in manual mode."""
    if game_id not in active_werewolf_games:
        raise HTTPException(status_code=404, detail=f"Game not found: {game_id}")
    control = get_stream_control(game_id)
    state = control.apply(mode=request.mode, speed=request.speed, action=request.action)
    return {"success": True, **state}


def ensure_broker_started(game_id: str) -> None:
    """Ensure the background game loop is running for this game (idempotent).

    守卫：主循环只启动一次。对局结束/被终止后的 SSE 重连不能重启整局，
    否则会从头重跑开场白与全部 LLM 调用；重连续播由 broker backlog 负责。
    """
    service = active_werewolf_games.get(game_id)
    if not service:
        return
    if getattr(service, "loop_started", False):
        return
    service.loop_started = True
    game_broker.start(game_id, lambda emit: werewolf_game_loop(game_id, emit))


async def werewolf_game_loop(game_id: str, emit) -> None:
    """
    Drive one werewolf game to completion, publishing events via `emit`.

    Event flow:
    1. Opening phase - 每位玩家入座开场白（第一晚前）
    2. Night phase - agents perform night actions
    3. Dawn - announce deaths
    4. Discussion - agents discuss
    5. Voting - agents vote
    6. Elimination - eliminate voted player
    7. Check win condition
    8. Repeat or end game
    """
    # Get game service
    game_service = active_werewolf_games.get(game_id)
    if not game_service:
        emit({'type': 'error', 'message': f'Game not found: {game_id}'})
        return

    # Send game start event
    delay_scale = 0.15 if getattr(game_service, "fast_mode", False) else 1.0

    # 节奏控制闸门：auto=按节奏连播，manual=等待前端「下一步」放行
    # 新对局默认自动 1x；SSE 重连时保留用户已选择的模式/倍速
    control = get_stream_control(game_id)

    async def gate(seconds: float, *, reading_chars: int = 0) -> None:
        await control.gate(seconds, delay_scale, reading_chars=reading_chars)

    emit({
        'type': 'game_start',
        'game_id': game_id,
        'player_count': game_service.player_count,
        'round': game_service.state.current_round,
    })
    await gate(0.5)

    # ==================== OPENING PHASE（第一晚前的入座开场白） ====================
    if game_service.state.current_round == 1:
        emit({
            'type': 'phase_change',
            'phase': 'opening',
            'round': game_service.state.current_round,
            'message': '玩家入座 · 开场白',
        })
        await gate(1.0)

        opening_agents = game_service.get_alive_agents()
        for i, agent in enumerate(opening_agents):
            emit({
                'type': 'agent_speaking',
                'phase': 'opening',
                'agent_id': agent.agent_id,
                'agent_name': agent.name,
                'index': i + 1,
                'total': len(opening_agents),
                'message': f'{agent.name} 正在入场...',
            })
            await gate(0.4)

            started_at = asyncio.get_running_loop().time()
            opening_result = await game_service.run_opening_turn(agent.agent_id)
            elapsed_ms = int((asyncio.get_running_loop().time() - started_at) * 1000)
            emit({
                'type': 'agent_speaking',
                'phase': 'opening',
                'agent_id': agent.agent_id,
                'agent_name': agent.name,
                'index': i + 1,
                'total': len(opening_agents),
                'message': opening_result['content'],
                'speech': opening_result['content'],
                'thought': opening_result.get('thought', ''),
                'suspicion': opening_result.get('suspicion', {}),
                'elapsed_ms': elapsed_ms,
            })
            await gate(1.2, reading_chars=len(opening_result.get('content') or ''))

    # Main game loop
    while game_service.state.phase != WerewolfPhase.GAME_OVER:
        current_round = game_service.state.current_round

        # ==================== NIGHT PHASE ====================
        if game_service.state.phase == WerewolfPhase.NIGHT:
            emit({
                'type': 'phase_change',
                'phase': 'night',
                'round': current_round,
                'message': f'第 {current_round} 回合 - 夜晚降临',
            })
            await gate(2.0)

            emit({
                'type': 'night_action',
                'action': 'werewolf_kill',
                'message': '狼人正在商量今晚的目标...',
            })
            await gate(0.8)
            werewolf_result = await game_service.decide_werewolf_kill()
            if werewolf_result.get("success"):
                emit({
                    'type': 'night_action',
                    'action': 'werewolf_kill',
                    'actor_name': game_service.get_agent_state(werewolf_result['werewolf_id']).name,
                    'target_id': werewolf_result['target_id'],
                    'target_name': game_service.get_agent_state(werewolf_result['target_id']).name,
                    'used_llm': werewolf_result.get('used_llm', False),
                    'reason': werewolf_result.get('reason', ''),
                    'message': f"狼人锁定了 {game_service.get_agent_state(werewolf_result['target_id']).name}",
                })
                await gate(1.2)

            emit({
                'type': 'night_action',
                'action': 'seer_check',
                'message': '预言家正在查验...',
            })
            await gate(0.8)
            seer_result = await game_service.decide_seer_check()
            if seer_result.get("success"):
                emit({
                    'type': 'night_action',
                    'action': 'seer_check',
                    'actor_name': game_service.get_agent_state(seer_result['seer_id']).name,
                    'target_id': seer_result['target_id'],
                    'target_name': seer_result['target_name'],
                    'result': seer_result['faction'],
                    'used_llm': seer_result.get('used_llm', False),
                    'reason': seer_result.get('reason', ''),
                    'message': f"预言家查验了 {seer_result['target_name']}",
                })
                await gate(1.2)

            emit({
                'type': 'night_action',
                'action': 'witch',
                'message': '女巫正在斟酌是否用药...',
            })
            await gate(0.8)
            witch_result = await game_service.decide_witch_action()
            if witch_result.get("save_result"):
                save_result = witch_result["save_result"]
                emit({
                    'type': 'night_action',
                    'action': 'witch_save',
                    'actor_name': game_service.get_agent_state(save_result['witch_id']).name,
                    'target_id': save_result['target_id'],
                    'target_name': game_service.get_agent_state(save_result['target_id']).name,
                    'used_llm': witch_result.get('used_llm', False),
                    'message': f"女巫救下了 {game_service.get_agent_state(save_result['target_id']).name}",
                })
                await gate(1.0)
            if witch_result.get("poison_result"):
                poison_result = witch_result["poison_result"]
                emit({
                    'type': 'night_action',
                    'action': 'witch_poison',
                    'actor_name': game_service.get_agent_state(poison_result['witch_id']).name,
                    'target_id': poison_result['target_id'],
                    'target_name': game_service.get_agent_state(poison_result['target_id']).name,
                    'used_llm': witch_result.get('used_llm', False),
                    'message': f"女巫毒杀了 {game_service.get_agent_state(poison_result['target_id']).name}",
                })
                await gate(1.0)

            emit({
                'type': 'night_action',
                'action': 'guard_protect',
                'message': '守卫正在决定守护对象...',
            })
            await gate(0.8)
            guard_result = await game_service.decide_guard_protect()
            if guard_result.get("success"):
                emit({
                    'type': 'night_action',
                    'action': 'guard_protect',
                    'actor_name': game_service.get_agent_state(guard_result['guard_id']).name,
                    'target_id': guard_result['target_id'],
                    'target_name': game_service.get_agent_state(guard_result['target_id']).name,
                    'used_llm': guard_result.get('used_llm', False),
                    'reason': guard_result.get('reason', ''),
                    'message': f"守卫守护了 {game_service.get_agent_state(guard_result['target_id']).name}",
                })
                await gate(1.0)

            # Resolve night
            night_result = game_service.resolve_night()

            emit({
                'type': 'night_complete',
                'round': current_round,
                'message': '夜晚结束',
            })
            await gate(1.0)

            # Move to dawn
            game_service.state.phase = WerewolfPhase.DAWN

        # ==================== DAWN PHASE ====================
        if game_service.state.phase == WerewolfPhase.DAWN:
            day_result = game_service.start_day_phase()

            emit({
                'type': 'phase_change',
                'phase': 'dawn',
                'round': current_round,
                'deaths': day_result['deaths'],
                'message': day_result['message'],
            })
            await gate(2.0)

            # Check win condition after deaths
            win_result = game_service.check_win_condition()
            if win_result:
                emit({
                    'type': 'game_over',
                    'round': current_round,
                    'winner': win_result['winner'],
                    'reason': win_result['reason'],
                    'message': win_result['message'],
                })
                break

            # Move to discussion
            game_service.start_discussion_phase()

        # ==================== DISCUSSION PHASE ====================
        if game_service.state.phase == WerewolfPhase.DAY_DISCUSSION:
            emit({
                'type': 'phase_change',
                'phase': 'discussion',
                'round': current_round,
                'message': '白天讨论开始',
            })
            await gate(1.0)

            # Agents discuss using the configured LLM.
            alive_agents = game_service.get_discussion_agents_for_round()
            for i, agent in enumerate(alive_agents):
                emit({
                    'type': 'agent_speaking',
                    'phase': 'discussion',
                    'agent_id': agent.agent_id,
                    'agent_name': agent.name,
                    'index': i + 1,
                    'total': len(alive_agents),
                    'message': f'{agent.name} 正在组织发言...',
                })
                await gate(0.5)

                # 夺席：玩家已代打提交发言则直接采用，否则走 LLM
                player_override = game_service.consume_player_speech(agent.agent_id)
                if player_override is None and game_service.is_player_agent(agent.agent_id):
                    # 参与模式：轮到玩家席位，等待真人输入（超时交给 AI 代打）
                    emit({
                        'type': 'player_input_required',
                        'phase': 'discussion',
                        'agent_id': agent.agent_id,
                        'agent_name': agent.name,
                        'timeout_seconds': 240,
                        'message': f'轮到你发言（{agent.name}），请在输入框提交；超时将由 AI 代打',
                    })
                    player_override = await game_service.wait_for_player_speech(agent.agent_id, timeout=240.0)
                started_at = asyncio.get_running_loop().time()
                discussion_result = await game_service.run_discussion_turn(
                    agent.agent_id, override_content=player_override
                )
                elapsed_ms = int((asyncio.get_running_loop().time() - started_at) * 1000)
                emit({
                    'type': 'agent_speaking',
                    'phase': 'discussion',
                    'agent_id': agent.agent_id,
                    'agent_name': agent.name,
                    'index': i + 1,
                    'total': len(alive_agents),
                    'message': discussion_result['content'],
                    'speech': discussion_result['content'],
                    'bubbles': discussion_result.get('bubbles') or [discussion_result['content']],
                    'thought': discussion_result.get('thought', ''),
                    'suspicion': discussion_result.get('suspicion', {}),
                    'player_controlled': bool(player_override),
                    'elapsed_ms': elapsed_ms,
                })
                await gate(1.5, reading_chars=len(discussion_result.get('content') or ''))

            # Move to voting
            game_service.start_voting_phase()

        # ==================== VOTING PHASE ====================
        if game_service.state.phase == WerewolfPhase.DAY_VOTING:
            emit({
                'type': 'phase_change',
                'phase': 'voting',
                'round': current_round,
                'message': '投票阶段开始',
            })
            await gate(1.0)

            # Agents vote using the configured LLM.
            alive_agents = game_service.get_alive_agents()
            for i, agent in enumerate(alive_agents):
                emit({
                    'type': 'agent_voting',
                    'agent_id': agent.agent_id,
                    'agent_name': agent.name,
                    'index': i + 1,
                    'total': len(alive_agents),
                    'message': f'{agent.name} 正在考虑投票对象...',
                })
                await gate(0.5)

                started_at = asyncio.get_running_loop().time()

                # 参与模式：玩家席位等待真人投票（超时交给 AI 代投）
                if game_service.is_player_agent(agent.agent_id):
                    emit({
                        'type': 'player_input_required',
                        'phase': 'voting',
                        'agent_id': agent.agent_id,
                        'agent_name': agent.name,
                        'timeout_seconds': 240,
                        'message': f'轮到你投票（{agent.name}），请在目标面板选择；超时将由 AI 代投',
                    })
                    voted_in_time = await game_service.wait_for_player_vote(agent.agent_id, timeout=240.0)
                    if voted_in_time:
                        target_id = game_service.state.votes_this_round[agent.agent_id]
                        target_state = game_service.get_agent_state(target_id)
                        elapsed_ms = int((asyncio.get_running_loop().time() - started_at) * 1000)
                        emit({
                            'type': 'agent_voting',
                            'agent_id': agent.agent_id,
                            'agent_name': agent.name,
                            'voted_for': target_id,
                            'voted_for_name': target_state.name if target_state else target_id,
                            'thought': '（由玩家本人投票）',
                            'confidence': 1.0,
                            'index': i + 1,
                            'total': len(alive_agents),
                            'player_controlled': True,
                            'elapsed_ms': elapsed_ms,
                        })
                        await gate(1.0)
                        continue
                    # 超时：落入下方 AI 代投

                vote_result = await game_service.run_voting_turn(agent.agent_id)
                elapsed_ms = int((asyncio.get_running_loop().time() - started_at) * 1000)

                emit({
                    'type': 'agent_voting',
                    'agent_id': agent.agent_id,
                    'agent_name': agent.name,
                    'voted_for': vote_result['target_id'],
                    'voted_for_name': vote_result['target_name'],
                    'thought': vote_result.get('thought', ''),
                    'confidence': vote_result.get('confidence', 0.5),
                    'index': i + 1,
                    'total': len(alive_agents),
                    'elapsed_ms': elapsed_ms,
                })
                await gate(1.0)

            # Resolve voting
            elimination_result = game_service.resolve_voting()

            if elimination_result['eliminated']:
                emit({
                    'type': 'elimination',
                    'round': current_round,
                    'eliminated_id': elimination_result['eliminated_id'],
                    'eliminated_name': elimination_result['eliminated_name'],
                    'eliminated_role': elimination_result['eliminated_role'],
                    'eliminated_role_cn': elimination_result['eliminated_role_cn'],
                    'vote_count': elimination_result['vote_count'],
                    'votes': elimination_result['votes'],
                })
                await gate(2.0)

            # Check win condition
            win_result = game_service.check_win_condition()
            if win_result:
                emit({
                    'type': 'game_over',
                    'round': current_round,
                    'winner': win_result['winner'],
                    'reason': win_result['reason'],
                    'message': win_result['message'],
                })
                break

            # Advance to next round
            game_service.advance_to_next_round()

            emit({
                'type': 'round_complete',
                'round': current_round,
                'next_round': game_service.state.current_round,
            })
            await gate(1.0)

    # Game over
    logger.info("Werewolf game %s completed", game_id)


@router.post("/start")
async def start_werewolf_stream(request: StartStreamRequest):
    """
    Start werewolf game stream.

    Starts (or joins) the background game loop and returns an SSE stream.
    """
    if request.game_id not in active_werewolf_games:
        raise HTTPException(status_code=404, detail=f"Game not found: {request.game_id}")
    ensure_broker_started(request.game_id)
    return StreamingResponse(
        game_broker.sse_stream(request.game_id, _sse),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("/{game_id}")
async def stream_werewolf_game(game_id: str):
    """
    Stream werewolf game events (GET endpoint for EventSource).

    Idempotent: 若后台对局已在运行则直接作为订阅者接入（回放 backlog 后续播），
    绝不重启对局。
    """
    if game_id not in active_werewolf_games and not game_broker.has_game(game_id):
        raise HTTPException(status_code=404, detail=f"Game not found: {game_id}")
    ensure_broker_started(game_id)
    return StreamingResponse(
        game_broker.sse_stream(game_id, _sse),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
