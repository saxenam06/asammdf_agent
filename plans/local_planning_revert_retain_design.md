# Local Planning: Revert/Retain Decision Mechanism

## Overview
Enhance local planning in `adaptive_executor.py` to intelligently decide whether to revert or retain actions based on progress toward the high-level goal.

## Core Requirements

### 1. Progress Evaluation
- **Goal Distance Metric**: Measure how close we are to achieving the high-level intent
  - Use LLM to evaluate: "How close is current state to goal?" (scale 0-10)
  - Compare before/after each local action
  - Progress = increased distance score

### 2. Revert vs Retain Decision
Decision logic:
```
IF goal_condition_met:
    RETURN success (done with local planning)
ELIF progress_made (distance increased):
    RETAIN action, continue exploring from new state
ELIF no_progress AND unexplored_options_exist:
    RETAIN action, try different next step
ELIF no_progress AND all_options_explored:
    REVERT action, backtrack to previous state
ELIF stuck_for_N_iterations:
    CANCEL local plan, escalate to replanning
```

### 3. Action Reversal Strategies
Smart reversion based on action type:

| Action Type | Reversal Strategy |
|-------------|------------------|
| Click checkbox | Click same location again (toggle off) |
| Click button that opens dialog | Find and click "Cancel" or "Close" button |
| Type text in field | Clear field (Ctrl+A, Delete) |
| Select menu item | Click elsewhere or ESC key |
| Open window/dialog | Click close button (X) or Alt+F4 |
| Generic click | No standard revert - use state analysis |

### 4. Exploration Strategy
Before reverting a step, explore all meaningful options:
- After clicking a button that opens dialog, try:
  1. Fill form and click OK
  2. Try different form values
  3. Only then click Cancel to revert

Implementation:
- Track "exploration branches" per action
- LLM suggests next exploration option
- Mark action as "fully explored" only when all options tried

### 5. Plan Cancellation
Conditions to cancel local planning:
- Max iterations reached (already implemented)
- Stuck in loop (same state repeated 3+ times)
- LLM determines goal is unreachable from current path
- Safety limit: if distance_to_goal decreased consistently for 3 iterations

## Implementation Architecture

### New Classes

```python
class LocalActionHistory:
    """Stack of local actions with revert capability"""
    actions: List[LocalActionNode]

    def push(action, state_before, state_after, result)
    def pop() -> LocalActionNode
    def peek_last() -> LocalActionNode
    def get_exploration_depth() -> int
```

```python
class LocalActionNode:
    """Single local action with exploration tracking"""
    action: ActionSchema
    state_before: str
    state_after: str
    result: ExecutionResult
    distance_to_goal_before: float  # 0-10 scale
    distance_to_goal_after: float   # 0-10 scale
    exploration_branches: List[str]  # ["try_ok_button", "try_cancel", ...]
    explored_count: int
    reverted: bool
```

```python
class ActionReverter:
    """Knows how to revert different action types"""

    def can_revert(action: ActionSchema) -> bool
    def generate_revert_action(action: ActionSchema, current_state: str) -> ActionSchema
    def suggest_exploration_options(action: ActionSchema, state: str) -> List[str]
```

### Modified Functions

**`_execute_with_local_planning`**: Main loop with revert/retain logic
```python
def _execute_with_local_planning(...):
    history = LocalActionHistory()
    reverter = ActionReverter(self.client)

    for iteration in range(max_iterations):
        # Get current state
        latest_state = get_latest_state()

        # Generate next action (2-step plan)
        adaptation = self._interpret_and_adapt(...)

        # Execute action + state check
        state_before = latest_state
        result = execute_action(action)
        state_after = get_latest_state()

        # Evaluate progress
        dist_before = self._evaluate_distance_to_goal(state_before, goal)
        dist_after = self._evaluate_distance_to_goal(state_after, goal)

        # Record in history
        history.push(action, state_before, state_after, result,
                    dist_before, dist_after)

        # Check goal
        if goal_met:
            return success

        # Decide: revert or retain?
        decision = self._decide_revert_or_retain(
            history, dist_before, dist_after, goal
        )

        if decision == "retain":
            continue  # Next iteration from new state
        elif decision == "revert":
            # Generate revert action
            last_node = history.pop()
            revert_action = reverter.generate_revert_action(
                last_node.action, state_after
            )
            execute_action(revert_action)
            # Continue from reverted state
        elif decision == "cancel":
            return failure("Local planning cancelled")
```

**New: `_evaluate_distance_to_goal`**
```python
def _evaluate_distance_to_goal(self, current_state: str, goal: str) -> float:
    """
    Use LLM to evaluate how close current state is to goal
    Returns: 0.0 (far) to 10.0 (very close)
    """
    prompt = f"""
    Goal: {goal}
    Current State: {current_state}

    On a scale of 0-10, how close is the current state to achieving the goal?
    0 = completely unrelated, 10 = goal fully achieved

    Respond with JSON:
    {{"distance_score": <0-10>, "reasoning": "why this score"}}
    """
    # Call LLM, parse response
    return score
```

**New: `_decide_revert_or_retain`**
```python
def _decide_revert_or_retain(
    self,
    history: LocalActionHistory,
    dist_before: float,
    dist_after: float,
    goal: str
) -> str:
    """
    Decide whether to revert last action or retain it
    Returns: "retain", "revert", or "cancel"
    """
    progress = dist_after - dist_before
    last_node = history.peek_last()

    # Check for stuck condition
    if self._is_stuck(history):
        return "cancel"

    # Progress made - keep exploring
    if progress > 0.5:
        return "retain"

    # No progress - check if more exploration possible
    if progress <= 0:
        has_unexplored = self._has_unexplored_options(last_node)
        if has_unexplored:
            return "retain"  # Try different branch
        else:
            return "revert"  # Dead end, backtrack

    return "retain"  # Default: keep moving forward
```

## Integration Points

1. **adaptive_executor.py:519** - `_execute_with_local_planning` method
2. **adaptive_executor.py:282** - Add new methods after `_check_goal_condition`
3. **New file**: `agent/execution/action_reverter.py` - Reversal strategies

## Testing Strategy

1. Test checkbox toggle: Click → Revert by clicking again
2. Test dialog reversion: Open dialog → Click Cancel
3. Test progress evaluation: Measure distance at each step
4. Test exploration: Try multiple options before reverting
5. Test cancellation: Detect stuck loops and cancel

## Success Criteria

- ✓ Local planning can backtrack when hitting dead ends
- ✓ Progress is measured quantitatively (0-10 scale)
- ✓ Different action types have appropriate revert strategies
- ✓ Exploration exhausts options before backtracking
- ✓ Infinite loops are detected and cancelled
