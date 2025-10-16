"""
Mem0-powered Learning Memory Manager

Handles storage and retrieval of learnings from multiple sources:
- Human proactive (agent asks, human responds)
- Human interrupt (human interrupts execution)
- Agent self-exploration (successful self-recovery)

Uses Mem0 for automatic vector embeddings and semantic search
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid
import json
import os

try:
    from mem0 import Memory
    MEM0_AVAILABLE = True
except ImportError:
    MEM0_AVAILABLE = False
    print("WARNING: mem0ai not installed. Install with: pip install mem0ai")

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from agent.feedback.schemas import LearningEntry, LearningSource


class LearningMemoryManager:
    """
    Mem0-powered memory manager for HITL learnings

    Features:
    - Multi-level memory (session, agent, global)
    - Automatic vector embeddings via Mem0
    - Semantic search across all learning sources
    - Session tracking
    """

    def __init__(self):
        """Initialize memory manager with default Mem0 configuration"""
        if not MEM0_AVAILABLE:
            raise ImportError("mem0ai package required. Install with: pip install mem0ai")

        # Initialize Mem0 with default configuration
        # Uses Qdrant for vector store (local) and OpenAI for embeddings
        try:
            self.memory = Memory()
        except Exception as e:
            print(f"[Warning] Mem0 initialization failed: {e}")
            print("[Warning] Continuing without Mem0 - will use JSON-only storage")
            self.memory = None

        # Session storage directory
        self.sessions_dir = "agent/feedback/memory/sessions"
        os.makedirs(self.sessions_dir, exist_ok=True)

        print("[Memory] Initialized Mem0-powered learning memory manager")

    def store_learning(
        self,
        session_id: str,
        source: LearningSource,
        learning_data: Dict[str, Any],
        context: Dict[str, Any]
    ) -> str:
        """
        Store learning entry in Mem0

        Args:
            session_id: Current session ID
            source: Learning source (human_proactive, human_interrupt, agent_self_exploration)
            learning_data: Learning content
            context: Execution context (task, step, ui_state)

        Returns:
            Learning ID
        """
        learning_id = f"learn_{uuid.uuid4().hex[:8]}"

        # Create learning entry
        learning = LearningEntry(
            learning_id=learning_id,
            session_id=session_id,
            source=source,
            task=context.get("task", ""),
            step_num=context.get("step"),
            ui_state=context.get("ui_state"),
            **learning_data
        )

        # Format as conversational message for Mem0
        message = self._format_learning_as_message(learning, source)

        # Store in Mem0 with multi-level identifiers
        if self.memory:
            try:
                self.memory.add(
                    messages=[{"role": "user", "content": message}],
                    user_id=session_id,  # Session-level memory
                    agent_id="asammdf_executor",  # Agent-level memory
                    metadata={
                        "learning_id": learning_id,
                        "source": source.value,
                        "task": learning.task,
                        "step": learning.step_num,
                        "timestamp": learning.timestamp
                    }
                )

                print(f"  [Stored] {source.value} learning: {learning_id} (Mem0)")

            except Exception as e:
                print(f"  [Error] Failed to store in Mem0: {e}")

        # Always save to JSON for backup
        self._save_learning_json(learning)
        if not self.memory:
            print(f"  [Stored] {source.value} learning: {learning_id} (JSON only)")

        return learning_id

    def _format_learning_as_message(
        self,
        learning: LearningEntry,
        source: LearningSource
    ) -> str:
        """
        Format learning as conversational message for Mem0

        Args:
            learning: Learning entry
            source: Learning source

        Returns:
            Formatted message
        """
        if source == LearningSource.HUMAN_PROACTIVE:
            return (
                f"Task: {learning.task}. "
                f"Human correction: {learning.human_reasoning}. "
                f"Original action was {learning.original_action.get('tool_name')}, "
                f"corrected to {learning.corrected_action.get('tool_name') if learning.corrected_action else 'N/A'}."
            )

        elif source == LearningSource.HUMAN_INTERRUPT:
            return (
                f"Task: {learning.task}. "
                f"Human interrupted at step {learning.step_num}: {learning.human_reasoning}. "
                f"Correction provided: {learning.corrected_action}."
            )

        elif source == LearningSource.AGENT_SELF_EXPLORATION:
            return (
                f"Task: {learning.task}. "
                f"Agent self-recovered from error: {learning.original_error}. "
                f"Recovery approach: {learning.recovery_approach}. "
                f"Why it worked: {learning.why_it_worked}."
            )

        return f"Learning for task: {learning.task}"

    def _save_learning_json(self, learning: LearningEntry):
        """Save learning to JSON file as backup"""
        learning_file = os.path.join(
            self.sessions_dir,
            f"{learning.session_id}_{learning.learning_id}.json"
        )

        with open(learning_file, 'w', encoding='utf-8') as f:
            json.dump(learning.model_dump(), f, indent=2)

    def retrieve_all_learnings_for_task(
        self,
        task: str,
        session_id: Optional[str] = None,
        limit: int = 10
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Retrieve all relevant learnings for a task

        Args:
            task: Task description
            session_id: Optional session ID to include session-specific learnings
            limit: Maximum number of learnings to retrieve

        Returns:
            Dictionary grouped by learning source
        """
        if not self.memory:
            print("  [Warning] Mem0 not available, returning empty results")
            return {
                "human_proactive": [],
                "human_interrupt": [],
                "agent_self_exploration": []
            }

        try:
            # Search Mem0 for relevant learnings
            query = f"Task: {task}"

            memories = self.memory.search(
                query=query,
                user_id=session_id,  # Include session if provided
                agent_id="asammdf_executor",  # Include agent's learnings
                limit=limit
            )

            # Group by source
            grouped_learnings = {
                "human_proactive": [],
                "human_interrupt": [],
                "agent_self_exploration": []
            }

            for mem in memories:
                source = mem.get("metadata", {}).get("source", "unknown")
                if source in grouped_learnings:
                    grouped_learnings[source].append({
                        "memory": mem.get("memory", ""),
                        "metadata": mem.get("metadata", {}),
                        "relevance": mem.get("relevance", 0.0)
                    })

            # Print summary
            total = sum(len(learnings) for learnings in grouped_learnings.values())
            if total > 0:
                print(f"  [Retrieved] {total} learnings for task: {task}")
                for source, learnings in grouped_learnings.items():
                    if learnings:
                        print(f"    - {source}: {len(learnings)}")

            return grouped_learnings

        except Exception as e:
            print(f"  [Error] Failed to retrieve learnings: {e}")
            return {
                "human_proactive": [],
                "human_interrupt": [],
                "agent_self_exploration": []
            }

    def get_all_session_memories(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Get all memories for a specific session

        Args:
            session_id: Session identifier

        Returns:
            List of all memories in the session
        """
        if not self.memory:
            print("  [Warning] Mem0 not available")
            return []

        try:
            memories = self.memory.get_all(user_id=session_id)
            print(f"  [Retrieved] {len(memories)} memories for session: {session_id}")
            return memories

        except Exception as e:
            print(f"  [Error] Failed to get session memories: {e}")
            return []

    def clear_session_memories(self, session_id: str):
        """
        Clear all memories for a session

        Args:
            session_id: Session to clear
        """
        try:
            # Mem0 doesn't have direct delete by user_id, so we'd need to delete individually
            # For now, just log
            print(f"  [Clear] Session memories: {session_id}")
            # Note: Implement if needed by getting all memory IDs and deleting

        except Exception as e:
            print(f"  [Error] Failed to clear session: {e}")


if __name__ == "__main__":
    """Test memory manager"""

    print("Testing Mem0-Powered Learning Memory Manager\n")

    # Initialize
    manager = LearningMemoryManager()

    # Test 1: Store human proactive learning
    print("Test 1: Store human proactive learning")
    learning1_id = manager.store_learning(
        session_id="test_session_001",
        source=LearningSource.HUMAN_PROACTIVE,
        learning_data={
            "original_action": {"tool_name": "Click-Tool", "loc": [450, 300]},
            "corrected_action": {"tool_name": "Shortcut-Tool", "shortcut": ["ctrl", "m"]},
            "human_reasoning": "Use keyboard shortcut instead of clicking button"
        },
        context={
            "task": "Concatenate MF4 files",
            "step": 5,
            "ui_state": "Menu bar visible"
        }
    )

    # Test 2: Store agent self-exploration learning
    print("\nTest 2: Store agent self-exploration learning")
    learning2_id = manager.store_learning(
        session_id="test_session_001",
        source=LearningSource.AGENT_SELF_EXPLORATION,
        learning_data={
            "original_action": {"tool_name": "Click-Tool", "loc": [500, 400]},
            "original_error": "Element not found at coordinates",
            "recovery_approach": "Used State-Tool to refresh UI, found element at new location",
            "why_it_worked": "UI state had changed dynamically, refreshing cache revealed new coordinates",
            "agent_reasoning": "Self-recovery by adapting to dynamic UI"
        },
        context={
            "task": "Concatenate MF4 files",
            "step": 15
        }
    )

    # Test 3: Store human interrupt learning
    print("\nTest 3: Store human interrupt learning")
    learning3_id = manager.store_learning(
        session_id="test_session_001",
        source=LearningSource.HUMAN_INTERRUPT,
        learning_data={
            "original_action": {"tool_name": "Click-Tool", "loc": [600, 200]},
            "corrected_action": {"type": "skip_step"},
            "human_reasoning": "This step is not needed, skip it"
        },
        context={
            "task": "Concatenate MF4 files",
            "step": 20
        }
    )

    # Test 4: Retrieve learnings
    print("\nTest 4: Retrieve learnings for similar task")
    learnings = manager.retrieve_all_learnings_for_task(
        task="Concatenate MF4 files",
        session_id="test_session_001",
        limit=5
    )

    for source, items in learnings.items():
        if items:
            print(f"\n  {source}:")
            for item in items:
                print(f"    - {item['memory'][:100]}...")

    # Test 5: Get all session memories
    print("\nTest 5: Get all session memories")
    all_memories = manager.get_all_session_memories("test_session_001")
    print(f"  Total session memories: {len(all_memories)}")

    print("\n[SUCCESS] Memory manager tests completed!")
