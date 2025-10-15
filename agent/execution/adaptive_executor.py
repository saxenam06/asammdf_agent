"""
Adaptive low-level executor that interprets high-level plans and resolves symbolic references
Uses a lightweight LLM (GPT-4o-mini) to understand intent and make execution decisions
"""

import json
from typing import Dict, Any, List, Optional, Tuple
from openai import OpenAI
import os
from dotenv import load_dotenv

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from agent.planning.schemas import ActionSchema, ExecutionResult, PlanSchema
from agent.execution.mcp_client import MCPClient
from agent.planning.plan_recovery import PlanRecoveryManager
from agent.prompts.coordinate_resolution_prompt import get_coordinate_resolution_prompt
from agent.utils.cost_tracker import track_api_call

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

    def __init__(self, mcp_client: MCPClient, api_key: Optional[str] = None, knowledge_retriever=None, plan_filepath: Optional[str] = None):
        """
        Initialize adaptive executor

        Args:
            mcp_client: MCP client for tool execution
            api_key: OpenAI API key (defaults to env var)
            knowledge_retriever: Optional KnowledgeRetriever instance for KB queries
            plan_filepath: Optional path to plan file for recovery tracking
        """
        self.mcp_client = mcp_client
        self.state_cache = StateCache()
        self.knowledge_retriever = knowledge_retriever
        self.plan_filepath = plan_filepath
        self.recovery_manager = None

        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY required")

        self.client = OpenAI(api_key=self.api_key, timeout=60.0)
        self.model = "gpt-4o-mini"  # Lightweight, fast model

        # Initialize recovery manager if plan filepath provided
        if self.plan_filepath and os.path.exists(self.plan_filepath):
            self.recovery_manager = PlanRecoveryManager(
                plan_filepath=self.plan_filepath,
                knowledge_retriever=self.knowledge_retriever,
                api_key=self.api_key
            )

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
            step_num: Optional step number from the plan (used for state caching)

        Returns:
            Execution result
        """
        context = context or []

        print(f"\n[Adaptive Executor] {action.tool_name}")
        print(f"  Arguments: {action.tool_arguments}")
        print(f"  Reasoning: {action.reasoning}")

        # Step 1: Check if this is a State-Tool call
        if action.tool_name == 'State-Tool':
            result = self.mcp_client.execute_action_sync(action)

            # Cache the state output
            if result.success and result.evidence:
                self.state_cache.add_state(result.evidence)
                print(f"  ✓ Cached as latest state")

            return result

        # Step 2: Resolve symbolic references in arguments
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

            # Trigger replanning if recovery manager is available
            if self.recovery_manager and step_num is not None:
                return self._trigger_replanning(action, step_num, str(e))

            # Fallback: return failure
            return ExecutionResult(
                success=False,
                action=action.tool_name,
                error=f"Failed to resolve arguments: {e}"
            )

        # Step 3: Execute the resolved action
        result = self.mcp_client.execute_action_sync(resolved_action)

        return result

    def _trigger_replanning(
        self,
        failed_action: ActionSchema,
        step_num: int,
        error: str
    ) -> ExecutionResult:
        """
        Trigger replanning workflow when execution fails

        This method:
        1. Saves a snapshot of the current plan state with timestamp
        2. Summarizes what's completed vs what yet to be achieved
        3. Retrieves relevant knowledge from KB for the part yet to be achieved
        4. Generates a new plan with reasoning why it should work (includes latest UI state)
        5. Merges completed steps with the new plan
        6. Returns a signal to continue execution with the updated plan

        Args:
            failed_action: The action that failed
            step_num: Step number that failed
            error: Error message

        Returns:
            ExecutionResult indicating replanning was triggered
        """
        if not self.recovery_manager:
            return ExecutionResult(
                success=False,
                action=failed_action.tool_name,
                error=f"Replanning not available: {error}"
            )

        print(f"\n{'='*80}")
        print(f"🔄 REPLANNING TRIGGERED - Step {step_num + 1} failed")
        print(f"{'='*80}")

        try:
            # Step 0: Record the failure FIRST so summarize_progress can see it
            failure_result = ExecutionResult(
                success=False,
                action=failed_action.tool_name,
                error=error
            )
            self.recovery_manager.mark_step_failed(step_num, failure_result)
            print(f"  ✓ Failure recorded: Step {step_num + 1} - {failed_action.tool_name}")

            # Step 1 & 2: Summarize progress (now includes the failed step)
            completed, failed, remaining = self.recovery_manager.summarize_progress()
            print(f"\n📊 EXECUTION SUMMARY:")
            print(f"\n{completed}")
            print(f"\n{failed}")
            print(f"\n{remaining}")

            # Get latest UI state from cache
            latest_state = self.state_cache.get_latest_state()
            if latest_state:
                print(f"\n📸 Latest UI state captured (length: {len(latest_state)} chars)")
            else:
                print(f"\n⚠️  No UI state available in cache")

            # Step 3 & 4: Generate recovery plan (includes KB retrieval, reasoning, and latest state)
            # Get MCP tools info
            mcp_tools = self.mcp_client.list_tools_sync()
            tools_description = self.mcp_client.get_tools_description_sync(mcp_tools)
            valid_tool_names = self.mcp_client.get_valid_tool_names_sync(mcp_tools)

            # Pass the already-computed summaries and latest state to avoid redundant calculation
            recovery_plan = self.recovery_manager.generate_recovery_plan(
                mcp_tools_description=tools_description,
                valid_tool_names=valid_tool_names,
                completed_summary=completed,
                failed_summary=failed,
                remaining_goal=remaining,
                latest_state=latest_state
            )

            # Step 6: Merge plans
            merged_plan, new_filepath = self.recovery_manager.merge_plans(recovery_plan)

            print(f"\n{'='*80}")
            print(f"✅ REPLANNING COMPLETE - Continue with merged plan")
            print(f"  New plan file: {os.path.basename(new_filepath)}")
            print(f"{'='*80}\n")

            # Return a special result that signals replanning occurred
            # The LangGraph workflow will detect this and restart execution with the merged plan
            return ExecutionResult(
                success=False,
                action="REPLAN_TRIGGERED",
                error="Replanning triggered - restart execution with merged plan",
                evidence=f"New plan: {new_filepath}"
            )

        except Exception as e:
            print(f"\n✗ Replanning failed: {e}")
            return ExecutionResult(
                success=False,
                action=failed_action.tool_name,
                error=f"Replanning failed: {e}"
            )


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
