"""
Adaptive low-level executor that interprets high-level plans and resolves symbolic references
Uses a lightweight LLM (GPT-4o-mini) to understand intent and make execution decisions
"""

import json
from typing import Dict, Any, List, Optional, Tuple
from openai import OpenAI
import os
from dotenv import load_dotenv
from datetime import datetime

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from agent.planning.schemas import ActionSchema, ExecutionResult, PlanSchema
from agent.execution.mcp_client import MCPClient
from agent.prompts.coordinate_resolution_prompt import get_coordinate_resolution_prompt
from agent.utils.cost_tracker import track_api_call

# HITL imports
try:
    from agent.feedback.human_observer import HumanObserver
    from agent.feedback.schemas import FailureLearning
    HITL_AVAILABLE = True
except ImportError:
    HITL_AVAILABLE = False
    print("[Warning] HITL components not available")

load_dotenv()


class StateCache:
    """Cache for State-Tool outputs to resolve symbolic references"""

    def __init__(self):
        self.latest_state: Optional[str] = None

    def add_state(self, state_output: str) -> None:
        """Add a state output as the latest state

        Args:
            state_output: The state output to cache
        """
        self.latest_state = state_output

    def get_latest_state(self) -> Optional[str]:
        """Get the most recent state output"""
        return self.latest_state


