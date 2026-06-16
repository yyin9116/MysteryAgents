"""
State management service for game save/load and checkpoints.
"""

import json
import pickle
import gzip
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging
logger = logging.getLogger(__name__)

from config.settings import settings


class StateService:
    """Service for managing game state persistence."""
    
    def __init__(self):
        self.storage_path = Path(settings.STORAGE_PATH)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"State service initialized with storage path: {self.storage_path}")
    
    def save_game(
        self,
        game_id: str,
        game_state: Dict[str, Any],
        snapshot_name: Optional[str] = None
    ) -> str:
        """
        Save game state to disk.
        
        Args:
            game_id: Unique game identifier
            game_state: Complete game state dictionary
            snapshot_name: Optional custom snapshot name
            
        Returns:
            Snapshot ID
        """
        timestamp = datetime.now()
        if not snapshot_name:
            snapshot_name = f"snapshot_{timestamp.strftime('%Y%m%d_%H%M%S')}"
        
        snapshot_id = f"{game_id}_{snapshot_name}"
        
        # Add metadata
        game_state["snapshot_metadata"] = {
            "snapshot_id": snapshot_id,
            "game_id": game_id,
            "saved_at": timestamp.isoformat(),
            "round": game_state.get("current_round", 0),
            "phase": game_state.get("phase", "unknown")
        }
        
        # Save as compressed pickle
        file_path = self.storage_path / f"{snapshot_id}.pkl.gz"
        
        try:
            with gzip.open(file_path, 'wb') as f:
                pickle.dump(game_state, f, protocol=pickle.HIGHEST_PROTOCOL)
            
            # Also save JSON for debugging
            json_path = self.storage_path / f"{snapshot_id}.json"
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(game_state, f, ensure_ascii=False, indent=2, default=str)
            
            logger.info(f"Saved game state: {snapshot_id}")
            return snapshot_id
            
        except Exception as e:
            logger.error(f"Failed to save game state: {e}")
            raise
    
    def load_game(self, snapshot_id: str) -> Dict[str, Any]:
        """
        Load game state from disk.
        
        Args:
            snapshot_id: Snapshot identifier
            
        Returns:
            Game state dictionary
        """
        file_path = self.storage_path / f"{snapshot_id}.pkl.gz"
        
        if not file_path.exists():
            raise FileNotFoundError(f"Snapshot not found: {snapshot_id}")
        
        try:
            with gzip.open(file_path, 'rb') as f:
                game_state = pickle.load(f)
            
            logger.info(f"Loaded game state: {snapshot_id}")
            return game_state
            
        except Exception as e:
            logger.error(f"Failed to load game state: {e}")
            raise
    
    def list_snapshots(self, game_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all available snapshots.
        
        Args:
            game_id: Optional filter by game ID
            
        Returns:
            List of snapshot metadata
        """
        snapshots = []
        
        for file_path in self.storage_path.glob("*.pkl.gz"):
            try:
                with gzip.open(file_path, 'rb') as f:
                    game_state = pickle.load(f)
                
                metadata = game_state.get("snapshot_metadata", {})
                
                # Filter by game_id if provided
                if game_id and metadata.get("game_id") != game_id:
                    continue
                
                snapshots.append({
                    "snapshot_id": metadata.get("snapshot_id", file_path.stem),
                    "game_id": metadata.get("game_id", "unknown"),
                    "timestamp": metadata.get("saved_at"),
                    "saved_at": metadata.get("saved_at"),
                    "round": metadata.get("round", 0),
                    "phase": metadata.get("phase", "unknown"),
                    "file_size": file_path.stat().st_size,
                    "agent_count": len(game_state.get("agents", {})),
                    "alive_count": sum(
                        1
                        for agent in game_state.get("agents", {}).values()
                        if agent.get("is_alive", True)
                    ),
                    "snapshot_type": (
                        "checkpoint"
                        if "checkpoint" in metadata.get("snapshot_id", "")
                        else "manual"
                    ),
                })
                
            except Exception as e:
                logger.warning(f"Failed to read snapshot {file_path}: {e}")
                continue
        
        # Sort by saved_at descending
        snapshots.sort(key=lambda x: x.get("saved_at", ""), reverse=True)
        
        return snapshots
    
    def delete_snapshot(self, snapshot_id: str) -> bool:
        """
        Delete a snapshot.
        
        Args:
            snapshot_id: Snapshot identifier
            
        Returns:
            True if deleted successfully
        """
        file_path = self.storage_path / f"{snapshot_id}.pkl.gz"
        json_path = self.storage_path / f"{snapshot_id}.json"
        
        try:
            if file_path.exists():
                file_path.unlink()
            if json_path.exists():
                json_path.unlink()
            
            logger.info(f"Deleted snapshot: {snapshot_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete snapshot: {e}")
            return False
    
    def create_checkpoint(
        self,
        game_id: str,
        game_state: Dict[str, Any],
        checkpoint_interval: int = 5
    ) -> Optional[str]:
        """
        Create automatic checkpoint if needed.
        
        Args:
            game_id: Game identifier
            game_state: Current game state
            checkpoint_interval: Create checkpoint every N rounds
            
        Returns:
            Snapshot ID if checkpoint created, None otherwise
        """
        current_round = game_state.get("current_round", 0)
        
        if current_round % checkpoint_interval == 0 and current_round > 0:
            snapshot_name = f"checkpoint_round_{current_round}"
            return self.save_game(game_id, game_state, snapshot_name)
        
        return None
    
    def get_latest_checkpoint(self, game_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the latest checkpoint for a game.
        
        Args:
            game_id: Game identifier
            
        Returns:
            Snapshot metadata or None
        """
        snapshots = self.list_snapshots(game_id)
        checkpoints = [s for s in snapshots if "checkpoint" in s["snapshot_id"]]
        
        if checkpoints:
            return checkpoints[0]  # Already sorted by date
        
        return None
