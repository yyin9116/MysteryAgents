"""
API endpoints for game replay functionality.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import logging
logger = logging.getLogger(__name__)

from services.replay_service import get_replay_manager
from services.state_service import StateService

router = APIRouter()

# Initialize services
state_service = StateService()


class StartReplayRequest(BaseModel):
    """Request to start replay."""
    snapshot_id: str


class JumpToRoundRequest(BaseModel):
    """Request to jump to specific round."""
    round_num: int


class JumpToIndexRequest(BaseModel):
    """Request to jump to specific index."""
    index: int


@router.post("/api/replay/start")
async def start_replay(request: StartReplayRequest):
    """
    Start replay from a snapshot.
    
    Returns:
        Replay initialization info
    """
    try:
        replay_manager = get_replay_manager()
        
        # Load snapshot
        snapshot = state_service.load_snapshot(request.snapshot_id)
        
        # Start replay
        result = replay_manager.start_replay(snapshot)
        
        return {
            "status": "success",
            **result
        }
    
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    except Exception as e:
        logger.error(f"Failed to start replay: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/replay/step/forward")
async def step_forward():
    """
    Step forward to next event.
    
    Returns:
        Next event data and progress
    """
    try:
        replay_manager = get_replay_manager()
        result = replay_manager.step_forward()
        
        if result is None:
            return {
                "status": "end_reached",
                "message": "已到达回放结尾"
            }
        
        return {
            "status": "success",
            **result
        }
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to step forward: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/replay/step/backward")
async def step_backward():
    """
    Step backward to previous event.
    
    Returns:
        Previous event data and progress
    """
    try:
        replay_manager = get_replay_manager()
        result = replay_manager.step_backward()
        
        if result is None:
            return {
                "status": "start_reached",
                "message": "已到达回放开始"
            }
        
        return {
            "status": "success",
            **result
        }
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to step backward: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/replay/jump/round")
async def jump_to_round(request: JumpToRoundRequest):
    """
    Jump to specific round.
    
    Returns:
        Events from target round
    """
    try:
        replay_manager = get_replay_manager()
        result = replay_manager.jump_to_round(request.round_num)
        
        return {
            "status": "success",
            **result
        }
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to jump to round: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/replay/jump/index")
async def jump_to_index(request: JumpToIndexRequest):
    """
    Jump to specific event index.
    
    Returns:
        Event at target index
    """
    try:
        replay_manager = get_replay_manager()
        result = replay_manager.jump_to_index(request.index)
        
        return {
            "status": "success",
            **result
        }
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to jump to index: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/replay/progress")
async def get_progress():
    """
    Get current replay progress.
    
    Returns:
        Progress information
    """
    try:
        replay_manager = get_replay_manager()
        progress = replay_manager.get_progress()
        
        return progress
    
    except Exception as e:
        logger.error(f"Failed to get progress: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/replay/round/{round_num}")
async def get_round_summary(round_num: int):
    """
    Get summary of specific round.
    
    Args:
        round_num: Round number
        
    Returns:
        Round summary with all events
    """
    try:
        replay_manager = get_replay_manager()
        summary = replay_manager.get_round_summary(round_num)
        
        return summary
    
    except Exception as e:
        logger.error(f"Failed to get round summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/replay/agent/{agent_id}")
async def get_agent_timeline(agent_id: str):
    """
    Get timeline of events for specific agent.
    
    Args:
        agent_id: Agent ID
        
    Returns:
        List of events involving this agent
    """
    try:
        replay_manager = get_replay_manager()
        timeline = replay_manager.get_agent_timeline(agent_id)
        
        return {
            "agent_id": agent_id,
            "total_events": len(timeline),
            "events": timeline
        }
    
    except Exception as e:
        logger.error(f"Failed to get agent timeline: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/replay/stop")
async def stop_replay():
    """
    Stop current replay.
    
    Returns:
        Final statistics
    """
    try:
        replay_manager = get_replay_manager()
        stats = replay_manager.stop_replay()
        
        return stats
    
    except Exception as e:
        logger.error(f"Failed to stop replay: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/replay/export")
async def export_replay():
    """
    Export complete replay data.
    
    Returns:
        Complete replay data for analysis
    """
    try:
        replay_manager = get_replay_manager()
        data = replay_manager.export_replay_data()
        
        return data
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to export replay: {e}")
        raise HTTPException(status_code=500, detail=str(e))