class AdaptiveExecutor:
    """
    Low-level executor that:
    - Resolves symbolic coordinate references (e.g., 'last_state:menu:Mode')
    - Interprets unclear instructions and makes execution decisions
    - Calls additional actions if needed to reach desired state
    - Uses GPT-4o-mini for lightweight reasoning
    """

    def __init__(
        self,
        mcp_client: MCPClient,
        api_key: Optional[str] = None,
        knowledge_retriever=None,
        plan_filepath: Optional[str] = None,
        human_observer: Optional['HumanObserver'] = None,
        session_id: Optional[str] = None,
        parameters: Optional[Dict[str, str]] = None
    ):
        """
        Initialize adaptive executor

        Args:
            mcp_client: MCP client for tool execution
            api_key: OpenAI API key (defaults to env var)
            knowledge_retriever: Optional KnowledgeRetriever instance for KB queries and enriched learning
            plan_filepath: Optional path to plan file for task name retrieval
            human_observer: Optional HumanObserver for HITL feedback
            session_id: Optional session ID for tracking
            parameters: Optional path parameters for parameterized tasks
        """
        self.mcp_client = mcp_client
        self.state_cache = StateCache()
        self.knowledge_retriever = knowledge_retriever
        self.plan_filepath = plan_filepath
        self.parameters = parameters or {}  # Path parameters for substitution

        # HITL components
        self.human_observer = human_observer
        self.session_id = session_id or "default_session"

        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY required")

        self.client = OpenAI(api_key=self.api_key, timeout=60.0)
        self.model = "gpt-4o-mini"  # Lightweight, fast model

    def _resolve_coordinates(
        self,
        element_refs: List[str],
        action: ActionSchema,
        tool_schema: Optional[Dict] = None
    ) -> Tuple[Optional[List[int]], Optional[str]]:
        """
        Resolve element reference(s) to actual coordinates using latest cached state
        LLM intelligently interprets any reference format and finds matching coordinates

        Args:
            element_refs: List of element descriptions/references in any format
                         Examples: ['last_state:menu:Mode', 'Mode menu', 'menu named Mode']
            action: The action being executed (provides tool name, arguments, and reasoning)
            tool_schema: Optional schema for the MCP tool (describes expected arguments)

        Returns:
            Tuple of ([x, y] coordinates or None, error_message or None)
        """
        state_output = self.state_cache.get_latest_state()

        if not state_output:
            error_msg = f"No cached state available to resolve coordinates"
            print(f"  ✗ {error_msg}")
            return None, error_msg

        # Get prompt from centralized module
        prompt = get_coordinate_resolution_prompt(element_refs, action, state_output, tool_schema)

        try:
            print(f"Resolving Coordinates with GPT")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0,
                response_format={"type": "json_object"}
            )

            # Track API cost
            usage = response.usage
            cost = track_api_call(
                model=self.model,
                component="resolution",
                input_tokens=usage.prompt_tokens,
                output_tokens=usage.completion_tokens,
                task_context=f"{action.tool_name}: {element_refs[0][:50] if element_refs else 'N/A'}"
            )
            print(f"  💰 Resolution cost: ${cost:.6f} ({usage.prompt_tokens:,} in + {usage.completion_tokens:,} out tokens)")

            result = json.loads(response.choices[0].message.content.strip())

            if result.get("found"):
                coords = result.get("coordinates")
                matched_ref = result.get("matched_ref", "unknown")
                adaptation = result.get("adaptation", "")

                if adaptation:
                    print(f"  ✓ Resolved '{matched_ref}' to {coords} (Adapted: {adaptation})")
                else:
                    print(f"  ✓ Resolved '{matched_ref}' to {coords}")
                return coords, None
            else:
                reason = result.get('reason', 'Unknown reason')
                suggestion = result.get('suggestion', '')
                error_msg = f"Could not resolve any of {len(element_refs)} alternative(s): {reason}"
                if suggestion:
                    error_msg += f" | Suggestion: {suggestion}"
                print(f"  ! {error_msg}")
                return None, error_msg

        except Exception as e:
            error_msg = f"Error resolving coordinates: {e}"
            print(f"  ! {error_msg}")
            return None, error_msg

    def _resolve_action_arguments(self, action: ActionSchema) -> Dict[str, Any]:
        """
        Resolve element references in action arguments to actual coordinates

        Flexible - accepts any reference format (structured or natural language):
        - Structured: ['last_state:menu:Mode']
        - Natural: ['Mode menu', 'File button']
        - Mixed: ['last_state:menu:File', 'Files menu', 'button named File']

        Args:
            action: Action with potentially symbolic arguments

        Returns:
            Resolved arguments dictionary

        Raises:
            ValueError: If resolution fails
        """
        resolved_args = {}

        # Tools that need coordinate resolution for their 'loc' parameter
        # Other tools (like Shortcut-Tool) use lists for other purposes
        needs_coordinate_resolution = ('loc' in action.tool_arguments)

        # Get tool schema for better context
        tool_schema = None
        if needs_coordinate_resolution:
            try:
                mcp_tools = self.mcp_client.list_tools_sync()
                for tool in mcp_tools:
                    if tool.get('name') == action.tool_name:
                        tool_schema = tool.get('schema', {})
                        break
            except Exception as e:
                print(f"  ! Could not fetch tool schema: {e}")

        for key, value in action.tool_arguments.items():
            # Check if value is a list of strings (potential element references)
            # AND if this tool/parameter combination needs coordinate resolution
            if (isinstance(value, list) and len(value) >= 1 and
                all(isinstance(item, str) for item in value) and key == 'loc'):

                print(f"  → Resolving '{key}' with {len(value)} alternative(s)")

                # Pass full action context and tool schema to resolver
                coords, error_msg = self._resolve_coordinates(
                    element_refs=value,
                    action=action,
                    tool_schema=tool_schema
                )

                if coords:
                    resolved_args[key] = coords
                else:
                    raise ValueError(error_msg)
            else:
                # Use value as-is (not a reference list or doesn't need resolution)
                resolved_args[key] = value

        return resolved_args

    def execute_action(
        self,
        action: ActionSchema,
        context: List[ActionSchema] = None,
        step_num: Optional[int] = None
    ) -> ExecutionResult:
        """
        Execute a single action with adaptive resolution

        Args:
            action: High-level action to execute
            context: Previous actions for context
            step_num: Optional step number (1-indexed for display, KB storage, and logs)

        Returns:
            Execution result
        """
        from agent.utils.parameter_substitution import substitute_in_action

        context = context or []

        print(f"\n[Adaptive Executor] {action.tool_name}")
        print(f"  Arguments: {action.tool_arguments}")
        print(f"  Reasoning: {action.reasoning}")

        # Step 1: Substitute parameters if this is a parameterized task
        if self.parameters:
            try:
                action_dict = action.model_dump()
                substituted_action_dict = substitute_in_action(
                    action_dict,
                    self.parameters,
                    strict=False  # Don't fail if some placeholders aren't in parameters
                )
                action = ActionSchema(**substituted_action_dict)
                print(f"  [Parameterized] Substituted {len(self.parameters)} parameter(s)")
            except Exception as e:
                print(f"  [Warning] Parameter substitution failed: {e}")
                # Continue with original action if substitution fails

        # Step 2: Check if this is a State-Tool call
        if action.tool_name == 'State-Tool':
            result = self.mcp_client.execute_action_sync(action)

            # Cache the state output
            if result.success and result.evidence:
                self.state_cache.add_state(result.evidence)
                print(f"  ✓ Cached as latest state")

            return result

        # Step 3: Resolve symbolic references in arguments
        try:
            resolved_args = self._resolve_action_arguments(action)
            resolved_action = ActionSchema(
                tool_name=action.tool_name,
                tool_arguments=resolved_args,
                reasoning=action.reasoning
            )

            print(f"  → Resolved arguments: {resolved_args}")

        except Exception as e:
            print(f"  ✗ Failed to resolve arguments: {e}")

            # Handle failure: attach learning to KB and stop
            if HITL_AVAILABLE and step_num is not None:
                return self._handle_failure(action, step_num, str(e))

            # Fallback: return failure
            return ExecutionResult(
                success=False,
                action=action.tool_name,
                error=f"Failed to resolve arguments: {e}"
            )

        # Step 3: Execute the resolved action
        result = self.mcp_client.execute_action_sync(resolved_action)

        return result

    def _create_failure_learning(
        self,
        failed_action: ActionSchema,
        step_display: int,
        error: str,
        task: str
    ):
        """
        Create failure learning (without related docs - those retrieved during planning)

        Args:
            failed_action: The action that failed
            step_display: Step number that failed (1-indexed for human readability)
            error: Error message
            task: Original task being executed

        Returns:
            FailureLearning object
        """
        from agent.feedback.schemas import FailureLearning

        # Create learning with 1-indexed step number
        # LLM planner will see failure history and determine alternative approach
        learning = FailureLearning(
            task=task,
            step_num=step_display,  # Store 1-indexed for human consistency
            original_action=failed_action.model_dump(),
            original_error=error
        )

        return learning

    def _handle_failure(
        self,
        failed_action: ActionSchema,
        step_display: int,
        error: str
    ) -> ExecutionResult:
        """
        Handle action failure by creating failure learning and stopping execution

        This method:
        1. Creates a FailureLearning (with 1-indexed step number)
        2. Attaches the learning to the responsible KB item (via kb_source)
        3. Updates KB trust score
        4. Updates KB vector metadata
        5. Returns failure result (stops execution)

        Related docs will be retrieved dynamically during next planning phase.
        User must explicitly rerun the task to apply learnings.

        Args:
            failed_action: The action that failed
            step_display: Step number that failed (1-indexed for display)
            error: Error message

        Returns:
            ExecutionResult indicating failure
        """
        print(f"\n{'='*80}")
        print(f"⚠️  FAILURE DETECTED - Step {step_display} failed")
        print(f"{'='*80}")
        print(f"Action: {failed_action.tool_name}")
        print(f"Error: {error}")

        # Get task name from plan filepath if available
        task = "Unknown task"
        if self.plan_filepath and os.path.exists(self.plan_filepath):
            try:
                with open(self.plan_filepath, 'r', encoding='utf-8') as f:
                    plan_data = json.load(f)
                    task = plan_data.get("task", "Unknown task")
            except Exception as e:
                print(f"  ! Could not load task from plan: {e}")

        try:
            # Create failure learning (with 1-indexed step number)
            learning = self._create_failure_learning(failed_action, step_display, error, task)

            # Attach learning to KB item if kb_source is set
            if failed_action.kb_source:
                self._attach_learning_to_kb(
                    kb_id=failed_action.kb_source,
                    learning=learning
                )
                print(f"  [KB Learning] Attached to KB item: {failed_action.kb_source}")
            else:
                print(f"  [KB Learning] No KB source - action was not from KB")
                print(f"  [KB Learning] Learning created but not attached")

        except Exception as e:
            print(f"  [Warning] Failed to create/attach learning: {e}")
            import traceback
            traceback.print_exc()

        print(f"\n{'='*80}")
        print(f"🛑 EXECUTION STOPPED")
        print(f"{'='*80}")
        print(f"Learning attached to KB. Please rerun the task to apply learnings.")
        print(f"{'='*80}\n")

        # Return failure result (stops execution)
        return ExecutionResult(
            success=False,
            action=failed_action.tool_name,
            error=error
        )

    def _attach_learning_to_kb(
        self,
        kb_id: str,
        learning
    ):
        """
        Attach a learning to a KB item in the catalog and persist

        Args:
            kb_id: Knowledge base item ID to attach learning to
            learning: FailureLearning or HumanInterruptLearning object
        """
        catalog_path = "agent/knowledge_base/parsed_knowledge/knowledge_catalog.json"

        try:
            # Load catalog
            with open(catalog_path, 'r', encoding='utf-8') as f:
                catalog_data = json.load(f)

            # Find KB item and attach learning
            kb_found = False
            for item in catalog_data:
                if item.get("knowledge_id") == kb_id:
                    # Initialize kb_learnings if doesn't exist
                    if "kb_learnings" not in item:
                        item["kb_learnings"] = []

                    # Append learning as dict
                    item["kb_learnings"].append(learning.model_dump())

                    # Update trust score (decrease with each failure)
                    current_trust = item.get("trust_score", 1.0)
                    item["trust_score"] = max(0.5, current_trust * 0.95)

                    kb_found = True
                    print(f"  [KB] Updated '{kb_id}': {len(item['kb_learnings'])} learnings, trust={item['trust_score']:.2f}")
                    break

            if not kb_found:
                print(f"  [Warning] KB item '{kb_id}' not found in catalog")
                return

            # Save updated catalog
            with open(catalog_path, 'w', encoding='utf-8') as f:
                json.dump(catalog_data, f, indent=2, ensure_ascii=False)

            print(f"  [KB] Catalog updated successfully")

            # Update vector metadata for this KB item (reloads from catalog)
            if self.knowledge_retriever:
                try:
                    self.knowledge_retriever.update_vector_metadata(kb_id=kb_id)
                    print(f"  [KB Vector] Updated metadata from catalog for: {kb_id}")
                except Exception as e:
                    print(f"  [Warning] Could not update vector metadata: {e}")

        except Exception as e:
            print(f"  [Error] Failed to attach learning to KB: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    """Test adaptive executor"""
    from agent.execution.mcp_client import get_mcp_client

    # Create test action with symbolic reference (using new format)
    test_action = ActionSchema(
        tool_name='Click-Tool',
        tool_arguments={
            'loc': ['last_state:menu:Mode'],
            'button': 'left',
            'clicks': 1
        },
        reasoning="Click the Mode menu"
    )

    # Mock state output
    mock_state = """
    Desktop UI Elements:
    - Window: asammdf 8.6.10 (1920, 1080)
      - Menu Bar (0, 0, 1920, 30)
        - Menu: File (10, 5) [80x20]
        - Menu: Mode (100, 5) [80x20]
        - Menu: Help (190, 5) [80x20]
    """

    client = get_mcp_client()
    executor = AdaptiveExecutor(mcp_client=client, plan_filepath=r"agent\plans\Concatenate_all_MF4_files_in_C__Users_ADMIN_Downlo_bad75d6c.json")

    # Add mock state (only need to add once - it becomes the latest state)
    executor.state_cache.add_state(mock_state)

    # Test resolution
    result = executor.execute_action(test_action)
    print(f"\nResult: {result}")
