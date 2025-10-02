"""
Example usage of asammdf Agent

This script demonstrates different ways to use the agent programmatically
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from agent.workflows.asammdf_workflow import AsammdfWorkflow, plot_signal_from_mf4


def example_1_basic_usage():
    """Example 1: Basic usage with convenience function"""
    print("\n" + "="*80)
    print("Example 1: Basic Usage")
    print("="*80 + "\n")

    results = plot_signal_from_mf4(
        mf4_file="Discrete_deflate.mf4",
        signal_name="ASAM.M.SCALAR.SBYTE.IDENTICAL.DISCRETE"
    )

    if results['success']:
        print("✓ Workflow completed successfully!")
    else:
        print(f"✗ Workflow failed: {results['error']}")

if __name__ == '__main__':
    import sys

    examples = {
        '1': ('Basic Usage', example_1_basic_usage),
    }

    name, func = examples['1']
    print(f"\nRunning Example : {name}")
    func()

