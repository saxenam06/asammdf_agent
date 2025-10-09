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
        self.states: Dict[float, str] = {}  # state_num -> state_output (supports 8.1, 8.2 for local planning)
        self.current_state_num: float = 0.0
        self.local_substep: int = 0  # Track substeps within current high-level step

    def add_state(self, state_output: str, step_num: Optional[int] = None, is_local: bool = False) -> float:
        """Add a state output and return its state number

        Args:
            state_output: The state output to cache
            step_num: Optional step number from high-level plan
            is_local: If True, this is a local planning state (uses decimal notation)

        Returns:
            The state number used (e.g., 8 for high-level, 8.1 for local)
        """
        if step_num is not None and not is_local:
            # High-level plan step - cache with integer step number
            state_num = float(step_num + 1)
            self.states[state_num] = state_output
            self.current_state_num = state_num
            self.local_substep = 0  # Reset local substep counter
            return state_num
        elif is_local:
            # Local planning step - use decimal notation (e.g., 8.1, 8.2)
            self.local_substep += 1
            base_step = int(self.current_state_num)
            state_num = float(f"{base_step}.{self.local_substep}")
            self.states[state_num] = state_output
            return state_num
        else:
            # No step_num and not local - shouldn't happen, but return current
            return self.current_state_num

    def get_state(self, state_num: float) -> Optional[str]:
        """Get a cached state output by step number"""
        return self.states.get(state_num)

    def get_latest_state(self) -> Optional[str]:
        """Get the most recent state output"""
        if not self.states:
            return None
        latest_key = max(self.states.keys())
        return self.states[latest_key]


class AdaptiveExecutor:
    """
    Low-level executor that:
    - Resolves symbolic coordinate references (e.g., 'STATE_3:menu:Mode')
    - Interprets unclear instructions and makes execution decisions
    - Calls additional actions if needed to reach desired state
    - Uses GPT-4o-mini for lightweight reasoning
    """

    def __init__(self, mcp_client: MCPClient, api_key: Optional[str] = None, knowledge_retriever=None):
        """
        Initialize adaptive executor

        Args:
            mcp_client: MCP client for tool execution
            api_key: OpenAI API key (defaults to env var)
            knowledge_retriever: Optional KnowledgeRetriever instance for KB queries
        """
        self.mcp_client = mcp_client
        self.state_cache = StateCache()
        self.knowledge_retriever = knowledge_retriever

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

    def _parse_symbolic_reference(self, ref: str) -> Tuple[float, str, str]:
        """
        Parse symbolic reference like 'STATE_3:menu:Mode' or 'STATE_8.1:button:Add'

        Returns:
            (state_num, control_type, element_name)
        """
        match = re.match(r'STATE_([\d.]+):([^:]+):(.+)', ref)
        if match:
            state_num = float(match.group(1))
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
{state_output}  # Limit to avoid token overflow
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
                temperature=0,
                response_format={"type": "json_object"}
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

    def _query_knowledge_base(self, queries: List[dict]) -> str:
        """Query knowledge base and return formatted context"""
        if not self.knowledge_retriever or not queries:
            return ""

        kb_results = []
        for query_dict in queries:
            query = query_dict.get('query', '')
            print(f"  → Querying KB: '{query}'")
            try:
                results = self.knowledge_retriever.retrieve(query, top_k=2)
                for result in results:
                    kb_results.append(f"ID: {result.knowledge_id}\nDescription: {result.description}\nSteps: {result.steps}")
            except Exception as e:
                print(f"  ! KB query failed: {e}")
        return "\n\n".join(kb_results) if kb_results else ""

    def _check_goal_condition(self, goal_condition: str, current_state: str) -> bool:
        """Check if goal condition is met in current state"""
        if not goal_condition or not current_state:
            return False

        prompt = f"""Check if the goal condition is met in the current UI state.

Goal: {goal_condition}

Current UI State:
```
{current_state}
```

Respond ONLY with JSON:
{{"goal_met": true/false, "reasoning": "brief explanation"}}
"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=150,
                temperature=0,
                response_format={"type": "json_object"}
            )
            result = json.loads(response.choices[0].message.content.strip())
            goal_met = result.get('goal_met', False)
            print(f"  → Goal {'✓ MET' if goal_met else '✗ NOT MET'}: {result.get('reasoning', '')}")
            return goal_met
        except Exception as e:
            print(f"  ! Error checking goal: {e}")
            return False

    def _interpret_and_adapt(
        self,
        action: ActionSchema,
        context: List[ActionSchema],
        latest_state: Optional[str],
        kb_context: Optional[str] = None
    ) -> dict:
        """
        Use LLM to interpret unclear action and generate concrete steps

        Args:
            action: High-level action that needs interpretation
            context: Previous actions for context
            latest_state: Latest UI state output
            kb_context: Optional knowledge base context from previous queries

        Returns:
            Dict with keys: feasibility, kb_queries, goal_condition, concrete_actions, explanation
        """
        # Build context summary
        context_summary = "\n".join([
            f"{i+1}. {a.tool_name} - {a.reasoning}"
            for i, a in enumerate(context)  # Last 3 actions for context
        ])

        state_summary = latest_state if latest_state else "No state available"

        kb_section = ""
        if kb_context:
            kb_section = f"\n\nKnowledge Base Context:\n```\n{kb_context}\n```\n"

        prompt = f"""You are a low-level GUI automation executor interpreting high-level plans.

