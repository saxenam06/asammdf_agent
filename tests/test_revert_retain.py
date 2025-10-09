"""
Test script for revert/retain decision mechanism in local planning
"""

import sys
import os

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

sys.path.insert(0, os.path.dirname(__file__))

from agent.planning.schemas import ActionSchema, ExecutionResult
from agent.execution.adaptive_executor import LocalActionHistory, LocalActionNode
from agent.execution.action_reverter import ActionReverter


def test_local_action_history():
    """Test LocalActionHistory tracking"""
    print("\n" + "="*80)
    print("Test 1: LocalActionHistory")
    print("="*80)

    history = LocalActionHistory()

    # Simulate adding actions
    action1 = ActionSchema(
        tool_name='Click-Tool',
        tool_arguments={'loc': [100, 200], 'button': 'left', 'clicks': 1},
        reasoning='Click File menu'
    )

    result1 = ExecutionResult(success=True, action='Click-Tool', evidence='Clicked')

    node1 = history.push(
        action=action1,
        state_before="State A",
        state_after="State B",
        result=result1,
        distance_before=2.0,
        distance_after=4.0
    )

    print(f"✓ Added action 1")
    print(f"  Progress: {node1.progress_made:+.1f}")
    print(f"  Depth: {history.get_depth()}")

    # Add another action with no progress
    action2 = ActionSchema(
        tool_name='Click-Tool',
        tool_arguments={'loc': [150, 250], 'button': 'left', 'clicks': 1},
        reasoning='Click wrong button'
    )

    result2 = ExecutionResult(success=True, action='Click-Tool', evidence='Clicked')

    node2 = history.push(
        action=action2,
        state_before="State B",
        state_after="State C",
        result=result2,
        distance_before=4.0,
        distance_after=3.5  # Regression
    )

    print(f"✓ Added action 2")
    print(f"  Progress: {node2.progress_made:+.1f}")
    print(f"  Depth: {history.get_depth()}")

    # Test loop detection
    print(f"\n  Loop detection: {history.is_stuck_in_loop()}")

    # Test regression detection
    print(f"  Consistent regression: {history.has_consistent_regression()}")

    # Pop action
    popped = history.pop()
    print(f"\n✓ Popped action: {popped.action.reasoning}")
    print(f"  Depth after pop: {history.get_depth()}")


def test_action_reverter():
    """Test ActionReverter strategies"""
    print("\n" + "="*80)
    print("Test 2: ActionReverter")
    print("="*80)

    # Mock MCP client (won't actually execute)
    class MockMCPClient:
        def execute_action(self, action):
            return ExecutionResult(success=True, action=action.tool_name, evidence="Mocked")

    reverter = ActionReverter(MockMCPClient(), llm_client=None)

    # Test 1: Checkbox click
    checkbox_action = ActionSchema(
        tool_name='Click-Tool',
        tool_arguments={'loc': [100, 200], 'button': 'left', 'clicks': 1},
        reasoning='Click checkbox to enable feature'
    )

    print("\n  Test: Checkbox revert")
    can_revert = reverter.can_revert(checkbox_action)
    print(f"    Can revert: {can_revert}")

    if can_revert:
        revert_action = reverter.generate_revert_action(
            checkbox_action,
            state_after="Checkbox is now checked",
            state_before="Checkbox was unchecked"
        )
        if revert_action:
            print(f"    ✓ Revert strategy: {revert_action.reasoning}")
            print(f"      Tool: {revert_action.tool_name}")
            print(f"      Args: {revert_action.tool_arguments}")

    # Test 2: State-Tool (should not be revertible)
    state_action = ActionSchema(
        tool_name='State-Tool',
        tool_arguments={'use_vision': False},
        reasoning='Check current state'
    )

    print("\n  Test: State-Tool revert")
    can_revert = reverter.can_revert(state_action)
    print(f"    Can revert: {can_revert}")

    # Test 3: Type action
    type_action = ActionSchema(
        tool_name='Type-Tool',
        tool_arguments={'text': 'test.txt'},
        reasoning='Type filename'
    )

    print("\n  Test: Type revert")
    can_revert = reverter.can_revert(type_action)
    print(f"    Can revert: {can_revert}")

    if can_revert:
        revert_action = reverter.generate_revert_action(
            type_action,
            state_after="Text field contains 'test.txt'",
            state_before="Text field was empty"
        )
        if revert_action:
            print(f"    ✓ Revert strategy: {revert_action.reasoning}")
            print(f"      Tool: {revert_action.tool_name}")
            print(f"      Args: {revert_action.tool_arguments}")


