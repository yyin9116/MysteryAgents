"""
CrewAI-backed game-service import path.

GameService drives turns directly while each Agent delegates generation to a
CrewAI runtime when available.
"""

from services.game_service import GameResult, GameService


class CrewAIGameService(GameService):
    """Named entry point for CrewAI-backed game orchestration."""

