"""
Memory service with dependency graph and corruption mechanism.

Simplified version without mem0 for initial development.
"""

import random
from typing import List, Dict, Any, Optional, Set
from datetime import datetime
import networkx as nx
import logging
logger = logging.getLogger(__name__)

from config.settings import settings


class MemoryFragment:
    """Represents a single memory with metadata."""
    
    def __init__(
        self,
        memory_id: str,
        content: str,
        round_number: int,
        agent_id: str,
        is_corrupted: bool = False,
        dependencies: Optional[List[str]] = None
    ):
        self.memory_id = memory_id
        self.content = content
        self.round_number = round_number
        self.agent_id = agent_id
        self.is_corrupted = is_corrupted
        self.dependencies = dependencies or []
        self.created_at = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "content": self.content,
            "round_number": self.round_number,
            "agent_id": self.agent_id,
            "is_corrupted": self.is_corrupted,
            "dependencies": self.dependencies,
            "created_at": self.created_at.isoformat()
        }


class AgentMemorySystem:
    """Memory system for a single agent with corruption and dependencies."""
    
    def __init__(self, agent_id: str, iq_level: str):
        self.agent_id = agent_id
        self.iq_level = iq_level
        self.dependency_graph = nx.DiGraph()
        self.memories: Dict[str, MemoryFragment] = {}
        
        # Memory decay rates based on IQ
        self.decay_rate = {
            "High": settings.MEMORY_DECAY_HIGH,
            "Mid": settings.MEMORY_DECAY_MID,
            "Low": settings.MEMORY_DECAY_LOW
        }.get(iq_level, settings.MEMORY_DECAY_MID)
        
        self.cascade_probability = settings.MEMORY_CASCADE_PROBABILITY
        
        logger.info(f"Initialized memory system for agent {agent_id} (simplified mode)")
    
    def add_memory(
        self,
        content: str,
        round_number: int,
        dependencies: Optional[List[str]] = None
    ) -> str:
        """
        Add a new memory with optional dependencies.
        
        Args:
            content: Memory content
            round_number: Game round when memory was created
            dependencies: List of memory IDs this memory depends on
            
        Returns:
            Memory ID
        """
        memory_id = f"{self.agent_id}_r{round_number}_{len(self.memories)}"
        
        fragment = MemoryFragment(
            memory_id=memory_id,
            content=content,
            round_number=round_number,
            agent_id=self.agent_id,
            dependencies=dependencies or []
        )
        
        self.memories[memory_id] = fragment
        self.dependency_graph.add_node(memory_id)
        
        # Add dependency edges
        if dependencies:
            for dep_id in dependencies:
                if dep_id in self.memories:
                    self.dependency_graph.add_edge(dep_id, memory_id)
        
        logger.debug(f"Added memory {memory_id}: {content[:50]}...")
        return memory_id
    
    def apply_memory_decay(self, current_round: int) -> List[str]:
        """
        Apply random memory corruption based on decay rate.
        
        Args:
            current_round: Current game round
            
        Returns:
            List of corrupted memory IDs
        """
        corrupted_ids = []
        
        for memory_id, fragment in self.memories.items():
            if fragment.is_corrupted:
                continue
            
            # Probability of corruption increases with time
            age = current_round - fragment.round_number
            corruption_prob = self.decay_rate * (1 + age * 0.1)
            
            if random.random() < corruption_prob:
                fragment.is_corrupted = True
                corrupted_ids.append(memory_id)
                logger.info(f"Memory corrupted: {memory_id}")
                
                # Cascade corruption to dependent memories
                self._cascade_corruption(memory_id)
        
        return corrupted_ids
    
    def _cascade_corruption(self, parent_memory_id: str):
        """
        Propagate corruption to dependent memories.
        
        Args:
            parent_memory_id: ID of the corrupted parent memory
        """
        if parent_memory_id not in self.dependency_graph:
            return
        
        # Get all memories that depend on this one
        dependent_ids = list(self.dependency_graph.successors(parent_memory_id))
        
        for dep_id in dependent_ids:
            if dep_id in self.memories and not self.memories[dep_id].is_corrupted:
                if random.random() < self.cascade_probability:
                    self.memories[dep_id].is_corrupted = True
                    logger.info(f"Cascaded corruption to: {dep_id}")
                    # Recursively cascade
                    self._cascade_corruption(dep_id)
    
    def get_memories(
        self,
        include_corrupted: bool = False,
        max_count: Optional[int] = None
    ) -> List[MemoryFragment]:
        """
        Get memories, optionally filtering corrupted ones.
        
        Args:
            include_corrupted: Whether to include corrupted memories
            max_count: Maximum number of memories to return
            
        Returns:
            List of memory fragments
        """
        memories = list(self.memories.values())
        
        if not include_corrupted:
            memories = [m for m in memories if not m.is_corrupted]
        
        # Sort by round number (most recent first)
        memories.sort(key=lambda m: m.round_number, reverse=True)
        
        if max_count:
            memories = memories[:max_count]
        
        return memories
    
    def search_memories(
        self,
        query: str,
        top_k: int = 5,
        include_corrupted: bool = False
    ) -> List[MemoryFragment]:
        """
        Search for relevant memories (simplified without semantic search).
        
        Args:
            query: Search query
            top_k: Number of results to return
            include_corrupted: Whether to include corrupted memories
            
        Returns:
            List of relevant memory fragments
        """
        # Simplified: just return most recent memories
        logger.debug("Using simplified memory search (no semantic search)")
        return self.get_memories(include_corrupted, top_k)
    
    def get_conversation_context(
        self,
        current_round: int,
        max_memories: int = 10
    ) -> str:
        """
        Build conversation context from memories for LLM prompt.
        
        Args:
            current_round: Current game round
            max_memories: Maximum number of memories to include
            
        Returns:
            Formatted context string
        """
        memories = self.get_memories(include_corrupted=True, max_count=max_memories)
        
        if not memories:
            return "【你还没有任何记忆】"
        
        context_parts = []
        for memory in memories:
            if memory.is_corrupted:
                context_parts.append(f"第{memory.round_number}轮: 【记忆受损：你记不清此轮细节】")
            else:
                context_parts.append(f"第{memory.round_number}轮: {memory.content}")
        
        return "\n".join(context_parts)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize memory system state."""
        return {
            "agent_id": self.agent_id,
            "iq_level": self.iq_level,
            "decay_rate": self.decay_rate,
            "memories": {
                mid: mem.to_dict() for mid, mem in self.memories.items()
            },
            "dependency_graph": nx.node_link_data(self.dependency_graph)
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentMemorySystem":
        """Deserialize memory system state."""
        system = cls(data["agent_id"], data["iq_level"])
        
        # Restore memories
        for mid, mem_data in data["memories"].items():
            fragment = MemoryFragment(
                memory_id=mem_data["memory_id"],
                content=mem_data["content"],
                round_number=mem_data["round_number"],
                agent_id=mem_data["agent_id"],
                is_corrupted=mem_data["is_corrupted"],
                dependencies=mem_data["dependencies"]
            )
            system.memories[mid] = fragment
        
        # Restore dependency graph
        system.dependency_graph = nx.node_link_graph(data["dependency_graph"])
        
        return system
