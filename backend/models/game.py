"""
Game state data models.

Defines models for game configuration, state, and events.
"""

from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Literal
from datetime import datetime
from enum import Enum

from .agent import AgentConfig


class GameStatus(str, Enum):
    """Game status enumeration."""
    CONFIGURING = "configuring"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    PAUSED = "paused"


class GamePhase(str, Enum):
    """Current phase within a game round."""
    DESCRIPTION = "description"
    VOTING = "voting"
    ELIMINATION = "elimination"


class WordPair(BaseModel):
    """Pair of similar words for the game."""
    word1: str = Field(..., description="First word (majority)")
    word2: str = Field(..., description="Second word (minority/undercover)")
    similarity: float = Field(default=0.8, ge=0.0, le=1.0, description="Semantic similarity")


class GameConfig(BaseModel):
    """Configuration for a new game."""
    game_id: str = Field(..., description="Unique game identifier")
    agent_count: int = Field(..., ge=3, le=10, description="Number of agents")
    civilian_word: str = Field(..., description="Word for civilian agents")
    undercover_word: str = Field(..., description="Word for undercover agent")
    max_rounds: int = Field(default=10, description="Maximum number of rounds")
    agents: List[AgentConfig] = Field(default_factory=list, description="Agent configurations")
    memory_loss_probability: float = Field(default=0.15, ge=0.0, le=1.0)
    user_profile_id: Optional[str] = None


class ConversationEntry(BaseModel):
    """Single entry in conversation history."""
    round: int = Field(..., description="Round number")
    agent_id: str = Field(..., description="Agent who spoke")
    type: Literal["description", "vote", "elimination"] = Field(..., description="Entry type")
    content: str = Field(..., description="Content of the entry")
    timestamp: float = Field(default_factory=lambda: datetime.now().timestamp())
    metadata: Dict = Field(default_factory=dict)


class PossessionState(BaseModel):
    """State of agent possession by user."""
    agent_id: str
    is_possessed: bool = False
    user_id: Optional[str] = None
    possessed_at: Optional[float] = None
    corrupted_memory: List[Dict] = Field(default_factory=list)


class GameState(BaseModel):
    """Complete game state."""
    id: str = Field(..., description="Unique game identifier")
    status: GameStatus = Field(default=GameStatus.CONFIGURING)
    config: GameConfig
    word_pair: Optional[WordPair] = None
    undercover_agent_id: Optional[str] = None
    current_round: int = 0
    current_turn: int = 0
    conversation_history: List[ConversationEntry] = Field(default_factory=list)
    eliminated_agents: List[str] = Field(default_factory=list)
    possession_states: Dict[str, PossessionState] = Field(default_factory=dict)
    winner: Optional[Literal["Undercover", "Civilians"]] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    last_checkpoint: Optional[str] = None
    version: str = "1.0.0"


class EliminationResult(BaseModel):
    """Result of an elimination vote."""
    eliminated_agent_id: str
    votes: Dict[str, str] = Field(description="Mapping of voter_id to voted_agent_id")
    revealed_word: str
    revealed_role: Literal["Undercover", "Civilian"]
