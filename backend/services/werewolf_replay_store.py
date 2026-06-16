"""
Persistent storage for werewolf replay data.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from config.settings import settings

logger = logging.getLogger(__name__)


class WerewolfReplayStore:
    """Stores replay payloads for werewolf games on disk."""

    def __init__(self) -> None:
        self.storage_path = settings.get_storage_path() / "werewolf_replays"
        self.storage_path.mkdir(parents=True, exist_ok=True)

    def save_replay(self, replay_data: Dict[str, Any]) -> Path:
        """Persist replay data to disk."""
        game_id = replay_data["game_id"]
        file_path = self.storage_path / f"{game_id}.json"
        with open(file_path, "w", encoding="utf-8") as file:
            json.dump(replay_data, file, ensure_ascii=False, indent=2, default=str)
        logger.info("Saved werewolf replay: %s", game_id)
        return file_path

    def load_replay(self, game_id: str) -> Dict[str, Any]:
        """Load persisted replay data for a game."""
        file_path = self.storage_path / f"{game_id}.json"
        if not file_path.exists():
            raise FileNotFoundError(f"Werewolf replay not found: {game_id}")

        with open(file_path, "r", encoding="utf-8") as file:
            return json.load(file)

    def list_replays(self) -> List[Dict[str, Any]]:
        """List persisted replays with lightweight metadata."""
        replays: List[Dict[str, Any]] = []
        for file_path in self.storage_path.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as file:
                    replay = json.load(file)
                events = replay.get("events", [])
                first_event_at = events[0]["timestamp"] if events else None
                replays.append({
                    "game_id": replay["game_id"],
                    "total_events": replay.get("total_events", len(events)),
                    "player_count": replay.get("player_count"),
                    "alive_count": replay.get("alive_count"),
                    "current_round": replay.get("current_round", 1),
                    "current_phase": replay.get("current_phase", "unknown"),
                    "winner": replay.get("winner"),
                    "game_over_reason": replay.get("game_over_reason"),
                    "updated_at": replay.get("updated_at") or first_event_at,
                    "started_at": replay.get("started_at") or first_event_at,
                })
            except Exception as exc:
                logger.warning("Failed to read werewolf replay %s: %s", file_path, exc)

        replays.sort(key=lambda item: item.get("updated_at") or "", reverse=True)
        return replays

    def delete_replay(self, game_id: str) -> bool:
        """Delete a persisted replay file if it exists."""
        file_path = self.storage_path / f"{game_id}.json"
        if not file_path.exists():
            return False
        file_path.unlink()
        logger.info("Deleted werewolf replay: %s", game_id)
        return True

    def delete_replays(self, game_ids: List[str]) -> int:
        """Delete multiple persisted replay files and return deleted count."""
        deleted_count = 0
        for game_id in game_ids:
            if self.delete_replay(game_id):
                deleted_count += 1
        return deleted_count


werewolf_replay_store = WerewolfReplayStore()
