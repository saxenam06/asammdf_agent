"""
Test that manual_workflow still works after refactoring to use MCPExecutor
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from agent.workflows.manual_workflow import execute_tool

def test_manual_workflow_executor():
    """Test that execute_tool still works with MCPExecutor"""

    print("\n" + "="*80)
    print("Test: Manual Workflow with MCPExecutor")
    print("="*80 + "\n")

    try:
        # Test 1: Simple tool execution
        print("[Test 1] Wait-Tool...")
        result = execute_tool('Wait-Tool', duration=0.5)
        print(f"  Result: {result}")

        # Test 2: State-Tool
        print("\n[Test 2] State-Tool...")
        result = execute_tool('State-Tool', use_vision=False)
        # Extract text from result
        if hasattr(result, 'content') and result.content:
            output = result.content[0].text[:200]
        else:
            output = str(result)[:200]
        print(f"  Result (truncated): {output}...")

        print("\n" + "="*80)
        print("SUCCESS: Manual workflow execute_tool works with MCPExecutor!")
        print("="*80)
        return True

    except Exception as e:
        print("\n" + "="*80)
        print(f"FAILED: {e}")
        print("="*80)
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_manual_workflow_executor()
    sys.exit(0 if success else 1)
