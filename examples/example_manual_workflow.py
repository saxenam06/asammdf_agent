"""
Manual Workflow Examples for asammdf Agent

REQUIREMENTS:
- Activate .windows-venv before running
- Windows-MCP tools must be installed in .windows-venv

USAGE:
    .windows-venv\Scripts\activate
    python examples\example_manual_workflow.py

This script demonstrates MANUAL (hardcoded) workflows that directly
import and use Windows-MCP tools. No agent environment needed.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agent.workflows.manual_workflow import plot_signal_from_mf4


def example_plot_signal():
    """Example: Plot signal from MF4 file"""
    print("\n" + "="*80)
    print("Manual Workflow Example: Plot Signal from MF4")
    print("="*80 + "\n")
    print("Environment: .windows-venv (Windows-MCP tools)")
    print("Approach: Hardcoded action sequence\n")

    results = plot_signal_from_mf4(
        mf4_file="Discrete_deflate.mf4",
        signal_name="ASAM.M.SCALAR.SBYTE.IDENTICAL.DISCRETE"
    )

    if results['success']:
        print("\n✓ Manual workflow completed successfully!")
        print(f"  File: {results.get('mf4_file')}")
        print(f"  Signal: {results.get('signal_name')}")
    else:
        print(f"\n✗ Manual workflow failed: {results['error']}")




if __name__ == '__main__':
    print("\n" + "="*80)
    print("asammdf Agent - Manual Workflow Examples")
    print("="*80)
    print("\nThese examples use HARDCODED workflows.")
    print("They directly call Windows-MCP tools without AI planning.")
    print("\nFor AUTONOMOUS AI-driven workflows, use:")
    print("  → examples/example_autonomous_workflow.py\n")

    examples = {
        '1': ('Plot Signal from MF4', example_plot_signal),
    }

    # Choose example
    choice = '1' # input(f"Choose example (1-{len(examples)}, default=1): ").strip() or '1'

    if choice in examples:
        name, func = examples[choice]
        print(f"\nRunning: {name}")
        func()
    else:
        print(f"Invalid choice. Available: {', '.join(examples.keys())}")