Recent actions executed:
{context_summary}

Current UI state:
```
{state_summary}
```{kb_section}

High-level action to interpret:
Tool: {action.tool_name}
Arguments: {json.dumps(action.tool_arguments, indent=2)}
Reasoning: {action.reasoning}

Your task:
1. Assess whether the high-level action is **directly reachable** from the current state:
   - Check if the target element (e.g., button, menu item) exists and is visible/interactable in the current state
   - If YES: set feasibility="reachable" and provide concrete actions to execute it directly
   - If NO: set feasibility="unreachable" and follow steps 2-4 below

2. If UNREACHABLE, determine what knowledge is needed:
   - Identify what information from the knowledge base would help achieve the desired intent
   - Specify exact queries to retrieve relevant knowledge (e.g., "how to add files in batch processing mode")
   - The knowledge base will be queried and results provided to help plan the next steps

3. Generate a **2-step local plan** to incrementally progress toward the goal:
   - Step 1: Take ONE action based on current state (click, type, etc.) to move closer to the goal
   - Step 2: ALWAYS use State-Tool to check the new state after the action
   - IMPORTANT: Only provide 2 actions maximum - one action + one state check
   - The local plan will be executed, then this function will be called again with the new state

4. Define the goal condition:
   - Specify the observable condition that proves the high-level intent is achieved
   - Example: "File selection dialog is open with title 'Add Files'"
   - This condition will be checked after each local plan execution

CRITICAL RULES:
- ALWAYS limit concrete_actions to exactly 2 steps: [action, State-Tool]
- If symbolic references exist, try to resolve them from the current state
- Prefer reliable interactions: menu navigation, explicit coordinates, keyboard shortcuts
- The local plan loops until goal_condition is met, then resumes the original high-level plan

