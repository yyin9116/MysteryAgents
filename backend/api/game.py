"""
Game API endpoints.

Handles game creation, management, and gameplay.
"""

from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import logging
logger = logging.getLogger(__name__)

from models.game import GameConfig, GamePhase, GameState
from models.agent import AgentConfig, IQLevel
from services.agent_factory import AgentFactory
from services.game_service import GameService, GameResult
from services.state_service import StateService

router = APIRouter(prefix="/api/game", tags=["game"])

# Global state (in production, use proper state management)
active_games: Dict[str, GameService] = {}
state_service = StateService()


def _model_dump(model: Any) -> Dict[str, Any]:
    """Compatibility helper for Pydantic v1/v2 style models."""
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    return model.dict()


class CreateGameRequest(BaseModel):
    """Request to create a new game."""
    agent_count: int = Field(..., ge=3, le=10)
    civilian_word: str = Field(..., min_length=1)
    undercover_word: str = Field(..., min_length=1)
    max_rounds: int = Field(default=10, ge=3, le=20)
    agents: List[Dict[str, str]] = Field(
        default_factory=list,
        description="List of agent configs with mbti_type and iq_level"
    )
    use_balanced_team: bool = Field(default=True)
    # 模型配置 (新格式：统一的 llm_config 对象)
    llm_config: Optional[Dict[str, str]] = None


class CreateGameResponse(BaseModel):
    """Response after creating a game."""
    game_id: str
    agents: List[Dict[str, Any]]
    config: Dict[str, Any]


class GameActionRequest(BaseModel):
    """Request for game actions."""
    game_id: str


class SaveGameRequest(GameActionRequest):
    """Request to save game state."""
    snapshot_name: Optional[str] = None


class PossessAgentRequest(BaseModel):
    """Request to possess an agent."""
    game_id: str
    agent_id: str


class UserInputRequest(BaseModel):
    """User input for possessed agent."""
    game_id: str
    agent_id: str
    speech: str = Field(..., max_length=100)
    suspicion: Dict[str, int] = Field(default_factory=dict)


class UserVoteRequest(BaseModel):
    """User vote for possessed agent."""
    game_id: str
    agent_id: str
    vote: str
    confidence: float = Field(..., ge=0.0, le=1.0)


class LoadGameRequest(BaseModel):
    """Request to load a saved game."""
    snapshot_id: str


@router.post("/create", response_model=CreateGameResponse)
async def create_game(request: CreateGameRequest):
    """
    Create a new game.

    Creates agents and initializes game state.
    """
    try:
        import uuid
        game_id = f"game_{uuid.uuid4().hex[:8]}"

        # Create agent factory
        factory = AgentFactory()

        # 使用新的统一 llm_config 格式
        llm_config = request.llm_config
        if llm_config:
            logger.info(f"Using custom model config: {llm_config.get('model')}")

        # Create agents
        if request.use_balanced_team and not request.agents:
            agents = factory.create_balanced_team(request.agent_count, llm_config=llm_config)
        elif request.agents:
            agents = factory.create_batch(request.agents, llm_config=llm_config)
        else:
            raise HTTPException(400, "Must provide agents or use balanced team")
        
        # Create game config
        config = GameConfig(
            game_id=game_id,
            agent_count=len(agents),
            civilian_word=request.civilian_word,
            undercover_word=request.undercover_word,
            max_rounds=request.max_rounds
        )
        
        # Create game service
        game_service = GameService(config, agents)
        active_games[game_id] = game_service
        
        logger.info(f"Created game {game_id} with {len(agents)} agents")
        
        return CreateGameResponse(
            game_id=game_id,
            agents=[agent.to_dict() for agent in agents],
            config=_model_dump(config)
        )
        
    except Exception as e:
        logger.error(f"Failed to create game: {e}")
        raise HTTPException(500, f"Failed to create game: {str(e)}")


@router.post("/start")
async def start_game(request: GameActionRequest):
    """Start the game and run first round."""
    game_id = request.game_id
    
    if game_id not in active_games:
        raise HTTPException(404, "Game not found")
    
    game = active_games[game_id]
    
    try:
        # Run first description phase
        responses = await game.run_description_phase()
        
        return {
            "game_id": game_id,
            "round": game.current_round,
            "phase": game.phase.value,
            "responses": responses
        }
        
    except Exception as e:
        logger.error(f"Failed to start game: {e}")
        raise HTTPException(500, f"Failed to start game: {str(e)}")


