"""
Werewolf game streaming API using Server-Sent Events (SSE).
狼人杀游戏实时流式推送
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import asyncio
import json
import logging
from typing import AsyncGenerator

logger = logging.getLogger(__name__)

from api.werewolf import active_werewolf_games
from models.werewolf import WerewolfPhase, get_role_name_cn

router = APIRouter(prefix="/api/werewolf/stream", tags=["werewolf-stream"])


def _enum_value(value):
    return value.value if hasattr(value, "value") else value


def _sse(data: dict) -> str:
    """Serialize an SSE payload."""
    return f"data: {json.dumps(data)}\n\n"


class StartStreamRequest(BaseModel):
    """Request to start game stream."""
    game_id: str


async def werewolf_event_stream(game_id: str) -> AsyncGenerator[str, None]:
    """
    Generate werewolf game event stream.

    Event flow:
    1. Night phase - agents perform night actions
    2. Dawn - announce deaths
    3. Discussion - agents discuss
    4. Voting - agents vote
    5. Elimination - eliminate voted player
    6. Check win condition
    7. Repeat or end game
    """
    try:
        # Get game service
        game_service = active_werewolf_games.get(game_id)
        if not game_service:
            yield _sse({'type': 'error', 'message': f'Game not found: {game_id}'})
            return

        # Send game start event
        delay_scale = 0.15 if getattr(game_service, "fast_mode", False) else 1.0

        async def pause(seconds: float) -> None:
            await asyncio.sleep(max(0.0, seconds * delay_scale))

        yield _sse({
            'type': 'game_start',
            'game_id': game_id,
            'player_count': game_service.player_count,
            'round': game_service.state.current_round,
        })
        await pause(0.5)

        # Main game loop
        while game_service.state.phase != WerewolfPhase.GAME_OVER:
            current_round = game_service.state.current_round

            # ==================== NIGHT PHASE ====================
            if game_service.state.phase == WerewolfPhase.NIGHT:
                yield _sse({
                    'type': 'phase_change',
                    'phase': 'night',
                    'round': current_round,
                    'message': f'第 {current_round} 回合 - 夜晚降临',
                })
                await pause(2.0)

                # In a real implementation, agents would perform night actions here
                # For now, we'll simulate with AI agents making decisions

                yield _sse({
                    'type': 'night_action',
                    'action': 'werewolf_kill',
                    'message': '狼人正在商量今晚的目标...',
                })
                await pause(0.8)
                werewolf_result = await game_service.decide_werewolf_kill()
                if werewolf_result.get("success"):
                    yield _sse({
                        'type': 'night_action',
                        'action': 'werewolf_kill',
                        'actor_name': game_service.get_agent_state(werewolf_result['werewolf_id']).name,
                        'target_id': werewolf_result['target_id'],
                        'target_name': game_service.get_agent_state(werewolf_result['target_id']).name,
                        'used_llm': werewolf_result.get('used_llm', False),
                        'reason': werewolf_result.get('reason', ''),
                        'message': f"狼人锁定了 {game_service.get_agent_state(werewolf_result['target_id']).name}",
                    })
                    await pause(1.2)

                yield _sse({
                    'type': 'night_action',
                    'action': 'seer_check',
                    'message': '预言家正在查验...',
                })
                await pause(0.8)
                seer_result = await game_service.decide_seer_check()
                if seer_result.get("success"):
                    yield _sse({
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
                    await pause(1.2)

                yield _sse({
                    'type': 'night_action',
                    'action': 'witch',
                    'message': '女巫正在斟酌是否用药...',
                })
                await pause(0.8)
                witch_result = await game_service.decide_witch_action()
                if witch_result.get("save_result"):
                    save_result = witch_result["save_result"]
                    yield _sse({
                        'type': 'night_action',
                        'action': 'witch_save',
                        'actor_name': game_service.get_agent_state(save_result['witch_id']).name,
                        'target_id': save_result['target_id'],
                        'target_name': game_service.get_agent_state(save_result['target_id']).name,
                        'used_llm': witch_result.get('used_llm', False),
                        'message': f"女巫救下了 {game_service.get_agent_state(save_result['target_id']).name}",
                    })
                    await pause(1.0)
                if witch_result.get("poison_result"):
                    poison_result = witch_result["poison_result"]
                    yield _sse({
                        'type': 'night_action',
                        'action': 'witch_poison',
                        'actor_name': game_service.get_agent_state(poison_result['witch_id']).name,
                        'target_id': poison_result['target_id'],
                        'target_name': game_service.get_agent_state(poison_result['target_id']).name,
                        'used_llm': witch_result.get('used_llm', False),
                        'message': f"女巫毒杀了 {game_service.get_agent_state(poison_result['target_id']).name}",
                    })
                    await pause(1.0)

                yield _sse({
                    'type': 'night_action',
                    'action': 'guard_protect',
                    'message': '守卫正在决定守护对象...',
                })
                await pause(0.8)
                guard_result = await game_service.decide_guard_protect()
                if guard_result.get("success"):
                    yield _sse({
                        'type': 'night_action',
                        'action': 'guard_protect',
                        'actor_name': game_service.get_agent_state(guard_result['guard_id']).name,
                        'target_id': guard_result['target_id'],
                        'target_name': game_service.get_agent_state(guard_result['target_id']).name,
                        'used_llm': guard_result.get('used_llm', False),
                        'reason': guard_result.get('reason', ''),
                        'message': f"守卫守护了 {game_service.get_agent_state(guard_result['target_id']).name}",
                    })
                    await pause(1.0)

                # Resolve night
                night_result = game_service.resolve_night()

                yield _sse({
                    'type': 'night_complete',
                    'round': current_round,
                    'message': '夜晚结束',
                })
                await pause(1.0)

                # Move to dawn
                game_service.state.phase = WerewolfPhase.DAWN

            # ==================== DAWN PHASE ====================
            if game_service.state.phase == WerewolfPhase.DAWN:
                day_result = game_service.start_day_phase()

                yield _sse({
                    'type': 'phase_change',
                    'phase': 'dawn',
                    'round': current_round,
                    'deaths': day_result['deaths'],
                    'message': day_result['message'],
                })
                await pause(2.0)

                # Check win condition after deaths
                win_result = game_service.check_win_condition()
                if win_result:
                    yield _sse({
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
                yield _sse({
                    'type': 'phase_change',
                    'phase': 'discussion',
                    'round': current_round,
                    'message': '白天讨论开始',
                })
                await asyncio.sleep(1.0)

                # Agents discuss using the configured LLM.
                alive_agents = game_service.get_discussion_agents_for_round()
                for i, agent in enumerate(alive_agents):
                    yield _sse({
                        'type': 'agent_speaking',
                        'phase': 'discussion',
                        'agent_id': agent.agent_id,
                        'agent_name': agent.name,
                        'index': i + 1,
                        'total': len(alive_agents),
                        'message': f'{agent.name} 正在组织发言...',
                    })
                    await pause(0.5)

                    discussion_result = await game_service.run_discussion_turn(agent.agent_id)
                    yield _sse({
                        'type': 'agent_speaking',
                        'phase': 'discussion',
                        'agent_id': agent.agent_id,
                        'agent_name': agent.name,
                        'index': i + 1,
                        'total': len(alive_agents),
                        'message': discussion_result['content'],
                        'speech': discussion_result['content'],
                        'thought': discussion_result.get('thought', ''),
                        'suspicion': discussion_result.get('suspicion', {}),
                    })
                    await pause(1.5)

                # Move to voting
                game_service.start_voting_phase()

            # ==================== VOTING PHASE ====================
            if game_service.state.phase == WerewolfPhase.DAY_VOTING:
                yield _sse({
                    'type': 'phase_change',
                    'phase': 'voting',
                    'round': current_round,
                    'message': '投票阶段开始',
                })
                await pause(1.0)

                # Agents vote using the configured LLM.
                alive_agents = game_service.get_alive_agents()
                for i, agent in enumerate(alive_agents):
                    yield _sse({
                        'type': 'agent_voting',
                        'agent_id': agent.agent_id,
                        'agent_name': agent.name,
                        'index': i + 1,
                        'total': len(alive_agents),
                        'message': f'{agent.name} 正在考虑投票对象...',
                    })
                    await pause(0.5)

                    vote_result = await game_service.run_voting_turn(agent.agent_id)

                    yield _sse({
                        'type': 'agent_voting',
                        'agent_id': agent.agent_id,
                        'agent_name': agent.name,
                        'voted_for': vote_result['target_id'],
                        'voted_for_name': vote_result['target_name'],
                        'thought': vote_result.get('thought', ''),
                        'confidence': vote_result.get('confidence', 0.5),
                        'index': i + 1,
                        'total': len(alive_agents),
                    })
                    await pause(1.0)

                # Resolve voting
                elimination_result = game_service.resolve_voting()

                if elimination_result['eliminated']:
                    yield _sse({
                        'type': 'elimination',
                        'round': current_round,
                        'eliminated_id': elimination_result['eliminated_id'],
                        'eliminated_name': elimination_result['eliminated_name'],
                        'eliminated_role': elimination_result['eliminated_role'],
                        'eliminated_role_cn': elimination_result['eliminated_role_cn'],
                        'vote_count': elimination_result['vote_count'],
                        'votes': elimination_result['votes'],
                    })
                    await pause(2.0)

                # Check win condition
                win_result = game_service.check_win_condition()
                if win_result:
                    yield _sse({
                        'type': 'game_over',
                        'round': current_round,
                        'winner': win_result['winner'],
                        'reason': win_result['reason'],
                        'message': win_result['message'],
                    })
                    break

                # Advance to next round
                game_service.advance_to_next_round()

                yield _sse({
                    'type': 'round_complete',
                    'round': current_round,
                    'next_round': game_service.state.current_round,
                })
                await pause(1.0)

        # Game over
        logger.info(f"Werewolf game {game_id} completed")

    except Exception as e:
        logger.error(f"Stream error: {e}")
        import traceback
        traceback.print_exc()
        yield _sse({'type': 'error', 'message': str(e)})


@router.post("/start")
async def start_werewolf_stream(request: StartStreamRequest):
    """
    Start werewolf game stream.

    Returns SSE stream with real-time game events.
    """
    return StreamingResponse(
        werewolf_event_stream(request.game_id),
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
    """
    return StreamingResponse(
        werewolf_event_stream(game_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