Respond with JSON:
{{
  "feasibility": "reachable" | "unreachable",
  "kb_queries": [
    {{
      "query": "exact search query for knowledge base",
      "reasoning": "why this knowledge helps"
    }}
  ],
  "goal_condition": "observable condition that proves the high-level action's intent is achieved",
  "concrete_actions": [
    {{
      "tool_name": "Click-Tool",
      "tool_arguments": {{"loc": [x, y], "button": "left", "clicks": 1}},
      "reasoning": "what we're doing and why it moves us toward the goal"
    }},
    {{
      "tool_name": "State-Tool",
      "tool_arguments": {{"use_vision": false}},
      "reasoning": "verify the action's effect and check if goal_condition is met"
    }}
  ],
  "explanation": "why this 2-step plan progresses toward the goal"
}}
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=800,
                temperature=0.3,
                response_format={"type": "json_object"}
            )

            content = response.choices[0].message.content.strip()
            result = json.loads(content)

            print(f"\n  [Adaptive Interpretation]")
            print(f"  Feasibility: {result.get('feasibility')}")
            print(f"  Explanation: {result.get('explanation')}")
            if result.get('goal_condition'):
                print(f"  Goal: {result.get('goal_condition')}")

            # Convert concrete_actions to ActionSchema objects
            concrete_actions = []
            for action_dict in result.get('concrete_actions', []):
                concrete_actions.append(ActionSchema(
                    tool_name=action_dict['tool_name'],
                    tool_arguments=action_dict['tool_arguments'],
                    reasoning=action_dict.get('reasoning', '')
                ))

            return {
                'feasibility': result.get('feasibility', 'unknown'),
                'kb_queries': result.get('kb_queries', []),
                'goal_condition': result.get('goal_condition', ''),
                'concrete_actions': concrete_actions,
                'explanation': result.get('explanation', '')
            }

        except Exception as e:
            print(f"  ! Error in adaptive interpretation: {e}")
            # Fallback: return original action as reachable
            return {
                'feasibility': 'reachable',
                'kb_queries': [],
                'goal_condition': '',
                'concrete_actions': [action],
                'explanation': 'Fallback to original action'
            }

    def execute_action(
        self,
        action: ActionSchema,
        context: List[ActionSchema] = None,
        step_num: Optional[int] = None,
        is_local: bool = False
    ) -> ExecutionResult:
        """
        Execute a single action with adaptive resolution

        Args:
            action: High-level action to execute
            context: Previous actions for context
            step_num: Optional step number from the plan (used for state caching)
            is_local: If True, cache states with decimal notation (e.g., 8.1, 8.2)

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
                state_num = self.state_cache.add_state(result.evidence, step_num, is_local)
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

            # Try adaptive interpretation with iterative local planning
            return self._execute_with_local_planning(action, context, step_num)

        # Step 3: Execute the resolved action
        result = self.mcp_client.execute_action(resolved_action)

        return result

    def _execute_with_local_planning(
        self,
        high_level_action: ActionSchema,
        context: List[ActionSchema],
        step_num: Optional[int],
        max_local_iterations: int = 10
    ) -> ExecutionResult:
        """
        Execute a high-level action using iterative 2-step local planning

        Args:
            high_level_action: The original high-level action to achieve
            context: Previous actions for context
            step_num: Step number from high-level plan
            max_local_iterations: Maximum local planning iterations

        Returns:
            Execution result
        """
        print(f"\n  [Local Planning Mode] Achieving: {high_level_action.reasoning}")

        kb_context = None

        for iteration in range(max_local_iterations):
            print(f"\n  --- Local Iteration {iteration + 1}/{max_local_iterations} ---")

            # Get current state
            latest_state = self.state_cache.get_latest_state()

            # Interpret and adapt with KB context
            adaptation = self._interpret_and_adapt(
                high_level_action,
                context,
                latest_state,
                kb_context
            )

            feasibility = adaptation['feasibility']
            goal_condition = adaptation['goal_condition']
            kb_queries = adaptation['kb_queries']
            concrete_actions = adaptation['concrete_actions']

            # If unreachable and has KB queries, fetch knowledge
            if feasibility == 'unreachable' and kb_queries and not kb_context:
                kb_context = self._query_knowledge_base(kb_queries)
                if kb_context:
                    print(f"  ✓ Retrieved knowledge, re-planning with context")
                    continue

            # Execute the 2-step local plan (action + state check)
            print(f"  → Executing {len(concrete_actions)}-step local plan")

            for local_action in concrete_actions:
                # Execute local action with is_local=True to cache as 8.1, 8.2, etc.
                result = self.execute_action(local_action, context, step_num=step_num, is_local=True)

                if not result.success:
                    return ExecutionResult(
                        success=False,
                        action=high_level_action.tool_name,
                        error=f"Local plan failed: {result.error}"
                    )

            # Check if goal is met
            latest_state = self.state_cache.get_latest_state()
            if goal_condition and self._check_goal_condition(goal_condition, latest_state):
                print(f"  ✓ High-level goal achieved via local planning")
                return ExecutionResult(
                    success=True,
                    action=high_level_action.tool_name,
                    evidence=f"Achieved via {iteration + 1} local planning iterations"
                )

        # Max iterations reached
        return ExecutionResult(
            success=False,
            action=high_level_action.tool_name,
            error=f"Max local planning iterations ({max_local_iterations}) reached without achieving goal"
        )

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
