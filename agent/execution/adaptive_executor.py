"""
Adaptive low-level executor that interprets high-level plans and resolves symbolic references
Uses a lightweight LLM (GPT-4o-mini) to understand intent and make execution decisions
"""

import json
import re
from typing import Dict, Any, List, Optional, Tuple
from openai import OpenAI
import os
from dotenv import load_dotenv

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from agent.planning.schemas import ActionSchema, ExecutionResult
from agent.execution.mcp_client import MCPClient

load_dotenv()


class StateCache:
    """Cache for State-Tool outputs to resolve symbolic references"""

    def __init__(self):
        self.states: Dict[int, str] = {}  # state_num -> state_output
        self.current_state_num = 0

    def add_state(self, state_output: str) -> int:
        """Add a state output and return its state number"""
        self.current_state_num += 1
        self.states[self.current_state_num] = state_output
        return self.current_state_num

    def get_state(self, state_num: int) -> Optional[str]:
        """Get a cached state output"""
        return self.states.get(state_num)

    def get_latest_state(self) -> Optional[Tuple[int, str]]:
        """Get the most recent state"""
        if self.current_state_num > 0:
            return self.current_state_num, self.states[self.current_state_num]
        return None


class AdaptiveExecutor:
    """
    Low-level executor that:
    - Resolves symbolic coordinate references (e.g., 'STATE_3:menu:Mode')
    - Interprets unclear instructions and makes execution decisions
    - Calls additional actions if needed to reach desired state
    - Uses GPT-4o-mini for lightweight reasoning
    """

    def __init__(self, mcp_client: MCPClient, api_key: Optional[str] = None):
        """
        Initialize adaptive executor

        Args:
            mcp_client: MCP client for tool execution
            api_key: OpenAI API key (defaults to env var)
        """
        self.mcp_client = mcp_client
        self.state_cache = StateCache()

        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY required")

        self.client = OpenAI(api_key=self.api_key, timeout=60.0)
        self.model = "gpt-4o-mini"  # Lightweight, fast model

    def _is_symbolic_reference(self, value: Any) -> bool:
        """Check if a value is a symbolic reference like ['STATE_3:menu:Mode']"""
        if isinstance(value, list) and len(value) == 1:
            if isinstance(value[0], str) and value[0].startswith('STATE_'):
                return True
        return False

    def _parse_symbolic_reference(self, ref: str) -> Tuple[int, str, str]:
        """
        Parse symbolic reference like 'STATE_3:menu:Mode'

        Returns:
            (state_num, control_type, element_name)
        """
        match = re.match(r'STATE_(\d+):([^:]+):(.+)', ref)
        if match:
            state_num = int(match.group(1))
            control_type = match.group(2)
            element_name = match.group(3)
            return state_num, control_type, element_name
        raise ValueError(f"Invalid symbolic reference: {ref}")

    def _resolve_coordinates(self, symbolic_ref: str) -> Optional[List[int]]:
        """
        Resolve symbolic reference to actual coordinates using cached state

        Args:
            symbolic_ref: Reference like 'STATE_3:menu:Mode'

        Returns:
            [x, y] coordinates or None if not found
        """
        state_num, control_type, element_name = self._parse_symbolic_reference(symbolic_ref)

        state_output = self.state_cache.get_state(state_num)
        if not state_output:
            print(f"  ! Warning: State {state_num} not found in cache")
            return None

        # Use LLM to extract coordinates from state output
        prompt = f"""You are parsing UI state output to find element coordinates.

State output:
```
{state_output[:3000]}  # Limit to avoid token overflow
```

Find the element with:
- Control type: {control_type}
- Name/text: {element_name}

Extract the coordinates [x, y] for this element.

Respond with ONLY a JSON object:
{{"found": true, "coordinates": [x, y]}}

OR if not found:
{{"found": false, "reason": "why element was not found"}}
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0
            )

            result = json.loads(response.choices[0].message.content.strip())

            if result.get("found"):
                coords = result.get("coordinates")
                print(f"  ✓ Resolved '{symbolic_ref}' to {coords}")
                return coords
            else:
                print(f"  ! Could not resolve '{symbolic_ref}': {result.get('reason')}")
                return None

        except Exception as e:
            print(f"  ! Error resolving coordinates: {e}")
            return None

    def _resolve_action_arguments(self, action: ActionSchema) -> Dict[str, Any]:
        """
        Resolve symbolic references in action arguments to actual values

        Args:
            action: Action with potentially symbolic arguments

        Returns:
            Resolved arguments dictionary
        """
        resolved_args = {}

        for key, value in action.tool_arguments.items():
            if self._is_symbolic_reference(value):
                # Resolve symbolic reference
                symbolic_ref = value[0]
                coords = self._resolve_coordinates(symbolic_ref)
                if coords:
                    resolved_args[key] = coords
                else:
                    # Fallback: try to find in latest state
                    print(f"  ! Attempting fallback resolution for {key}")
                    resolved_args[key] = self._fallback_resolve(symbolic_ref)
            else:
                # Use value as-is
                resolved_args[key] = value

        return resolved_args

    def _fallback_resolve(self, symbolic_ref: str) -> List[int]:
        """
        Fallback: use latest state to resolve coordinates

        Returns:
            Best guess coordinates or raises exception
        """
        latest = self.state_cache.get_latest_state()
        if not latest:
            raise ValueError(f"Cannot resolve '{symbolic_ref}': no state available")

        state_num, state_output = latest
        print(f"  → Using STATE_{state_num} for fallback resolution")

        # Try to resolve from latest state
        _, control_type, element_name = self._parse_symbolic_reference(symbolic_ref)

        # Use simpler pattern matching as fallback
        lines = state_output.split('\n')
        for line in lines:
            if element_name.lower() in line.lower():
                # Try to extract coordinates from line
                coord_match = re.search(r'\((\d+),\s*(\d+)\)', line)
                if coord_match:
                    x, y = int(coord_match.group(1)), int(coord_match.group(2))
                    print(f"  → Fallback found coordinates: [{x}, {y}]")
                    return [x, y]

        raise ValueError(f"Cannot resolve '{symbolic_ref}' even with fallback")

    def _needs_clarification(self, action: ActionSchema, context: List[ActionSchema]) -> bool:
        """
        Check if action needs clarification before execution

        Args:
            action: Current action to execute
            context: Previous actions for context

        Returns:
            True if action needs LLM interpretation
        """
        # Check if there are unresolved symbolic references
        for value in action.tool_arguments.values():
            if self._is_symbolic_reference(value):
                return True

        # Check if reasoning suggests uncertainty
        if action.reasoning and any(word in action.reasoning.lower()
                                   for word in ['may', 'might', 'possibly', 'unclear']):
            return True

        return False

    def _interpret_and_adapt(
        self,
        action: ActionSchema,
        context: List[ActionSchema],
        current_state: Optional[str]
    ) -> List[ActionSchema]:
        """
        Use LLM to interpret unclear action and generate concrete steps

        Args:
            action: High-level action that needs interpretation
            context: Previous actions for context
            current_state: Latest UI state output

        Returns:
            List of concrete actions to execute
        """
        # Build context summary
        context_summary = "\n".join([
            f"{i+1}. {a.tool_name} - {a.reasoning}"
            for i, a in enumerate(context[-3:])  # Last 3 actions for context
        ])

        state_summary = current_state[:1000] if current_state else "No state available"

        prompt = f"""You are a low-level GUI automation executor interpreting high-level plans.

