"""
Example usage of asammdf Agent

This script demonstrates different ways to use the agent programmatically
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from agent.workflows.asammdf_workflow import AsammdfWorkflow, plot_signal_from_mf4
from agent.core.reporter import WorkflowVerifier


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


def example_2_with_verification():
    """Example 2: Workflow with verification"""
    print("\n" + "="*80)
    print("Example 2: With Verification")
    print("="*80 + "\n")

    # Run workflow
    results = plot_signal_from_mf4(
        mf4_file="sample_compressed.mf4",
        signal_name="ASAM.M.SCALAR.SBYTE.IDENTICAL.DISCRETE"
    )

    # Verify results
    verifier = WorkflowVerifier()
    report = verifier.get_verification_report(results)
    verifier.print_verification_report(report)


def example_3_custom_workflow():
    """Example 3: Custom workflow with step-by-step control"""
    print("\n" + "="*80)
    print("Example 3: Custom Workflow")
    print("="*80 + "\n")

    workflow = AsammdfWorkflow(fuzzy_threshold=75)

    # Run workflow
    results = workflow.plot_signal(
        mf4_file="sample_compressed.mf4",
        signal_name="Value"
    )

    # Print detailed results
    print("\nDetailed Results:")
    for step in results['steps']:
        print(f"  {step['name']}: {step['success']}")


def example_4_ui_discovery():
    """Example 4: UI Discovery for debugging"""
    print("\n" + "="*80)
    print("Example 4: UI Discovery")
    print("="*80 + "\n")

    workflow = AsammdfWorkflow()
    workflow.discover_ui(app_filter="asammdf")


def example_5_ui_discovery():
    """Example 5: UI Discovery using state_tool"""
    print("\n" + "="*80)
    print("Example 5: UI Discovery")
    print("="*80 + "\n")

    workflow = AsammdfWorkflow()

    # Discover all UI elements
    workflow.discover_ui(app_filter="asammdf")

    print("\nUI discovery completed. Check the output above for available elements.")


def example_6_multiple_signals():
    """Example 6: Plotting multiple signals (conceptual)"""
    print("\n" + "="*80)
    print("Example 6: Multiple Signals (Conceptual)")
    print("="*80 + "\n")

    workflow = AsammdfWorkflow()

    signals_to_plot = ["Value", "Speed", "Temperature"]

    for signal in signals_to_plot:
        print(f"\n--- Plotting {signal} ---")
        results = workflow.plot_signal(
            mf4_file="sample_compressed.mf4",
            signal_name=signal
        )

        if not results['success']:
            print(f"Failed to plot {signal}: {results['error']}")
            break


if __name__ == '__main__':
    import sys

    examples = {
        '1': ('Basic Usage', example_1_basic_usage),
        '2': ('With Verification', example_2_with_verification),
        '3': ('Custom Workflow', example_3_custom_workflow),
        '4': ('UI Discovery', example_4_ui_discovery),
        '5': ('UI Discovery', example_5_ui_discovery),
        '6': ('Multiple Signals', example_6_multiple_signals),
    }

    name, func = examples['1']
    print(f"\nRunning Example : {name}")
    func()

