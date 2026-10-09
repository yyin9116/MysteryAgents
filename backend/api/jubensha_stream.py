"""
Jubensha (剧本杀) streaming API.

对局主循环由 game_broker 后台任务驱动（与狼人杀一致）：
- 终止：DELETE /api/jubensha/game/{id} 立即取消；
- 断线：对局继续，重连按 seq 续播；
- 参与模式：轮到玩家席位时暂停等待输入，超时由 AI 代打。
"""

import asyncio
import json
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.jubensha import active_jubensha_games
from models.jubensha import JubenshaPhase
from services.game_broker import game_broker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/jubensha/stream", tags=["jubensha-stream"])

# 单次模型调用超时（秒）：超时/失败时用兜底发言继续对局，不让一次挂起拖死整局
TURN_TIMEOUT_SECONDS = 150.0

# game_id -> StreamControl（对齐狼人杀的节奏闸门）
from api.werewolf_stream import (
    StreamControl,
    StreamControlRequest,
    get_stream_control,
    stream_controls,
)


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


class StartStreamRequest(BaseModel):
    game_id: str


@router.post("/{game_id}/control")
async def control_stream(game_id: str, request: StreamControlRequest):
    if game_id not in active_jubensha_games:
        raise HTTPException(status_code=404, detail=f"Game not found: {game_id}")
    control = stream_controls.setdefault(game_id, StreamControl())
    state = control.apply(mode=request.mode, speed=request.speed, action=request.action)
    return {"success": True, **state}


# 复用狼人杀的控制请求模型（已在顶部导入）


def ensure_broker_started(game_id: str) -> None:
    service = active_jubensha_games.get(game_id)
    if not service:
        return
    # 守卫：主循环只启动一次。对局结束/被终止后的 SSE 重连绝不能重启整局
    # （否则会从头重跑读本与全部 LLM 调用）。重连续播由 broker backlog 负责。
    if getattr(service, "loop_started", False):
        return
    service.loop_started = True
    game_broker.start(game_id, lambda emit: jubensha_game_loop(game_id, emit))