Recent actions executed:
{context_summary}

Current UI state:
```
{state_summary}
```

High-level action to interpret:
Tool: {action.tool_name}
Arguments: {json.dumps(action.tool_arguments, indent=2)}
Reasoning: {action.reasoning}

Your task:
1. If the action has symbolic references (like 'STATE_X:type:name'), explain how to resolve them
2. If the action is unclear, break it down into concrete steps
3. If additional State-Tool calls are needed, include them

Respond with JSON:
{{
  "needs_state_refresh": true/false,
  "concrete_actions": [
    {{
      "tool_name": "State-Tool",
      "tool_arguments": {{"use_vision": false}},
      "reasoning": "why we need this"
    }},
    {{
      "tool_name": "Click-Tool",
      "tool_arguments": {{"loc": [x, y], "button": "left", "clicks": 1}},
      "reasoning": "what we're clicking"
    }}
  ],
  "explanation": "why these actions achieve the goal"
}}
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=800,
                temperature=0.3
            )

            result = json.loads(response.choices[0].message.content.strip())

            print(f"\n  [Adaptive Interpretation]")
            print(f"  Explanation: {result.get('explanation')}")

            # Convert to ActionSchema objects
            concrete_actions = []
            for action_dict in result.get('concrete_actions', []):
                concrete_actions.append(ActionSchema(
                    tool_name=action_dict['tool_name'],
                    tool_arguments=action_dict['tool_arguments'],
                    reasoning=action_dict.get('reasoning', '')
                ))

            return concrete_actions

        except Exception as e:
            print(f"  ! Error in adaptive interpretation: {e}")
            # Fallback: return original action
            return [action]

    def execute_action(
        self,
        action: ActionSchema,
        context: List[ActionSchema] = None
    ) -> ExecutionResult:
        """
        Execute a single action with adaptive resolution

        Args:
            action: High-level action to execute
            context: Previous actions for context

        Returns:
            Execution result
        """
        context = context or []

        print(f"\n[Adaptive Executor] {action.tool_name}")
        print(f"  Arguments: {action.tool_arguments}")
        print(f"  Reasoning: {action.reasoning}")

        # Step 1: Check if this is a State-Tool call
        if action.tool_name == 'State-Tool':
            result = self.mcp_client.execute_action(action)

            # Cache the state output
            if result.success and result.evidence:
                state_num = self.state_cache.add_state(result.evidence)
                print(f"  ✓ Cached as STATE_{state_num}")

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

            # Try adaptive interpretation
            latest = self.state_cache.get_latest_state()
            current_state = latest[1] if latest else None

            adapted_actions = self._interpret_and_adapt(action, context, current_state)

            if len(adapted_actions) > 1:
                print(f"  → Adapted to {len(adapted_actions)} concrete actions")

                # Execute adapted actions sequentially
                for i, adapted_action in enumerate(adapted_actions):
                    result = self.execute_action(adapted_action, context + [action])
                    if not result.success:
                        return result

                # Return success if all adapted actions succeeded
                return ExecutionResult(
                    success=True,
                    action=action.tool_name,
                    evidence=f"Completed via {len(adapted_actions)} adapted actions"
                )
            else:
                resolved_action = adapted_actions[0]

        # Step 3: Execute the resolved action
        result = self.mcp_client.execute_action(resolved_action)

        return result

    def execute_plan(
        self,
        plan_actions: List[ActionSchema],
        app_name: str = "asammdf 8.6.10"
    ) -> List[ExecutionResult]:
        """
        Execute a high-level plan with adaptive resolution

        Args:
            plan_actions: List of high-level actions
            app_name: Application window name

        Returns:
            List of execution results
        """
        results = []

        print("\n" + "="*80)
        print(f"Adaptive Executor: Executing plan with {len(plan_actions)} steps")
        print("="*80)

        # Ensure app is focused
        print("\n[Pre-execution] Focusing application window...")
        self.mcp_client.call_tool('Switch-Tool', {'name': app_name})

        for i, action in enumerate(plan_actions, 1):
            print(f"\n{'='*80}")
            print(f"Step {i}/{len(plan_actions)}")
            print(f"{'='*80}")

            # Execute with context
            result = self.execute_action(action, context=plan_actions[:i-1])
            results.append(result)

            if not result.success:
                print(f"\n✗ Execution failed at step {i}")
                break

            print(f"  ✓ Step {i} completed")

        success_count = sum(1 for r in results if r.success)
        print(f"\n{'='*80}")
        print(f"Execution complete: {success_count}/{len(results)} steps succeeded")
        print(f"{'='*80}")

        return results


if __name__ == "__main__":
    """Test adaptive executor"""
    from agent.execution.mcp_client import get_mcp_client

    # Create test action with symbolic reference
    test_action = ActionSchema(
        tool_name='Click-Tool',
        tool_arguments={
            'loc': ['STATE_3:menu:Mode'],
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
    executor = AdaptiveExecutor(client)

    # Manually add mock state
    executor.state_cache.add_state(mock_state)
    executor.state_cache.add_state(mock_state)  # STATE_2
    executor.state_cache.add_state(mock_state)  # STATE_3

    # Test resolution
    result = executor.execute_action(test_action)
    print(f"\nResult: {result}")
