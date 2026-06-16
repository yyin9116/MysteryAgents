"""
Replay service for game playback and analysis.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import logging
logger = logging.getLogger(__name__)


class ReplayEvent:
    """Represents a single event in the replay."""
    
    def __init__(
        self,
        event_type: str,
        round_num: int,
        timestamp: str,
        data: Dict[str, Any]
    ):
        self.event_type = event_type
        self.round_num = round_num
        self.timestamp = timestamp
        self.data = data
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "round_num": self.round_num,
            "timestamp": self.timestamp,
            "data": self.data
        }


class ReplayManager:
    """
    Manages game replay functionality.
    
    Allows stepping through game events, jumping to specific rounds,
    and viewing agent internal states at each decision point.
    """
    
    def __init__(self):
        self.events: List[ReplayEvent] = []
        self.current_index: int = 0
        self.snapshot_id: Optional[str] = None
        self.is_active: bool = False
    
    def start_replay(self, snapshot_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Start replay from a snapshot.
        
        Args:
            snapshot_data: Complete game snapshot data
            
        Returns:
            Dict with replay initialization info
        """
        self.snapshot_id = snapshot_data.get("snapshot_id")
        self.events = self._build_event_timeline(snapshot_data)
        self.current_index = 0
        self.is_active = True
        
        logger.info(f"Started replay with {len(self.events)} events")
        
        return {
            "status": "started",
            "snapshot_id": self.snapshot_id,
            "total_events": len(self.events),
            "total_rounds": self._get_total_rounds(),
            "current_index": self.current_index
        }
    
    def _build_event_timeline(self, snapshot_data: Dict[str, Any]) -> List[ReplayEvent]:
        """
        Build chronological event timeline from snapshot.
        
        Args:
            snapshot_data: Game snapshot data
            
        Returns:
            List of ReplayEvent objects
        """
        events = []
        
        # Extract conversation history
        conversation_history = snapshot_data.get("conversation_history", [])
        for msg in conversation_history:
            event = ReplayEvent(
                event_type="description",
                round_num=msg.get("round", 0),
                timestamp=msg.get("timestamp", datetime.now().isoformat()),
                data={
                    "agent_id": msg.get("agent_id"),
                    "speech": msg.get("content"),
                    "thought": msg.get("thought"),
                    "suspicion": msg.get("suspicion", {})
                }
            )
            events.append(event)
        
        # Extract elimination history
        elimination_history = snapshot_data.get("elimination_history", [])
        for elim in elimination_history:
            event = ReplayEvent(
                event_type="elimination",
                round_num=elim.get("round", 0),
                timestamp=elim.get("timestamp", datetime.now().isoformat()),
                data={
                    "eliminated_id": elim.get("eliminated_id"),
                    "eliminated_word": elim.get("eliminated_word"),
                    "eliminated_role": elim.get("eliminated_role"),
                    "votes": elim.get("votes", {}),
                    "vote_details": elim.get("vote_details", [])
                }
            )
            events.append(event)
        
        # Sort by round and timestamp
        events.sort(key=lambda e: (e.round_num, e.timestamp))
        
        return events
    
    def step_forward(self) -> Optional[Dict[str, Any]]:
        """
        Move to next event.
        
        Returns:
            Event data or None if at end
        """
        if not self.is_active:
            raise ValueError("Replay not started")
        
        if self.current_index >= len(self.events):
            logger.info("Reached end of replay")
            return None
        
        event = self.events[self.current_index]
        self.current_index += 1
        
        return {
            "event": event.to_dict(),
            "progress": self.get_progress()
        }
    
    def step_backward(self) -> Optional[Dict[str, Any]]:
        """
        Move to previous event.
        
        Returns:
            Event data or None if at beginning
        """
        if not self.is_active:
            raise ValueError("Replay not started")
        
        if self.current_index <= 0:
            logger.info("At beginning of replay")
            return None
        
        self.current_index -= 1
        event = self.events[self.current_index]
        
        return {
            "event": event.to_dict(),
            "progress": self.get_progress()
        }
    
    def jump_to_round(self, round_num: int) -> Dict[str, Any]:
        """
        Jump to specific round.
        
        Args:
            round_num: Target round number
            
        Returns:
            Dict with events from that round
        """
        if not self.is_active:
            raise ValueError("Replay not started")
        
        # Find first event of target round
        target_index = None
        for i, event in enumerate(self.events):
            if event.round_num == round_num:
                target_index = i
                break
        
        if target_index is None:
            raise ValueError(f"Round {round_num} not found")
        
        self.current_index = target_index
        
        # Get all events from this round
        round_events = [
            e.to_dict() for e in self.events
            if e.round_num == round_num
        ]
        
        logger.info(f"Jumped to round {round_num}, index {target_index}")
        
        return {
            "round": round_num,
            "events": round_events,
            "progress": self.get_progress()
        }
    
    def jump_to_index(self, index: int) -> Dict[str, Any]:
        """
        Jump to specific event index.
        
        Args:
            index: Target event index
            
        Returns:
            Event data at that index
        """
        if not self.is_active:
            raise ValueError("Replay not started")
        
        if index < 0 or index >= len(self.events):
            raise ValueError(f"Index {index} out of range")
        
        self.current_index = index
        event = self.events[index]
        
        return {
            "event": event.to_dict(),
            "progress": self.get_progress()
        }
    
    def get_progress(self) -> Dict[str, Any]:
        """
        Get current replay progress.
        
        Returns:
            Dict with progress information
        """
        if not self.is_active:
            return {
                "active": False
            }
        
        total = len(self.events)
        current = self.current_index
        percentage = (current / total * 100) if total > 0 else 0
        
        current_event = self.events[current] if current < total else None
        current_round = current_event.round_num if current_event else None
        
        return {
            "active": True,
            "current_index": current,
            "total_events": total,
            "progress_percentage": round(percentage, 2),
            "current_round": current_round,
            "total_rounds": self._get_total_rounds(),
            "at_start": current == 0,
            "at_end": current >= total
        }
    
    def get_round_summary(self, round_num: int) -> Dict[str, Any]:
        """
        Get summary of a specific round.
        
        Args:
            round_num: Round number
            
        Returns:
            Dict with round summary
        """
        round_events = [e for e in self.events if e.round_num == round_num]
        
        descriptions = [e for e in round_events if e.event_type == "description"]
        eliminations = [e for e in round_events if e.event_type == "elimination"]
        
        return {
            "round": round_num,
            "total_events": len(round_events),
            "descriptions": len(descriptions),
            "eliminations": len(eliminations),
            "events": [e.to_dict() for e in round_events]
        }
    
    def get_agent_timeline(self, agent_id: str) -> List[Dict[str, Any]]:
        """
        Get all events for a specific agent.
        
        Args:
            agent_id: Agent ID
            
        Returns:
            List of events involving this agent
        """
        agent_events = []
        
        for event in self.events:
            if event.event_type == "description":
                if event.data.get("agent_id") == agent_id:
                    agent_events.append(event.to_dict())
            elif event.event_type == "elimination":
                if event.data.get("eliminated_id") == agent_id:
                    agent_events.append(event.to_dict())
                # Also include if agent voted
                vote_details = event.data.get("vote_details", [])
                for vote in vote_details:
                    if vote.get("voter") == agent_id:
                        agent_events.append({
                            **event.to_dict(),
                            "agent_action": "voted",
                            "vote_target": vote.get("voted_for")
                        })
                        break
        
        return agent_events
    
    def _get_total_rounds(self) -> int:
        """Get total number of rounds in replay."""
        if not self.events:
            return 0
        return max(e.round_num for e in self.events)
    
    def stop_replay(self) -> Dict[str, Any]:
        """
        Stop current replay.
        
        Returns:
            Dict with final statistics
        """
        if not self.is_active:
            return {"status": "not_active"}
        
        stats = {
            "status": "stopped",
            "snapshot_id": self.snapshot_id,
            "total_events": len(self.events),
            "events_viewed": self.current_index,
            "completion_percentage": round(
                (self.current_index / len(self.events) * 100) if self.events else 0,
                2
            )
        }
        
        self.is_active = False
        logger.info(f"Stopped replay: {stats}")
        
        return stats
    
    def export_replay_data(self) -> Dict[str, Any]:
        """
        Export complete replay data for analysis.
        
        Returns:
            Dict with all replay data
        """
        if not self.is_active:
            raise ValueError("Replay not started")
        
        return {
            "snapshot_id": self.snapshot_id,
            "total_events": len(self.events),
            "total_rounds": self._get_total_rounds(),
            "events": [e.to_dict() for e in self.events],
            "progress": self.get_progress()
        }


# Global replay manager instance
_replay_manager = ReplayManager()


def get_replay_manager() -> ReplayManager:
    """Get global replay manager instance."""
    return _replay_manager
