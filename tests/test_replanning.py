"""
Test script for the replanning workflow

This demonstrates the complete replanning system:
1. Track plan execution state (completed/failed steps)
2. Save plan snapshots with timestamps on failure
3. Summarize progress (what worked vs what failed)
4. Retrieve relevant knowledge from KB
5. Replan with reasoning
6. Merge completed + new plan
7. Continue execution
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from agent.execution.mcp_client import get_mcp_client
from agent.execution.adaptive_executor import AdaptiveExecutor
from agent.planning.workflow_planner import load_plan
from agent.knowledge_base.retriever import KnowledgeRetriever


def test_replanning_workflow():
    """Test the complete replanning workflow"""

    print("="*80)
    print("TESTING REPLANNING WORKFLOW")
    print("="*80)

    # Configuration
    plan_file = "Concatenate_all_MF4_files_in_C__Users_ADMIN_Downlo_bad75d6c.json"
    plan_path = os.path.join("agent", "planning", "plans", plan_file)

    if not os.path.exists(plan_path):
        print(f"✗ Plan file not found: {plan_path}")
        return

    print(f"\n✓ Using plan file: {plan_file}")

    # Load the plan
    plan = load_plan(
        "Concatenate all MF4 files in C:\\Users\\ADMIN\\Downloads\\ev-data-pack-v10\\ev-data-pack-v10\\electric_cars\\log_files\\Tesla Model 3\\LOG\\3F78A21D\\00000001 folder save the concatenated MF4 file with name Tesla_Model_3_3F78A21D.mf4 in the same folder path"
    )

    if not plan:
        print("✗ Could not load plan")
        return

    print(f"✓ Plan loaded: {len(plan.plan)} steps")

    # Initialize components
    print("\n" + "="*80)
    print("INITIALIZING COMPONENTS")
    print("="*80)

    try:
        # MCP Client
        mcp_client = get_mcp_client()
        print("✓ MCP Client initialized")

        # Knowledge Retriever
        knowledge_retriever = KnowledgeRetriever()
        print("✓ Knowledge Retriever initialized")

        # Adaptive Executor with plan tracking
        executor = AdaptiveExecutor(
            mcp_client=mcp_client,
            knowledge_retriever=knowledge_retriever,
            plan_filepath=plan_path
        )
        print("✓ Adaptive Executor initialized with plan tracking")

    except Exception as e:
        print(f"✗ Initialization failed: {e}")
        return

    # Execute the plan
    print("\n" + "="*80)
    print("EXECUTING PLAN")
    print("="*80)
    print("\nThe executor will:")
    print("  1. Track each step's completion/failure")
    print("  2. On failure: save snapshot, summarize, retrieve KB, replan, merge, continue")
    print("  3. Repeat up to 3 times if needed")
    print("\n" + "="*80)

    try:
        results = executor.execute_plan(
            plan_actions=plan.plan,
            app_name="asammdf 8.6.10",
            max_replan_attempts=3
        )

        print("\n" + "="*80)
        print("EXECUTION RESULTS")
        print("="*80)

        success_count = sum(1 for r in results if r.success)
        print(f"\nTotal steps executed: {len(results)}")
        print(f"Successful: {success_count}")
        print(f"Failed: {len(results) - success_count}")

        # Show recovery manager status if available
        if executor.recovery_manager:
            print("\n" + "="*80)
            print("FINAL PLAN STATE")
            print("="*80)

            summary = executor.recovery_manager.get_execution_summary()
            print(f"\nCompleted steps: {summary['completed_count']}")
            print(f"Failed steps: {summary['failed_count']}")
            print(f"Pending steps: {summary['pending_count']}")

            if summary['failed_steps']:
                print(f"\nFirst failure at step {summary['first_failed_step'] + 1}:")
                print(f"  Error: {summary['failed_steps'][0]['error']}")

    except Exception as e:
        print(f"\n✗ Execution error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_replanning_workflow()
