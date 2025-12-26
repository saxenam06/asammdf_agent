"""
Test refactored autonomous workflow
"""

import sys
import os

# Add parent to path
sys.path.insert(0, os.path.dirname(__file__))

from agent.planning.schemas import ActionSchema
from agent.execution.mcp_client import MCPClient

def test_simple_execution():
    """Test simple MCP tool execution via new executor"""

    print("\n" + "="*80)
    print("Test 1: Simple MCP Tool Execution")
    print("="*80 + "\n")

    # Create test actions using new schema format
    actions = [
        ActionSchema(
            skill_id="switch_to_asammdf",
            tool_name="Switch-Tool",
            tool_arguments={"name": "asammdf 8.6.10"},
            doc_citation="Switch to asammdf window",
            expected_state="asammdf_focused"
        ),
        ActionSchema(
            skill_id="wait",
            tool_name="Wait-Tool",
            tool_arguments={"duration": 1},
            doc_citation="Wait for stability",
            expected_state="ready"
        ),
        ActionSchema(
            skill_id="get_state",
            tool_name="State-Tool",
            tool_arguments={"use_vision": False},
            doc_citation="Get current state",
            expected_state="state_retrieved"
        )
    ]

    executor = MCPClient()

    try:
        results = executor.execute_actions(actions)

        print("\n" + "="*80)
        print("Results:")
        print("="*80)

        all_success = all(r.success for r in results)

        for i, result in enumerate(results, 1):
            status = "OK" if result.success else "FAILED"
            print(f"{i}. [{status}] {result.action}")
            if result.error:
                print(f"   Error: {result.error}")

        if all_success:
            print("\nAll actions completed successfully!")
            return True
        else:
            print("\nSome actions failed!")
            return False

    except Exception as e:
        print(f"\nTest failed with exception: {e}")
        return False
    finally:
        try:
            executor.cleanup()
        except:
            pass  # Ignore cleanup errors for now


if __name__ == "__main__":
    success = test_simple_execution()
    sys.exit(0 if success else 1)
