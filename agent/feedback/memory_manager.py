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
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

try:
    from mem0 import MemoryClient
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
        """Initialize memory manager with Mem0 Platform (cloud-based)"""
        if not MEM0_AVAILABLE:
            raise ImportError("mem0ai package required. Install with: pip install mem0ai")

        # Initialize Mem0 Platform client with API key from .env
        api_key = os.getenv("MEM0_API_KEY")
        if not api_key:
            print("[Warning] MEM0_API_KEY not found in .env file")
            print("[Warning] Continuing without Mem0 - will use JSON-only storage")
            self.memory = None
        else:
            try:
                # Set API key in environment (MemoryClient reads from os.environ)
                os.environ["MEM0_API_KEY"] = api_key
                self.memory = MemoryClient()
                print("[Memory] Initialized Mem0 Platform client")
            except Exception as e:
                print(f"[Warning] Mem0 client initialization failed: {e}")
                print("[Warning] Continuing without Mem0 - will use JSON-only storage")
                self.memory = None

        # Session storage directory
        self.sessions_dir = "agent/feedback/memory/sessions"
        os.makedirs(self.sessions_dir, exist_ok=True)

        print("[Memory] Learning memory manager ready")

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
        # Schemas already match LearningEntry fields, just add context if needed
        context_fields = {}
        if "ui_state" not in learning_data and "ui_state" in context:
            context_fields["ui_state"] = context["ui_state"]

        learning = LearningEntry(
            learning_id=learning_id,
            session_id=session_id,
            source=source,
            **learning_data,
            **context_fields
        )

        # Format as conversational message for Mem0
        message = self._format_learning_as_message(learning, source)

        # Store in Mem0 with multi-level identifiers
        if self.memory:
            try:
                # Mem0 has 2000 char limit on metadata, so we store:
                # - Concise structured message in content (for semantic search)
                # - Essential metadata only (learning_id to lookup full JSON locally)
                # - Full data is in JSON backup files

                # Create concise but structured message for Mem0
                concise_message = self._format_concise_learning(learning, source)

                # Store as agent memory (agent learns across all sessions)
                # Use agent_id for cross-session learning, run_id for session-specific
                # NOTE: We format messages as single atomic facts to minimize splitting
                # Using infer=True (default) for better retrieval, but with atomic format
                add_params = {
                    "messages": [{"role": "user", "content": concise_message}],
                    "agent_id": "asammdf_executor",  # Agent-level: learns across sessions
                    "run_id": session_id,  # Session-level: track which session
                    "metadata": {
                        # Core identifiers only (stay under 2000 char limit)
                        "learning_id": learning_id,
                        "source": source.value,
                        "task": learning.task[:200],  # Truncate long tasks
                        "step": learning.step_num,
                        "timestamp": learning.timestamp,
                        # Reference to full data
                        "json_file": f"{session_id}_{learning_id}.json"
                    }
                }

                print(f"  [Mem0 Add] Sending parameters:")
                print(f"    - agent_id: asammdf_executor")
                print(f"    - run_id: {session_id}")
                print(f"    - message length: {len(concise_message)} chars")
                print(f"    - message: {concise_message[:100]}...")
                print(f"    - metadata: {list(add_params['metadata'].keys())}")

                result = self.memory.add(**add_params)

                # Process result from Mem0
                if isinstance(result, dict):
                    results_list = result.get('results', [])
                    num_memories = len(results_list)

                    print(f"  [Stored] {source.value} learning: {learning_id} (Mem0)")
                    print(f"  [Mem0 Result] {num_memories} memory/memories created")

                    # Show what memories were created (for debugging splitting)
                    for i, mem in enumerate(results_list):
                        if isinstance(mem, dict):
                            mem_text = mem.get('memory', str(mem))[:80]
                            print(f"    [{i+1}] {mem_text}...")

                    if num_memories > 1:
                        print(f"  [WARNING] Mem0 split message into {num_memories} memories")
                        print(f"  [WARNING] Consider making message more atomic")
                else:
                    print(f"  [Stored] {source.value} learning: {learning_id} (Mem0)")
                    print(f"  [Mem0 Result] {result}")

            except Exception as e:
                print(f"  [Error] Failed to store in Mem0: {e}")
                import traceback
                traceback.print_exc()

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
                f"Recovery approach: {learning.recovery_approach}."
            )

        return f"Learning for task: {learning.task}"

    def _format_concise_learning(
        self,
        learning: LearningEntry,
        source: LearningSource
    ) -> str:
        """
        Format concise learning for Mem0 as a SINGLE atomic fact

        Mem0 automatically extracts semantic facts from messages using an LLM.
        To prevent auto-splitting, we format the entire learning as ONE cohesive
        statement that cannot be logically divided.

        Args:
            learning: Learning entry
            source: Learning source

        Returns:
            Single atomic fact statement
        """
        import json

        if source == LearningSource.AGENT_SELF_EXPLORATION:
            # Format as single cohesive learning statement
            tool_name = learning.original_action.get('tool_name') if learning.original_action else 'Unknown'
            error = learning.original_error[:150] if learning.original_error else 'Unknown error'
            recovery = learning.recovery_approach[:200] if learning.recovery_approach else 'Unknown recovery'

            return (
                f"When executing '{learning.task[:100]}' at step {learning.step_num}, "
                f"the {tool_name} tool failed with '{error}', and successfully recovered by {recovery}."
            )

        elif source == LearningSource.HUMAN_INTERRUPT:
            # Format as single cohesive correction statement
            orig_tool = learning.original_action.get('tool_name') if learning.original_action else 'Unknown'
            corr_tool = learning.corrected_action.get('tool_name') if learning.corrected_action else 'alternative approach'
            reason = learning.human_reasoning[:200] if learning.human_reasoning else 'human preference'

            return (
                f"For task '{learning.task[:100]}' at step {learning.step_num}, "
                f"human corrected {orig_tool} to {corr_tool} because {reason}."
            )

        elif source == LearningSource.HUMAN_PROACTIVE:
            # Format as single cohesive guidance statement
            orig_tool = learning.original_action.get('tool_name') if learning.original_action else 'original approach'
            corr_tool = learning.corrected_action.get('tool_name') if learning.corrected_action else 'corrected approach'
            reason = learning.human_reasoning[:200] if learning.human_reasoning else 'human guidance'

            return (
                f"When working on '{learning.task[:100]}', "
                f"prefer {corr_tool} over {orig_tool} because {reason}."
            )

        return f"Learning acquired for task: {learning.task[:150]}"

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
        Retrieve all relevant learnings for a task using Mem0's semantic search

        Args:
            task: Task description to search for
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
            # Use Mem0's semantic search directly on the task
            # Search at agent level (cross-session) or filter by run_id if session provided
            search_params = {
                "query": task,
                "agent_id": "asammdf_executor",
                "run_id" : session_id,
                "limit": limit
            }
            if session_id:
                search_params["run_id"] = session_id

            print(f"  [Search] Query: {task[:100]}...")
            print(f"  [Search] Params: agent_id={search_params.get('agent_id')}, run_id={search_params.get('run_id', 'all')}")

            result = self.memory.search(**search_params)

            # MemoryClient.search() returns a list directly, not a dict
            if isinstance(result, list):
                memories = result
            else:
                # Fallback for unexpected format
                memories = result.get('results', []) if isinstance(result, dict) else []

            print(f"  [Retrieved] {len(memories)} memories from Mem0 search")

            # Group by source and reconstruct full learning data
            grouped_learnings = {
                "human_proactive": [],
                "human_interrupt": [],
                "agent_self_exploration": []
            }

            for mem in memories:
                # MemoryClient returns dict with 'memory', 'metadata', etc.
                if isinstance(mem, dict):
                    metadata = mem.get("metadata", {})
                    source = metadata.get("source", "unknown")

                    if source in grouped_learnings:
                        # Load complete learning from JSON file
                        json_file = metadata.get("json_file")
                        complete_learning = None

                        if json_file:
                            json_path = os.path.join(self.sessions_dir, json_file)
                            if os.path.exists(json_path):
                                try:
                                    with open(json_path, 'r', encoding='utf-8') as f:
                                        complete_learning = json.load(f)
                                except Exception as e:
                                    print(f"  [Warning] Failed to load {json_file}: {e}")

                        learning_data = {
                            "memory": mem.get("memory", ""),
                            "complete_learning": complete_learning,
                            "metadata": metadata,
                            "relevance": mem.get("score", 0.0)
                        }

                        grouped_learnings[source].append(learning_data)
                else:
                    # Skip unknown types
                    continue

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
            List of memories
        """
        if not self.memory:
            print("  [Warning] Mem0 not available")
            return []

        try:
            result = self.memory.get_all(user_id=session_id)
            # MemoryClient returns {'results': [...]}
            memories = result.get('results', []) if isinstance(result, dict) else []
            print(f"  [Retrieved] {len(memories)} memories for session: {session_id}")
            return memories

        except Exception as e:
            print(f"  [Error] Failed to get session memories: {e}")
            import traceback
            traceback.print_exc()
            return []

    def debug_all_memories(self) -> List[Dict[str, Any]]:
        """
        Debug: Get ALL memories stored in Mem0

        Returns:
            List of all memories
        """
        if not self.memory:
            print("  [Warning] Mem0 not available")
            return []

        try:
            # Try getting all memories without filters
            result = self.memory.get_all()
            # MemoryClient returns {'results': [...]}
            memories = result.get('results', []) if isinstance(result, dict) else []
            print(f"  [Debug] Found {len(memories)} total memories")
            for i, mem in enumerate(memories[:5]):  # Print first 5
                print(f"    [{i}] {mem.get('memory', '')[:100]}...")
            return memories

        except Exception as e:
            print(f"  [Error] Failed to get all memories: {e}")
            import traceback
            traceback.print_exc()
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