def test_progress_evaluation():
    """Test progress-based decision logic"""
    print("\n" + "="*80)
    print("Test 3: Progress Evaluation & Decision Logic")
    print("="*80)

    history = LocalActionHistory()

    # Scenario 1: Good progress
    print("\n  Scenario 1: Good progress (+2.0)")
    action = ActionSchema(
        tool_name='Click-Tool',
        tool_arguments={'loc': [100, 200], 'button': 'left', 'clicks': 1},
        reasoning='Click File menu'
    )
    result = ExecutionResult(success=True, action='Click-Tool')
    node = history.push(action, "State A", "State B", result, 3.0, 5.0)

    print(f"    Distance before: {node.distance_to_goal_before}")
    print(f"    Distance after: {node.distance_to_goal_after}")
    print(f"    Progress: {node.progress_made:+.1f}")
    print(f"    Expected decision: RETAIN")

    # Scenario 2: No progress, but has unexplored options
    print("\n  Scenario 2: No progress (0.0), unexplored options available")
    action2 = ActionSchema(
        tool_name='Click-Tool',
        tool_arguments={'loc': [150, 250], 'button': 'left', 'clicks': 1},
        reasoning='Try different button'
    )
    result2 = ExecutionResult(success=True, action='Click-Tool')
    node2 = history.push(action2, "State B", "State C", result2, 5.0, 5.0)
    node2.exploration_options = [
        {"name": "try_option_A", "description": "Try option A"},
        {"name": "try_option_B", "description": "Try option B"}
    ]

    print(f"    Distance before: {node2.distance_to_goal_before}")
    print(f"    Distance after: {node2.distance_to_goal_after}")
    print(f"    Progress: {node2.progress_made:+.1f}")
    print(f"    Unexplored options: {len(node2.exploration_options)}")
    print(f"    Expected decision: EXPLORE")

    # Scenario 3: Regression, no options
    print("\n  Scenario 3: Regression (-1.0), no unexplored options")
    action3 = ActionSchema(
        tool_name='Click-Tool',
        tool_arguments={'loc': [200, 300], 'button': 'left', 'clicks': 1},
        reasoning='Wrong click'
    )
    result3 = ExecutionResult(success=True, action='Click-Tool')
    node3 = history.push(action3, "State C", "State D", result3, 5.0, 4.0)
    node3.exploration_options = []
    node3.explored_count = 0

    print(f"    Distance before: {node3.distance_to_goal_before}")
    print(f"    Distance after: {node3.distance_to_goal_after}")
    print(f"    Progress: {node3.progress_made:+.1f}")
    print(f"    Unexplored options: {len(node3.exploration_options)}")
    print(f"    Has unexplored: {node3.has_unexplored_options}")
    print(f"    Expected decision: REVERT")


def test_loop_detection():
    """Test loop detection"""
    print("\n" + "="*80)
    print("Test 4: Loop Detection")
    print("="*80)

    history = LocalActionHistory()

    # Add actions that create a loop (same state repeated)
    same_state = "State X (repeated)"

    for i in range(4):
        action = ActionSchema(
            tool_name='Click-Tool',
            tool_arguments={'loc': [100 + i*10, 200], 'button': 'left', 'clicks': 1},
            reasoning=f'Action {i+1}'
        )
        result = ExecutionResult(success=True, action='Click-Tool')
        # All actions lead to the same state
        history.push(action, same_state, same_state, result, 5.0, 5.0)

        print(f"  Action {i+1}: Depth={history.get_depth()}, Loop detected={history.is_stuck_in_loop()}")

    print(f"\n  ✓ Loop detection working: {history.is_stuck_in_loop()}")


if __name__ == "__main__":
    print("\n" + "="*80)
    print("REVERT/RETAIN DECISION MECHANISM - UNIT TESTS")
    print("="*80)

    try:
        test_local_action_history()
        test_action_reverter()
        test_progress_evaluation()
        test_loop_detection()

        print("\n" + "="*80)
        print("✓ ALL TESTS COMPLETED")
        print("="*80)

    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
