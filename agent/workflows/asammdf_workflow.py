"""
Intelligent asammdf GUI Workflow Orchestrator
Uses dynamic UI element discovery instead of hardcoded coordinates
"""

import sys
import os
from typing import Optional, Dict, Any, List

# Add Windows-MCP to path
tools_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'tools', 'Windows-MCP')
sys.path.insert(0, tools_path)

from main import (
    launch_tool,
    click_tool,
    type_tool,
    drag_tool,
    shortcut_tool,
    key_tool,
    wait_tool,
    switch_tool,
    state_tool,
)

# Unwrap MCP tool functions to make them directly callable
launch_tool = launch_tool.fn
click_tool = click_tool.fn
type_tool = type_tool.fn
drag_tool = drag_tool.fn
shortcut_tool = shortcut_tool.fn
key_tool = key_tool.fn
wait_tool = wait_tool.fn
switch_tool = switch_tool.fn
state_tool = state_tool.fn


class AsammdfWorkflow:
    """
    Intelligent workflow orchestrator for asammdf GUI automation
    Dynamically discovers UI elements without hardcoded coordinates
    """

    def __init__(self, fuzzy_threshold: int = 70):
        """
        Initialize workflow

        Args:
            fuzzy_threshold: Fuzzy matching threshold for element names (0-100)
        """
        self.fuzzy_threshold = fuzzy_threshold
        self.app_name = "asammdf 8.6.10"

    def plot_signal(self,
                   mf4_file: str = "sample_compressed.mf4",
                   signal_name: str = "Value") -> Dict[str, Any]:
        """
        Execute complete workflow: Launch asammdf → Open file → Plot signal

        Args:
            mf4_file: Name of MF4 file (in Downloads folder)
            signal_name: Name of signal to plot

        Returns:
            Dictionary with execution results and status
        """
        results = {
            'steps': [],
            'success': False,
            'error': None,
            'mf4_file': mf4_file,
            'signal_name': signal_name
        }

        print("\n" + "="*80)
        print(f"asammdf Workflow: Plot '{signal_name}' from '{mf4_file}'")
        print("="*80 + "\n")

        try:
            # Step 1: Launch asammdf
            # step_result = self._execute_step(
            #     "Launch asammdf",
            #     self._launch_asammdf
            # )
            # results['steps'].append(step_result)
            # if not step_result['success']:
            #     raise Exception(f"Failed to launch asammdf: {step_result.get('error')}")

            # Step 2: Open MF4 file
            step_result = self._execute_step(
                "Open MF4 file",
                self._open_mf4_file,
                mf4_file
            )
            results['steps'].append(step_result)
            if not step_result['success']:
                raise Exception(f"Failed to open file: {step_result.get('error')}")

            # Step 4: Find and drag signal
            step_result = self._execute_step(
                f"Drag signal '{signal_name}'",
                self._drag_signal_to_plot,
                signal_name
            )
            results['steps'].append(step_result)
            if not step_result['success']:
                raise Exception(f"Failed to drag signal: {step_result.get('error')}")

            # Step 5: Create plot
            step_result = self._execute_step(
                "Create plot",
                self._create_plot
            )
            results['steps'].append(step_result)
            if not step_result['success']:
                raise Exception(f"Failed to create plot: {step_result.get('error')}")

            results['success'] = True
            print("\n" + "="*80)
            print("✓ Workflow completed successfully!")
            print("="*80 + "\n")

        except Exception as e:
            results['error'] = str(e)
            print(f"\n✗ Workflow failed: {e}\n")

        return results

    def _execute_step(self, step_name: str, step_func, *args) -> Dict[str, Any]:
        """
        Execute a workflow step with error handling

        Args:
            step_name: Human-readable step name
            step_func: Function to execute
            *args: Arguments to pass to function

        Returns:
            Dictionary with step results
        """
        print(f"[Step] {step_name}...")

        try:
            result = step_func(*args)
            print(f"  ✓ {step_name} completed\n")
            return {
                'name': step_name,
                'success': True,
                'result': result
            }
        except Exception as e:
            print(f"  ✗ {step_name} failed: {e}\n")
            return {
                'name': step_name,
                'success': False,
                'error': str(e)
            }

    def _launch_asammdf(self) -> str:
        """Launch asammdf application"""
        result = launch_tool("asammdf")
        print(f"  → {result}")

        # Wait for app to fully load
        wait_tool(4)
        print("  → Waiting for GUI to load...")

        return "asammdf launched"

    def _open_mf4_file(self, filename: str) -> str:
        """
        Open MF4 file using Ctrl+O shortcut

        Args:
            filename: Name of file to open (in Downloads folder)

        Returns:
            Status message
        """
        # Activate asammdf window
        switch_result = switch_tool(self.app_name)
        print(f"  → {switch_result}")
        wait_tool(1)

        # Press Ctrl+O to open file dialog
        shortcut_result = shortcut_tool(["ctrl", "o"])
        print(f"  → {shortcut_result}")

        # Wait for file dialog
        wait_tool(2)
        print("  → File dialog opened")

        # Use state_tool to get interactive elements
        state_output = state_tool(use_vision=False)
        state_text = state_output[0] if isinstance(state_output, list) else state_output
        print("  → Retrieved interactive elements from state tool")

        # Parse interactive elements to find "File name" Edit control
        file_input_coords = self._parse_element_from_state(
            state_text,
            "File name",
            control_type="Edit"
        )

        if file_input_coords:
            print(f"  → Found file input at: {file_input_coords}")
            # Type filename
            type_tool(
                loc=file_input_coords,
                text=filename,
                clear=True,
                press_enter=False
            )
            print(f"  → Typed filename: {filename}")
        else:
            # Fallback: just type filename (dialog should have focus)
            print(f"  → File name field not found, typing filename directly: {filename}")
            key_tool("home")  # Go to start of field
            shortcut_tool(["ctrl", "a"])  # Select all
            for char in filename:
                key_tool(char)

        wait_tool(1)

        # Get state again to find Open button
        state_output = state_tool(use_vision=False)
        state_text = state_output[0] if isinstance(state_output, list) else state_output

        # Parse interactive elements to find "Open" Button (prefer bottom-most one)
        open_button_coords = self._parse_element_from_state(
            state_text,
            "Open",
            control_type="Button",
            prefer_bottom=True
        )

        if open_button_coords:
            print(f"  → Found Open button at: {open_button_coords}")
            click_tool(loc=open_button_coords)
        else:
            print("  → Open button not found, pressing Enter to open file")
            key_tool("enter")

        # Wait for file to load
        wait_tool(2)
        print(f"  → File '{filename}' loaded")

        return f"Opened {filename}"

    def _parse_element_from_state(self, state_text: str, element_name: str, control_type: str = None, prefer_bottom: bool = False) -> Optional[List[int]]:
        """
        Parse state tool output to find element coordinates

        Args:
            state_text: Output from state_tool
            element_name: Name of element to find
            control_type: Optional control type filter (e.g., "Button", "Edit")
            prefer_bottom: If True and multiple matches found, return the one with highest y-coordinate

        Returns:
            [x, y] coordinates if found, None otherwise
        """
        import re

        # Look for interactive elements section
        lines = state_text.split('\n')
        in_interactive_section = False
        matches = []  # Store all matches if prefer_bottom is True

        for line in lines:
            if "List of Interactive Elements:" in line:
                in_interactive_section = True
                continue

            if in_interactive_section:
                # Stop at next section
                if "List of Informative Elements:" in line or "List of Scrollable Elements:" in line:
                    break

                # Parse line format: "Name: <name>, ControlType: <type>, Location: (x, y)"
                # Use word boundary matching to avoid partial matches (e.g., "OK" matching "Outlook")
                if re.search(r'\bName:\s*' + re.escape(element_name) + r'\b', line, re.IGNORECASE):
                    # Check control type if specified
                    if control_type:
                        if f"ControlType: {control_type}" not in line:
                            continue

                    # Extract coordinates using regex
                    match = re.search(r'Coordinates:\s*\((\d+),\s*(\d+)\)', line)
                    if match:
                        x = int(match.group(1))
                        y = int(match.group(2))

                        if prefer_bottom:
                            matches.append([x, y])
                        else:
                            return [x, y]  # Return first match if not prefer_bottom

        # If prefer_bottom, return the match with highest y-coordinate
        if matches:
            return max(matches, key=lambda coord: coord[1])

        return None

    def _select_natural_sort(self) -> str:
        """
        Click Natural Sort option in Channels tab

        Returns:
            Status message
        """
        # Activate asammdf window
        switch_result = switch_tool(self.app_name)
        print(f"  → {switch_result}")
        wait_tool(1)

        # Use state_tool to find Natural Sort button
        state_output = state_tool(use_vision=False)
        state_text = state_output[0] if isinstance(state_output, list) else state_output
        print("  → Retrieved interactive elements from state tool")

        # Find Natural Sort button/radio button
        natural_sort_coords = self._parse_element_from_state(
            state_text,
            "Natural Sort",
            control_type="RadioButton"
        )

        if natural_sort_coords:
            print(f"  → Found Natural Sort at: {natural_sort_coords}")
            click_tool(loc=natural_sort_coords)
            print("  → Clicked Natural Sort")
        else:
            raise Exception("Could not find Natural Sort button")

        # Wait for signals to load
        wait_tool(2)

        return "Selected Natural Sort view"

    def _drag_signal_to_plot(self, signal_name: str) -> str:
        """
        Find signal in Natural Sort list and drag to right panel

        Args:
            signal_name: Name of signal to find and drag

        Returns:
            Status message
        """
        # Activate asammdf window
        switch_result = switch_tool(self.app_name)
        print(f"  → {switch_result}")
        wait_tool(1)

        # Use state_tool to get interactive elements
        state_output = state_tool(use_vision=False)
        state_text = state_output[0] if isinstance(state_output, list) else state_output
        print("  → Retrieved interactive elements from state tool")

        # Parse interactive elements to find the signal in the list
        signal_coords = self._parse_element_from_state(
            state_text,
            signal_name,
            control_type="Tree Item"
        )

        if not signal_coords:
            raise Exception(f"Could not find signal '{signal_name}' in channels list")

        print(f"  → Found signal at: {signal_coords}")

        # Determine drag target (right panel area)
        # Strategy: Find a reasonable drop zone to the right of signal
        # Typically the plot area is in the right half of the window
        target_x = signal_coords[0] + 450  # Move 600px to the right
        target_y = signal_coords[1]  # Same vertical level

        print(f"  → Dragging from ({signal_coords[0]}, {signal_coords[1]}) to ({target_x}, {target_y})")

        # Perform drag operation
        drag_tool(
            from_loc=signal_coords,
            to_loc=[target_x, target_y]
        )

        print(f"  → Dragged '{signal_name}' to plot area")

        # Wait for plot creation dialog
        wait_tool(2)

        return f"Dragged signal '{signal_name}'"

    def _create_plot(self) -> str:
        """
        Click Plot button and OK to create the plot

        Returns:
            Status message
        """

        # Activate asammdf window
        switch_result = switch_tool(self.app_name)
        print(f"  → {switch_result}")
        wait_tool(1)

        # # Use state_tool to get interactive elements
        # state_output = state_tool(use_vision=False)
        # state_text = state_output[0] if isinstance(state_output, list) else state_output
        # print("  → Retrieved interactive elements from state tool")

        # # Parse interactive elements to find "Plot" Button
        # plot_button_coords = self._parse_element_from_state(
        #     state_text,
        #     "Plot",
        #     control_type="Button"
        # )

        # if plot_button_coords:
        #     print(f"  → Found Plot button at: {plot_button_coords}")
        #     click_tool(loc=plot_button_coords)
        #     print("  → Clicked Plot button")
        # else:
        #     raise Exception("Could not find Plot button")

        # Wait for next dialog/action
        # wait_tool(1)

        # Get state again to find OK button
        state_output = state_tool(use_vision=False)
        state_text = state_output[0] if isinstance(state_output, list) else state_output

        # Parse interactive elements to find "OK" Button (prefer bottom-most one)
        ok_button_coords = self._parse_element_from_state(
            state_text,
            "OK",
            control_type="Button",
            prefer_bottom=True
        )

        if ok_button_coords:
            print(f"  → Found OK button at: {ok_button_coords}")
            click_tool(loc=ok_button_coords)
            print("  → Clicked OK button")
        else:
            # Try pressing Enter as fallback
            print("  → OK button not found, pressing Enter")
            key_tool("enter")

        # Wait for plot to render
        wait_tool(2)

        return "Plot created successfully"

    def discover_ui(self, app_filter: Optional[str] = None):
        """
        Debug helper: Discover and print all UI elements

        Args:
            app_filter: Optional filter by application name
        """
        print("\n[UI Discovery Mode]")
        print(f"Discovering UI elements for: {app_filter or self.app_name}\n")

        # Use state_tool to get all UI elements
        state_output = state_tool(use_vision=False)
        state_text = state_output[0] if isinstance(state_output, list) else state_output

        print(state_text)


# Convenience function for direct execution
def plot_signal_from_mf4(mf4_file: str = "sample_compressed.mf4",
                        signal_name: str = "Value",
                        fuzzy_threshold: int = 70) -> Dict[str, Any]:
    """
    Convenience function to plot a signal from MF4 file

    Args:
        mf4_file: Name of MF4 file in Downloads folder
        signal_name: Name of signal to plot
        fuzzy_threshold: Fuzzy matching threshold (0-100)

    Returns:
        Workflow execution results
    """
    workflow = AsammdfWorkflow(fuzzy_threshold=fuzzy_threshold)
    return workflow.plot_signal(mf4_file=mf4_file, signal_name=signal_name)