@router.post("/next-round")
async def next_round(request: GameActionRequest, background_tasks: BackgroundTasks):
    """Advance to next round."""
    game_id = request.game_id
    
    if game_id not in active_games:
        raise HTTPException(404, "Game not found")
    
    game = active_games[game_id]
    
    try:
        # Check if we need to vote first
        if game.phase == GamePhase.DESCRIPTION:
            # Run voting phase
            elimination = await game.run_voting_phase()
            
            # Check win condition
            result, message = game.check_win_condition()
            
            if result != GameResult.IN_PROGRESS:
                return {
                    "game_id": game_id,
                    "game_over": True,
                    "result": result.value,
                    "message": message,
                    "elimination": elimination
                }
            
            # Create checkpoint in background
            background_tasks.add_task(
                state_service.create_checkpoint,
                game_id,
                game.to_dict()
            )
            
            # Reset phase to DESCRIPTION for next round
            game.phase = GamePhase.DESCRIPTION
            
            return {
                "game_id": game_id,
                "phase": "voting_complete",
                "elimination": elimination,
                "game_over": False
            }
        
        # Start next description round (phase is not DESCRIPTION, so we can start new round)
        responses = await game.run_description_phase()
        
        return {
            "game_id": game_id,
            "round": game.current_round,
            "phase": game.phase.value,
            "responses": responses,
            "game_over": False
        }
        
    except Exception as e:
        logger.error(f"Failed to advance round: {e}")
        raise HTTPException(500, f"Failed to advance round: {str(e)}")


@router.get("/state/{game_id}")
async def get_game_state(game_id: str):
    """Get current game state."""
    if game_id not in active_games:
        raise HTTPException(404, "Game not found")
    
    game = active_games[game_id]
    
    return {
        "game_id": game_id,
        "round": game.current_round,
        "phase": game.phase.value,
        "agents": [agent.to_dict() for agent in game.get_alive_agents()],
        "conversation_history": game.conversation_history[-20:],  # Last 20 messages
        "elimination_history": game.elimination_history,
        "game_over": False,
    }


@router.get("/{game_id}")
async def get_game_state_legacy(game_id: str):
    """Legacy alias for current game state used by older integration scripts."""
    return await get_game_state(game_id)


