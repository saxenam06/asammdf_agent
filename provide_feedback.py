"""
Standalone script to provide feedback for a specific step in the current task

Usage:
    python provide_feedback.py

Interactive prompts will guide you through:
1. Select which step to provide feedback for
2. Describe the error observed
3. Optionally provide a suggestion

The system will automatically:
- Load the current plan
- Extract the action and KB source
- Create a FailureLearning entry
- Attach to the appropriate KB item
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent.feedback.human_observer import HumanObserver
from agent.planning.workflow_planner import get_latest_plan_filepath


def main():
    print("\n" + "="*80)
    print("  PROVIDE STEP FEEDBACK")
    print("="*80)
    print("This tool allows you to provide feedback for any step in the current plan.\n")

    # Get task from user
    task_input = input("Enter the task description (or press Enter to use latest plan): ").strip()

    if not task_input:
        # Try to find latest plan in plans directory
        plans_dir = "agent/planning/plans"
        if not os.path.exists(plans_dir):
            print(f"[Error] Plans directory not found: {plans_dir}")
            print("Please provide the task description manually.")
            return

        # List available plans
        plan_files = [f for f in os.listdir(plans_dir) if f.endswith('.json')]
        if not plan_files:
            print(f"[Error] No plan files found in {plans_dir}")
            print("Please run a task first, then provide feedback.")
            return

        # Show available plans
        print(f"\nFound {len(plan_files)} plan(s):")
        for idx, plan_file in enumerate(plan_files[-5:], 1):  # Show last 5
            print(f"  [{idx}] {plan_file}")

        # Let user select
        selection = input("\nSelect a plan number (or press Enter for most recent): ").strip()

        if selection:
            try:
                selected_idx = int(selection) - 1
                plan_filename = plan_files[selected_idx]
            except (ValueError, IndexError):
                print(f"[Error] Invalid selection")
                return
        else:
            # Use most recent
            plan_filename = sorted(plan_files)[-1]

        plan_filepath = os.path.join(plans_dir, plan_filename)

        # Load task from plan file
        import json
        try:
            with open(plan_filepath, 'r', encoding='utf-8') as f:
                plan_data = json.load(f)
                task = plan_data.get("task", "Unknown task")
        except Exception as e:
            print(f"[Error] Could not load plan: {e}")
            return

        print(f"\n✓ Using plan: {plan_filename}")
        print(f"✓ Task: {task[:80]}..." if len(task) > 80 else f"✓ Task: {task}")

    else:
        # User provided task - find latest plan for that task
        task = task_input
        plan_filepath = get_latest_plan_filepath(task)

        if not plan_filepath or not os.path.exists(plan_filepath):
            print(f"[Error] No plan found for task: {task}")
            print("Please run the task first, then provide feedback.")
            return

        print(f"\n✓ Found plan: {os.path.basename(plan_filepath)}")

    # Initialize observer
    observer = HumanObserver(session_id="feedback_session")

    # Call provide_step_feedback
    feedback_result = observer.provide_step_feedback(
        task=task,
        plan_filepath=plan_filepath
    )

    if feedback_result:
        print("\n" + "="*80)
        print("  FEEDBACK SUMMARY")
        print("="*80)
        print(f"Step: {feedback_result['step_num']}")
        print(f"KB Source: {feedback_result['kb_source']}")
        print(f"Error: {feedback_result['error']}")
        print("\n✓ Feedback has been recorded in the knowledge base.")
        print("  The agent will see this feedback when planning future tasks.")
        print("="*80 + "\n")
    else:
        print("\n[Info] No feedback provided\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[Cancelled] Feedback session interrupted\n")
    except Exception as e:
        print(f"\n[Error] {e}")
        import traceback
        traceback.print_exc()