async def safe_turn(emit, coro_factory, actor_name: str, kind: str):
    """带超时与异常兜底的模型调用；失败返回 None，由调用方生成兜底内容。"""
    try:
        return await asyncio.wait_for(coro_factory(), timeout=TURN_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        logger.warning("Jubensha turn timeout: game phase=%s actor=%s", kind, actor_name)
        emit({
            'type': 'turn_error',
            'phase': kind,
            'agent_name': actor_name,
            'message': f'{actor_name} 的模型调用超时（{TURN_TIMEOUT_SECONDS:.0f}s），已使用兜底发言继续对局',
        })
        return None
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.exception("Jubensha turn failed: phase=%s actor=%s", kind, actor_name)
        emit({
            'type': 'turn_error',
            'phase': kind,
            'agent_name': actor_name,
            'message': f'{actor_name} 的模型调用失败（{exc.__class__.__name__}），已使用兜底发言继续对局',
        })
        return None


async def jubensha_game_loop(game_id: str, emit) -> None:
    """剧本杀主流程：读本 → 线索 → 讨论×N → 投票 → 结算。"""
    service = active_jubensha_games.get(game_id)
    if not service:
        emit({'type': 'error', 'message': f'Game not found: {game_id}'})
        return

    delay_scale = 0.15 if getattr(service, "fast_mode", False) else 1.0
    control = get_stream_control(game_id)

    async def gate(seconds: float, *, reading_chars: int = 0) -> None:
        await control.gate(seconds, delay_scale, reading_chars=reading_chars)

    emit({
        'type': 'game_start',
        'game_id': game_id,
        'script_id': service.script_pack.script_id,
        'title': service.script_pack.meta.title,
        'player_count': service.player_count,
        'phase': service.phase.value,
    })
    await gate(0.5)

    emit({
        'type': 'phase_change',
        'phase': JubenshaPhase.READING.value,
        'message': service.script_pack.host_manual.intro or '读本阶段：请各位阅读自己的角色本',
    })
    service.start_reading()
    await gate(1.0)

    # ==================== READING ====================
    runtimes = service.get_alive_runtimes()
    for i, runtime in enumerate(runtimes):
        emit({
            'type': 'agent_speaking',
            'phase': 'reading',
            'agent_id': runtime.char_id,
            'agent_name': runtime.name,
            'index': i + 1,
            'total': len(runtimes),
            'message': f'{runtime.name} 正在阅读角色本...',
        })
        await gate(0.4)

        player_override = service.pending_player_speeches.pop(runtime.char_id, None)
        if player_override is None and service.is_player_agent(runtime.char_id):
            emit({
                'type': 'player_input_required',
                'phase': 'reading',
                'agent_id': runtime.char_id,
                'agent_name': runtime.name,
                'timeout_seconds': 240,
                'message': f'轮到你做自我介绍（{runtime.name}）',
            })
            player_override = await service.wait_for_player_speech(runtime.char_id, timeout=240.0)

        started_at = asyncio.get_running_loop().time()
        if player_override is not None:
            reading_result = await service.run_reading_turn(
                runtime.char_id, override_content=player_override
            )
        else:
            reading_result = await safe_turn(
                emit,
                lambda: service.run_reading_turn(runtime.char_id),
                runtime.name,
                'reading',
            )
            if reading_result is None:
                reading_result = {
                    "content": f"（{runtime.name} 默默翻完角色本，向大家点了点头：「我先听各位说。」）",
                    "thought": "",
                }
        elapsed_ms = int((asyncio.get_running_loop().time() - started_at) * 1000)
        emit({
            'type': 'agent_speaking',
            'phase': 'reading',
            'agent_id': runtime.char_id,
            'agent_name': runtime.name,
            'index': i + 1,
            'total': len(runtimes),
            'message': reading_result['content'],
            'speech': reading_result['content'],
            'thought': reading_result.get('thought', ''),
            'player_controlled': bool(player_override),
            'elapsed_ms': elapsed_ms,
        })
        await gate(1.2, reading_chars=len(reading_result.get('content') or ''))

    # ==================== CLUE ROUNDS ====================
    clue_rounds = sorted({c.distribution.round for c in service.script_pack.clues})
    for round_no in clue_rounds:
        emit({
            'type': 'phase_change',
            'phase': JubenshaPhase.CLUE.value,
            'round': round_no,
            'message': f'线索发放 · 第 {round_no} 轮',
        })
        service.start_clue_round()
        await gate(1.0)

        grants = service.grant_clue_round()
        emit({
            'type': 'clue_granted',
            'round': round_no,
            'grants': grants,
            'message': f'第 {round_no} 轮线索已发放（{len(grants)} 组）',
        })
        await gate(1.5)

        # 每轮线索后插一轮讨论
        await _run_discussion_round(service, emit, gate)

        if service.phase == JubenshaPhase.REVEAL:
            return
    else:
        # 无线索时至少跑完默认讨论轮次
        if not clue_rounds:
            service.start_discussion()
            for _ in range(service.discussion_rounds):
                await _run_discussion_round(service, emit, gate)
                if service.phase == JubenshaPhase.REVEAL:
                    return

    # ==================== VOTE ====================
    await _run_vote_and_reveal(service, emit, gate)


async def _run_discussion_round(service, emit, gate) -> None:
    """一轮讨论：所有存活角色依次发言。"""
    service.start_discussion()
    emit({
        'type': 'phase_change',
        'phase': JubenshaPhase.DISCUSSION.value,
        'round': service.current_round,
        'message': f'第 {service.current_round} 轮讨论',
    })
    await gate(1.0)

    speakers = service.get_alive_runtimes()
    for i, runtime in enumerate(speakers):
        emit({
            'type': 'agent_speaking',
            'phase': 'discussion',
            'agent_id': runtime.char_id,
            'agent_name': runtime.name,
            'index': i + 1,
            'total': len(speakers),
            'round': service.current_round,
            'message': f'{runtime.name} 正在整理思路...',
        })
        await gate(0.5)

        player_override = service.pending_player_speeches.pop(runtime.char_id, None)
        if player_override is None and service.is_player_agent(runtime.char_id):
            emit({
                'type': 'player_input_required',
                'phase': 'discussion',
                'agent_id': runtime.char_id,
                'agent_name': runtime.name,
                'timeout_seconds': 240,
                'message': f'轮到你发言（{runtime.name}），超时将由 AI 代打',
            })
            player_override = await service.wait_for_player_speech(runtime.char_id, timeout=240.0)

        started_at = asyncio.get_running_loop().time()
        result = await safe_turn(
            emit,
            lambda: service.run_discussion_turn(
                runtime.char_id, override_content=player_override
            ),
            runtime.name,
            'discussion',
        )
        if result is None:
            fallback = f"（{runtime.name} 沉默片刻）……我暂时保留意见，先听听别人的推理。"
            result = {"content": fallback, "thought": "", "suspicion": {}, "bubbles": [fallback]}
        elapsed_ms = int((asyncio.get_running_loop().time() - started_at) * 1000)
        emit({
            'type': 'agent_speaking',
            'phase': 'discussion',
            'agent_id': runtime.char_id,
            'agent_name': runtime.name,
            'index': i + 1,
            'total': len(speakers),
            'round': service.current_round,
            'message': result['content'],
            'speech': result['content'],
            'bubbles': result.get('bubbles') or [result['content']],
            'thought': result.get('thought', ''),
            'suspicion': result.get('suspicion', {}),
            'player_controlled': bool(player_override),
            'elapsed_ms': elapsed_ms,
        })
        await gate(1.5, reading_chars=len(result.get('content') or ''))

    service.current_round += 1


async def _run_vote_and_reveal(service, emit, gate) -> None:
    """投票与结算。"""
    service.start_voting()
    emit({
        'type': 'phase_change',
        'phase': JubenshaPhase.VOTE.value,
        'message': '讨论结束，开始投票指认',
    })
    await gate(1.0)

    voters = service.get_alive_runtimes()
    for i, runtime in enumerate(voters):
        emit({
            'type': 'agent_voting',
            'agent_id': runtime.char_id,
            'agent_name': runtime.name,
            'index': i + 1,
            'total': len(voters),
            'message': f'{runtime.name} 正在考虑指认对象...',
        })
        await gate(0.5)

        if service.is_player_agent(runtime.char_id) and runtime.char_id not in service.votes:
            emit({
                'type': 'player_input_required',
                'phase': 'vote',
                'agent_id': runtime.char_id,
                'agent_name': runtime.name,
                'timeout_seconds': 240,
                'message': f'轮到你指认（{runtime.name}），请在角色面板选择；超时由 AI 代投',
            })
            voted_in_time = await service.wait_for_player_vote(runtime.char_id, timeout=240.0)
            if not voted_in_time:
                await service.run_vote_turn(runtime.char_id)
                await gate(0.8)
                continue
            # 玩家已通过 /player-vote 提交
            vote = service.votes[runtime.char_id]
            emit({
                'type': 'agent_voting',
                'agent_id': runtime.char_id,
                'agent_name': runtime.name,
                'voted_for': vote['target'],
                'voted_for_name': service.get_runtime(vote['target']).name if vote['target'] in service.agents else vote['target'],
                'thought': vote.get('reason', ''),
                'player_controlled': True,
                'index': i + 1,
                'total': len(voters),
            })
            await gate(0.8)
            continue

        started_at = asyncio.get_running_loop().time()
        vote_result = await safe_turn(
            emit,
            lambda: service.run_vote_turn(runtime.char_id),
            runtime.name,
            'vote',
        )
        if vote_result is None:
            others = [r for r in service.get_alive_runtimes() if r.char_id != runtime.char_id]
            target = others[0] if others else runtime
            vote_result = {
                "target_id": target.char_id,
                "target_name": target.name,
                "reason": "（模型调用失败，随机指认）",
            }
        elapsed_ms = int((asyncio.get_running_loop().time() - started_at) * 1000)
        emit({
            'type': 'agent_voting',
            'agent_id': runtime.char_id,
            'agent_name': runtime.name,
            'voted_for': vote_result['target_id'],
            'voted_for_name': vote_result['target_name'],
            'thought': vote_result.get('reason', ''),
            'index': i + 1,
            'total': len(voters),
            'elapsed_ms': elapsed_ms,
        })
        await gate(1.0)

    # ==================== REVEAL ====================
    reveal = service.reveal()
    emit({
        'type': 'reveal',
        **reveal,
    })
    emit({
        'type': 'game_over',
        'winner': reveal['winner'],
        'reason': reveal.get('message', ''),
        'murderer_id': reveal.get('murderer_id'),
        'murderer_name': reveal.get('murderer_name'),
        'correct_accusation': reveal.get('correct_accusation'),
        'tally': reveal.get('tally', {}),
        'scores': reveal.get('scores', []),
        'timeline': reveal.get('timeline', []),
        'case_replay': reveal.get('case_replay', ''),
    })


@router.post("/start")
async def start_stream(request: StartStreamRequest):
    if request.game_id not in active_jubensha_games:
        raise HTTPException(status_code=404, detail=f"Game not found: {request.game_id}")
    ensure_broker_started(request.game_id)
    return StreamingResponse(
        game_broker.sse_stream(request.game_id, _sse),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.get("/{game_id}")
async def stream_game(game_id: str):
    if game_id not in active_jubensha_games and not game_broker.has_game(game_id):
        raise HTTPException(status_code=404, detail=f"Game not found: {game_id}")
    ensure_broker_started(game_id)
    return StreamingResponse(
        game_broker.sse_stream(game_id, _sse),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )
