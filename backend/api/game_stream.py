"""
Game streaming API using Server-Sent Events (SSE)
实时流式推送游戏进度
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import asyncio
import json
import logging
from typing import AsyncGenerator

logger = logging.getLogger(__name__)

from services.game_service import GameService, GameResult
from services.state_service import StateService
from models.game import GamePhase

router = APIRouter(prefix="/api/game/stream", tags=["game-stream"])

state_service = StateService()


def _sse(data: dict) -> str:
    """Serialize an SSE payload."""
    return f"data: {json.dumps(data)}\n\n"


class StartStreamRequest(BaseModel):
    game_id: str


async def game_event_stream(game_id: str) -> AsyncGenerator[str, None]:
    """
    生成游戏事件流 - Select Speaker 模式
    
    完整流程：
    1. 开始新回合
    2. 逐个选择 Agent 发言
    3. 所有人发言完毕后进入投票
    4. 逐个 Agent 投票
    5. 淘汰得票最多的 Agent
    6. 检查游戏结束条件
    """
    try:
        from api.game import active_games
        
        game_service = active_games.get(game_id)
        if not game_service:
            yield _sse({'type': 'error', 'message': f'Game not found: {game_id}'})
            return
        
        # ==================== 开始新回合 ====================
        game_service.start_new_round()
        current_round = game_service.current_round
        
        yield _sse({'type': 'round_start', 'round': current_round, 'phase': 'description'})
        await asyncio.sleep(0.1)
        
        # ==================== 描述阶段 - 逐个选择发言人 ====================
        alive_agents = game_service.get_alive_agents()
        total_speakers = len(alive_agents)
        speaker_index = 0
        
        while True:
            # 选择下一个发言人
            next_speaker_id = game_service.select_next_speaker(strategy="round_robin")
            
            if not next_speaker_id:
                # 所有人都发言完毕
                break
            
            speaker_index += 1
            agent = game_service.get_agent(next_speaker_id)
            
            # 发送"正在思考"事件
            yield _sse({
                'type': 'agent_thinking',
                'phase': 'description',
                'agent_id': next_speaker_id,
                'agent_name': agent.config.name or next_speaker_id,
                'index': speaker_index,
                'total': total_speakers,
            })
            await asyncio.sleep(0.5)
            
            # Agent 发言
            try:
                speak_result = await game_service.agent_speak(next_speaker_id)
                
                # 检查是否因重复被淘汰
                if speak_result.get('is_duplicate', False):
                    # 发送违规事件
                    yield _sse({
                        'type': 'duplicate_violation',
                        'agent_id': next_speaker_id,
                        'agent_name': agent.config.name or next_speaker_id,
                        'speech': speak_result['speech'],
                        'duplicate_agent_id': speak_result.get('duplicate_agent_id'),
                        'duplicate_speech': speak_result.get('duplicate_speech'),
                        'eliminated': True,
                    })
                    await asyncio.sleep(2.0)  # 给用户时间看到违规通知
                else:
                    # 发送"发言完成"事件
                    yield _sse({
                        'type': 'agent_speaking',
                        'phase': 'description',
                        'agent_id': next_speaker_id,
                        'agent_name': agent.config.name or next_speaker_id,
                        'speech': speak_result['speech'],
                        'thought': speak_result['thought'],
                        'suspicion': speak_result['suspicion'],
                        'index': speaker_index,
                        'total': total_speakers,
                        'all_spoke': speak_result['all_spoke'],
                    })
                await asyncio.sleep(0.3)
                
            except Exception as e:
                logger.error(f"Agent {next_speaker_id} failed to speak: {e}")
                yield _sse({
                    'type': 'agent_error',
                    'agent_id': next_speaker_id,
                    'message': str(e),
                })
        
        # ==================== 投票阶段 ====================
        game_service.start_voting_phase()
        
        yield _sse({'type': 'voting_start', 'round': current_round})
        await asyncio.sleep(1.0)  # 增加延迟，让用户看到投票阶段开始
        
        # 获取所有存活的 Agent 进行投票
        alive_agents_for_voting = game_service.get_alive_agents()
        total_voters = len(alive_agents_for_voting)
        voter_index = 0
        
        for agent in alive_agents_for_voting:
            voter_index += 1
            agent_id = agent.config.id
            
            # 发送"正在思考投票"事件
            yield _sse({
                'type': 'agent_thinking',
                'phase': 'voting',
                'agent_id': agent_id,
                'agent_name': agent.config.name or agent_id,
                'index': voter_index,
                'total': total_voters,
            })
            await asyncio.sleep(0.8)  # 增加思考时间
            
            try:
                vote_result = await game_service.agent_vote(agent_id)
                
                voted_for_agent = game_service.get_agent(vote_result['voted_for'])
                voted_for_name = voted_for_agent.config.name if voted_for_agent else vote_result['voted_for']
                
                # 发送"投票完成"事件
                yield _sse({
                    'type': 'agent_voting',
                    'agent_id': agent_id,
                    'agent_name': agent.config.name or agent_id,
                    'voted_for': vote_result['voted_for'],
                    'voted_for_name': voted_for_name,
                    'confidence': vote_result['confidence'],
                    'thought': vote_result['thought'],
                    'index': voter_index,
                    'total': total_voters,
                    'all_voted': vote_result['all_voted'],
                })
                await asyncio.sleep(0.8)  # 增加延迟，让用户看清投票结果
                
                # 添加投票信息到对话历史（作为系统消息）
                game_service.conversation_history.append({
                    "round": current_round,
                    "agent_id": "system",
                    "type": "voting",
                    "content": f"🗳️ {agent.config.name or agent_id} 投票给 {voted_for_name}",
                    "thought": vote_result['thought'],
                    "suspicion": {}
                })
                
            except Exception as e:
                logger.error(f"Agent {agent_id} failed to vote: {e}")
                # 使用随机投票作为后备
                import random
                alive_ids = [a.config.id for a in game_service.get_alive_agents()]
                valid_targets = [aid for aid in alive_ids if aid != agent_id]
                if valid_targets:
                    random_vote = random.choice(valid_targets)
                    # 手动记录投票
                    agent.vote_history.append({
                        "round": current_round,
                        "voted_for": random_vote,
                        "confidence": 0.5,
                        "user_controlled": False
                    })
                    game_service.voters_this_round.append(agent_id)
        
        # ==================== 淘汰阶段 ====================
        try:
            elimination_result = await game_service.complete_voting_and_eliminate()
            
            # 发送淘汰事件
            yield _sse({
                'type': 'elimination',
                'round': current_round,
                'eliminated_id': elimination_result['eliminated_id'],
                'eliminated_name': elimination_result['eliminated_name'],
                'eliminated_role': elimination_result['eliminated_role'],
                'eliminated_word': elimination_result['eliminated_word'],
                'votes': elimination_result['votes'],
                'vote_count': elimination_result['vote_count'],
            })
            await asyncio.sleep(2.0)  # 增加延迟，等待淘汰动画显示
            
            # 添加淘汰信息到对话历史（作为系统消息）
            game_service.conversation_history.append({
                "round": current_round,
                "agent_id": "system",
                "type": "elimination",
                "content": f"💀 {elimination_result['eliminated_name']} 被淘汰！角色：{elimination_result['eliminated_role']}，词汇：{elimination_result['eliminated_word']}",
                "thought": f"得票数：{elimination_result['vote_count']}",
                "suspicion": {}
            })
            
            # ==================== 检查游戏结束 ====================
            if elimination_result['game_over']:
                # 游戏结束
                yield _sse({
                    'type': 'game_over',
                    'round': current_round,
                    'result': elimination_result['result'],
                    'message': elimination_result['message'],
                })
            else:
                # 回合完成，继续游戏
                remaining_count = len(game_service.get_alive_agents())
                yield _sse({
                    'type': 'round_complete',
                    'round': current_round,
                    'remaining_agents': remaining_count,
                })
        
        except Exception as e:
            logger.error(f"Elimination failed: {e}")
            yield _sse({'type': 'error', 'message': f'Elimination failed: {str(e)}'})
        
    except Exception as e:
        logger.error(f"Stream error: {e}")
        import traceback
        traceback.print_exc()
        yield _sse({'type': 'error', 'message': str(e)})


@router.post("/start")
async def start_game_stream(request: StartStreamRequest):
    """
    开始游戏流式推送
    
    返回 SSE 流，实时推送每个 Agent 的思考和发言
    """
    return StreamingResponse(
        game_event_stream(request.game_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # 禁用 nginx 缓冲
        }
    )


@router.get("/{game_id}/next-round-stream")
async def next_round_stream_legacy(game_id: str):
    """Legacy SSE route used by older integration scripts."""
    return StreamingResponse(
        game_event_stream(game_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