@router.get("/{game_id}/next-round-stream")
async def next_round_stream_legacy(game_id: str):
    """Legacy SSE route used by older integration scripts."""
    from api.game_stream import game_event_stream

    return StreamingResponse(
        game_event_stream(game_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/possess")
async def possess_agent(request: PossessAgentRequest):
    """Take control of an agent."""
    if request.game_id not in active_games:
        raise HTTPException(404, "Game not found")
    
    game = active_games[request.game_id]
    agent = game.get_agent(request.agent_id)
    
    if not agent:
        raise HTTPException(404, "Agent not found")
    
    if not agent.is_alive:
        raise HTTPException(400, "Cannot possess eliminated agent")
    
    agent.possess()
    
    # Return agent's current state and memories
    return {
        "agent_id": request.agent_id,
        "possessed": True,
        "word": agent.config.word,
        "role": agent.config.role.value,
        "memories": agent.memory_system.get_conversation_context(game.current_round),
        "suspicion_scores": agent.suspicion_scores
    }


@router.post("/release")
async def release_agent(request: PossessAgentRequest):
    """Release control of an agent."""
    if request.game_id not in active_games:
        raise HTTPException(404, "Game not found")
    
    game = active_games[request.game_id]
    agent = game.get_agent(request.agent_id)
    
    if not agent:
        raise HTTPException(404, "Agent not found")
    
    agent.release()
    
    return {
        "agent_id": request.agent_id,
        "possessed": False
    }


@router.post("/user-input")
async def submit_user_input(request: UserInputRequest):
    """Submit user input for possessed agent during description phase."""
    if request.game_id not in active_games:
        raise HTTPException(404, "Game not found")
    
    game = active_games[request.game_id]
    agent = game.get_agent(request.agent_id)
    
    if not agent:
        raise HTTPException(404, "Agent not found")
    
    if not agent.is_possessed:
        raise HTTPException(400, "Agent is not possessed")
    
    # Record user input
    message = {
        "round": game.current_round,
        "agent_id": agent.config.id,
        "type": "description",
        "content": request.speech,
        "thought": "[用户控制]",
        "suspicion": request.suspicion,
        "user_controlled": True
    }
    game.conversation_history.append(message)
    
    # Update agent's suspicion scores
    agent.suspicion_scores.update(request.suspicion)
    
    # Store in memory
    agent.observe_event(f"我说: {request.speech}", game.current_round)
    
    # Let other agents observe
    for other_agent in game.get_alive_agents():
        if other_agent.config.id != agent.config.id:
            other_agent.observe_event(
                f"{agent.config.id} 说: {request.speech}",
                game.current_round
            )
    
    return {"success": True, "message": message}


@router.post("/user-vote")
async def submit_user_vote(request: UserVoteRequest):
    """Submit user vote for possessed agent during voting phase."""
    if request.game_id not in active_games:
        raise HTTPException(404, "Game not found")
    
    game = active_games[request.game_id]
    agent = game.get_agent(request.agent_id)
    
    if not agent:
        raise HTTPException(404, "Agent not found")
    
    if not agent.is_possessed:
        raise HTTPException(400, "Agent is not possessed")
    
    # Record vote
    vote_record = {
        "round": game.current_round,
        "voted_for": request.vote,
        "confidence": request.confidence,
        "user_controlled": True
    }
    agent.vote_history.append(vote_record)
    
    # Store in memory
    agent.observe_event(
        f"我投票给 {request.vote}，置信度: {request.confidence}",
        game.current_round
    )
    
    return {"success": True, "vote": vote_record}


@router.post("/save")
async def save_game(request: SaveGameRequest):
    """Save game state."""
    if request.game_id not in active_games:
        raise HTTPException(404, "Game not found")
    
    game = active_games[request.game_id]
    
    try:
        snapshot_id = state_service.save_game(
            request.game_id,
            game.to_dict(),
            request.snapshot_name,
        )
        
        return {
            "success": True,
            "snapshot_id": snapshot_id
        }
        
    except Exception as e:
        logger.error(f"Failed to save game: {e}")
        raise HTTPException(500, f"Failed to save game: {str(e)}")


@router.get("/snapshots")
async def list_snapshots(game_id: str = None):
    """List all saved game snapshots."""
    try:
        snapshots = state_service.list_snapshots(game_id)
        return {"snapshots": snapshots}
        
    except Exception as e:
        logger.error(f"Failed to list snapshots: {e}")
        raise HTTPException(500, f"Failed to list snapshots: {str(e)}")


def _restore_game_from_snapshot(snapshot_id: str) -> Dict[str, Any]:
    """Restore an active game instance from a saved snapshot."""
    game_state = state_service.load_game(snapshot_id)
    game = GameService.from_dict(game_state)
    active_games[game.config.game_id] = game

    return {
        "success": True,
        "message": "Game loaded successfully",
        "game_id": game.config.game_id,
        "round": game.current_round,
        "phase": game.phase.value,
        "game_state": game.to_dict(),
    }


@router.post("/load")
async def load_game(request: LoadGameRequest):
    """Load a saved game using request body."""
    try:
        return _restore_game_from_snapshot(request.snapshot_id)
    except FileNotFoundError:
        raise HTTPException(404, "Snapshot not found")
    except Exception as e:
        logger.error(f"Failed to load game: {e}")
        raise HTTPException(500, f"Failed to load game: {str(e)}")


@router.post("/load/{snapshot_id}")
async def load_game_legacy(snapshot_id: str):
    """Load a saved game using legacy path parameter route."""
    try:
        return _restore_game_from_snapshot(snapshot_id)
    except FileNotFoundError:
        raise HTTPException(404, "Snapshot not found")
    except Exception as e:
        logger.error(f"Failed to load game: {e}")
        raise HTTPException(500, f"Failed to load game: {str(e)}")


@router.delete("/snapshot/{snapshot_id}")
async def delete_snapshot(snapshot_id: str):
    """Delete a saved snapshot."""
    try:
        success = state_service.delete_snapshot(snapshot_id)
        
        if success:
            return {"success": True}
        else:
            raise HTTPException(500, "Failed to delete snapshot")
            
    except Exception as e:
        logger.error(f"Failed to delete snapshot: {e}")
        raise HTTPException(500, f"Failed to delete snapshot: {str(e)}")
