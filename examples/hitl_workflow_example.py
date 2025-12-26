"""
Example: Using the HITL-Enhanced Autonomous Workflow

This example demonstrates:
1. Basic HITL workflow execution
2. Skill reuse from library
3. Memory retrieval and learning
4. Interactive human feedback

Run with:
    python examples/hitl_workflow_example.py
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agent.workflows.autonomous_workflow import AutonomousWorkflow


def example_1_basic_hitl_workflow():
    """
    Example 1: Basic HITL workflow with human interaction

    This will:
    - Start human observer (Ctrl+I to interrupt)
    - Execute task with HITL support
    - Request approval for low-confidence actions
    - Request final verification
    - Create verified skill on success
    """
    print("\n" + "="*80)
    print("Example 1: Basic HITL Workflow")
    print("="*80)

    # Create workflow with HITL enabled (default)
    workflow = AutonomousWorkflow(
        app_name="asammdf 8.6.10",
        enable_hitl=True,  # HITL enabled
        session_id="example_session_001"
    )

    # Define task
    task = (
        "Concatenate all MF4 files in folder "
        r"C:\Users\ADMIN\Downloads\test_files. "
        "Save as concatenated_result.mf4 in the same folder."
    )

    print(f"\nTask: {task}")
    print("\nHITL Features Active:")
    print("  - Press Ctrl+I anytime to interrupt")
    print("  - Agent will request approval for uncertain actions")
    print("  - Final verification will be requested")
    print("  - Successful workflow will be saved as verified skill")

    # Run task
    results = workflow.run_sync(task)

    # Display results
    print("\n" + "="*80)
    print("Results:")
    print("="*80)
    print(f"Success: {results['success']}")
    print(f"Steps Completed: {results.get('steps_completed', 0)}")
    if results.get('error'):
        print(f"Error: {results['error']}")

    return results


def example_2_skill_reuse():
    """
    Example 2: Skill Reuse from Library

    If you run the same/similar task again:
    - Workflow checks SkillLibrary first
    - Finds verified skill (similarity >= 0.7)
    - Reuses skill's plan without LLM planning
    - Executes faster and more reliably
    """
    print("\n" + "="*80)
    print("Example 2: Skill Reuse")
    print("="*80)

    workflow = AutonomousWorkflow(
        enable_hitl=True,
        session_id="example_session_002"
    )

    # Similar task (should match verified skill from Example 1)
    task = (
        "Concatenate MF4 files in folder "
        r"C:\Users\ADMIN\Downloads\test_files_v2. "
        "Save as output.mf4."
    )

    print(f"\nTask: {task}")
    print("\nExpected:")
    print("  [HITL] Checking for verified skills...")
    print("  ✓ [HITL] Found verified skill (similarity: 0.85+)")
    print("  → Using verified skill's plan")

    results = workflow.run_sync(task)

    print(f"\nSkill Reused: {results.get('skill_reused', False)}")
    print(f"Success: {results['success']}")

    return results


def example_3_without_hitl():
    """
    Example 3: Fully Autonomous (No HITL)

    Run without human interaction:
    - No human observer
    - No approval requests
    - No final verification
    - No skill creation
    """
    print("\n" + "="*80)
    print("Example 3: Fully Autonomous (No HITL)")
    print("="*80)

    # Disable HITL
    workflow = AutonomousWorkflow(
        enable_hitl=False  # HITL disabled
    )

    task = (
        "Concatenate MF4 files in folder "
        r"C:\Users\ADMIN\Downloads\test_files. "
        "Save as result.mf4."
    )

    print(f"\nTask: {task}")
    print("\nRunning without HITL:")
    print("  - No human interaction")
    print("  - No approval requests")
    print("  - No skill creation")

    results = workflow.run_sync(task)

    print(f"\nSuccess: {results['success']}")

    return results


def example_4_inspect_learnings():
    """
    Example 4: Inspect Stored Learnings

    View what the agent has learned:
    - Human guidance
    - Human corrections
    - Agent self-recovery
    """
    print("\n" + "="*80)
    print("Example 4: Inspect Learnings")
    print("="*80)

    from agent.feedback.memory_manager import LearningMemoryManager

    # Create memory manager
    memory = LearningMemoryManager()

    # Retrieve learnings for a task
    task = "Concatenate MF4 files"

    print(f"\nRetrieving learnings for: '{task}'")

    learnings = memory.retrieve_all_learnings_for_task(
        task=task,
        session_id="example_session_001"
    )

    # Display learnings
    print("\nHuman Guidance:")
    for learning in learnings.get("human_proactive", [])[:3]:
        print(f"  - {learning.get('memory', 'N/A')}")

    print("\nHuman Corrections:")
    for learning in learnings.get("human_interrupt", [])[:3]:
        print(f"  - {learning.get('memory', 'N/A')}")

    print("\nAgent Self-Recovery:")
    for learning in learnings.get("agent_self_exploration", [])[:2]:
        print(f"  - {learning.get('memory', 'N/A')}")

    total = sum(len(v) for v in learnings.values())
    print(f"\nTotal learnings: {total}")


def example_5_inspect_skills():
    """
    Example 5: Inspect Verified Skills

    View verified skills in library:
    - Original tasks
    - Success rates
    - Usage counts
    """
    print("\n" + "="*80)
    print("Example 5: Inspect Verified Skills")
    print("="*80)

    from agent.learning.skill_library import SkillLibrary

    # Create skill library
    library = SkillLibrary()

    print("\nVerified Skills in Library:")
    print("-" * 80)

    # List all skills
    if library.skills:
        for skill_id, skill in library.skills.items():
            print(f"\nSkill ID: {skill_id}")
            print(f"  Task: {skill.original_task}")
            print(f"  Success Rate: {skill.success_rate:.1%}")
            print(f"  Usage Count: {skill.usage_count}")
            print(f"  Steps: {len(skill.plan.get('plan', []))}")
            print(f"  Human Verified: {skill.metadata.get('human_verified', False)}")
    else:
        print("  (No verified skills yet - run Example 1 first)")


def main():
    """Run all examples"""
    print("\n" + "="*80)
    print("HITL Workflow Examples")
    print("="*80)

    print("\nAvailable Examples:")
    print("  1. Basic HITL workflow with human interaction")
    print("  2. Skill reuse from library")
    print("  3. Fully autonomous (no HITL)")
    print("  4. Inspect stored learnings")
    print("  5. Inspect verified skills")
    print("  6. Run all examples")

    choice = input("\nSelect example (1-6): ").strip()

    if choice == "1":
        example_1_basic_hitl_workflow()
    elif choice == "2":
        example_2_skill_reuse()
    elif choice == "3":
        example_3_without_hitl()
    elif choice == "4":
        example_4_inspect_learnings()
    elif choice == "5":
        example_5_inspect_skills()
    elif choice == "6":
        # Run inspection examples only (no execution)
        example_4_inspect_learnings()
        example_5_inspect_skills()
    else:
        print("Invalid choice. Please run again and select 1-6.")


if __name__ == "__main__":
    # Quick test mode
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        print("\n[Test Mode] Running inspection examples only...")
        example_4_inspect_learnings()
        example_5_inspect_skills()
    else:
        main()
