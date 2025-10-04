"""
Autonomous Workflow Examples for asammdf Agent

REQUIREMENTS:
- Activate .agent-venv before running
- Agent dependencies must be installed in .agent-venv
- Windows-MCP must be installed in .windows-venv (will run as subprocess)
- ANTHROPIC_API_KEY must be set in .env file

USAGE:
    .agent-venv\Scripts\activate
    python examples\example_autonomous_workflow.py

This script demonstrates AUTONOMOUS workflows where:
- Claude AI takes control of the GUI via MCP tools
- Agent runs in .agent-venv
- Windows-MCP server runs as subprocess in .windows-venv
- No hardcoded actions - fully AI-driven
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def example_rag_autonomous_simple():
    """Example 2: RAG-Powered Autonomous Workflow (Simple Task)"""
    print("\n" + "="*80)
    print("Example 2: RAG-Powered Autonomous Workflow - Simple Task")
    print("="*80 + "\n")
    print("Environment: .agent-venv (Agent + RAG)")
    print("MCP Server: .windows-venv (subprocess)")
    print("Approach: RAG retrieval → Claude planning → MCP execution\n")

    from agent.workflows.autonomous_workflow import execute_autonomous_task

    # asammdf-specific task - uses skill catalog
    task = "Open an MF4 file called sample.mf4"

    print(f"Task: {task}\n")
    print("Workflow:")
    print("1. RAG retrieves relevant skills from knowledge base")
    print("2. Claude generates execution plan")
    print("3. Agent executes plan using MCP tools")
    print("4. Claude observes and adapts\n")

    results = execute_autonomous_task(task)

    print("\n" + "="*80)
    if results['success']:
        print("✓ Task completed successfully!")
        print(f"Steps completed: {results.get('steps_completed', 0)}")
        if results.get('plan'):
            print(f"\nPlan reasoning:")
            print(f"  {results['plan'].get('reasoning', 'N/A')}")
    else:
        print(f"✗ Task failed: {results.get('error')}")
    print("="*80)


def example_rag_autonomous_complex():
    """Example 3: RAG-Powered Autonomous Workflow (Complex Task)"""
    print("\n" + "="*80)
    print("Example 3: RAG-Powered Autonomous Workflow - Complex Task")
    print("="*80 + "\n")
    print("Environment: .agent-venv (Agent + RAG + LangGraph)")
    print("MCP Server: .windows-venv (subprocess)")
    print("Approach: Multi-step planning with retry logic\n")

    from agent.workflows.autonomous_workflow import execute_autonomous_task

    # Complex multi-step task
    task = "Concatenate all MF4 files in C:\\data folder and export to Excel"

    print(f"Task: {task}\n")
    print("Workflow:")
    print("1. RAG retrieves concatenation and export skills")
    print("2. Claude generates multi-step plan")
    print("3. LangGraph orchestrates execution with state management")
    print("4. Automatic retry on failures (up to 2 retries per step)")
    print("5. Verification after each step\n")

    results = execute_autonomous_task(task)

    print("\n" + "="*80)
    if results['success']:
        print("✓ Complex task completed successfully!")
        print(f"Steps completed: {results.get('steps_completed', 0)}")

        if results.get('plan'):
            plan = results['plan']
            print(f"\nPlan reasoning:")
            print(f"  {plan.get('reasoning', 'N/A')}")
            print(f"\nEstimated duration: {plan.get('estimated_duration', 'N/A')}s")

        if results.get('execution_log'):
            print(f"\nExecution log: {len(results['execution_log'])} steps")
    else:
        print(f"✗ Task failed: {results.get('error')}")
        print(f"Steps attempted: {results.get('steps_completed', 0)}")
    print("="*80)


if __name__ == '__main__':
    print("\n" + "="*80)
    print("asammdf Agent - Autonomous Workflow Examples")
    print("="*80)
    print("\nThese examples use AUTONOMOUS AI-driven workflows.")
    print("Claude takes control of the GUI and decides actions in real-time.")
    print("\nIMPORTANT:")
    print("  - Make sure you activated .agent-venv")
    print("  - Make sure ANTHROPIC_API_KEY is set in .env")
    print("  - Windows-MCP will run automatically as subprocess\n")
    print("For MANUAL hardcoded workflows, use:")
    print("  → examples/example_manual_workflow.py\n")

    examples = {
        '1': ('RAG + Autonomous (Open MF4 file)', example_rag_autonomous_simple),
        '2': ('RAG + Autonomous (Concatenate & Export)', example_rag_autonomous_complex)
                }

    # Choose example
    print("="*80)
    for key, (name, _) in examples.items():
        print(f"  {key}. {name}")
    print("="*80)

    choice = '1' #input(f"\nChoose example (1-{len(examples)}, default=1): ").strip() or '1'

    if choice in examples:
        name, func = examples[choice]
        print(f"\nRunning: {name}")
        func()
    else:
        print(f"Invalid choice. Available: {', '.join(examples.keys())}")
