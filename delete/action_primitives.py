"""
Primitive GUI actions for dynamic execution
These are the building blocks that action_sequences are composed of
"""

import re
import asyncio
from typing import List, Optional, Dict, Any

from .mcp_client import get_mcp_client

# Global MCP client and event loop
_mcp = None
_event_loop = None
_server = 'windows-mcp'

def get_event_loop():
    """Get or create the global event loop"""
    global _event_loop
    if _event_loop is None or _event_loop.is_closed():
        _event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_event_loop)
    return _event_loop

def get_connected_client():
    """Get or create connected MCP client"""
    global _mcp
    if _mcp is None:
        _mcp = get_mcp_client()
        loop = get_event_loop()
        loop.run_until_complete(_mcp.connect(_server))
    return _mcp

# Helper functions that call Windows-MCP tools directly
def click_tool(loc: List[int], button: str = 'left', clicks: int = 1) -> str:
    """Call Click-Tool on Windows-MCP server"""
    client = get_connected_client()
    loop = get_event_loop()
    result = loop.run_until_complete(client.call_tool('Click-Tool', {'loc': loc, 'button': button, 'clicks': clicks}))
    return result.content[0].text if hasattr(result, 'content') and result.content else str(result)

def type_tool(loc: List[int], text: str, clear: bool = False, press_enter: bool = False) -> str:
    """Call Type-Tool on Windows-MCP server"""
    client = get_connected_client()
    loop = get_event_loop()
    result = loop.run_until_complete(client.call_tool('Type-Tool', {'loc': loc, 'text': text, 'clear': clear, 'press_enter': press_enter}))
    return result.content[0].text if hasattr(result, 'content') and result.content else str(result)

def drag_tool(from_loc: List[int], to_loc: List[int]) -> str:
    """Call Drag-Tool on Windows-MCP server"""
    client = get_connected_client()
    loop = get_event_loop()
    result = loop.run_until_complete(client.call_tool('Drag-Tool', {'from_loc': from_loc, 'to_loc': to_loc}))
    return result.content[0].text if hasattr(result, 'content') and result.content else str(result)

def shortcut_tool(keys: List[str]) -> str:
    """Call Shortcut-Tool on Windows-MCP server"""
    client = get_connected_client()
    loop = get_event_loop()
    result = loop.run_until_complete(client.call_tool('Shortcut-Tool', {'shortcut': keys}))
    return result.content[0].text if hasattr(result, 'content') and result.content else str(result)

def key_tool(key: str) -> str:
    """Call Key-Tool on Windows-MCP server"""
    client = get_connected_client()
    loop = get_event_loop()
    result = loop.run_until_complete(client.call_tool('Key-Tool', {'key': key}))
    return result.content[0].text if hasattr(result, 'content') and result.content else str(result)

def wait_tool(seconds: float) -> str:
    """Call Wait-Tool on Windows-MCP server"""
    client = get_connected_client()
    loop = get_event_loop()
    result = loop.run_until_complete(client.call_tool('Wait-Tool', {'duration': seconds}))
    return result.content[0].text if hasattr(result, 'content') and result.content else str(result)

def switch_tool(name: str) -> str:
    """Call Switch-Tool on Windows-MCP server"""
    client = get_connected_client()
    loop = get_event_loop()
    result = loop.run_until_complete(client.call_tool('Switch-Tool', {'name': name}))
    return result.content[0].text if hasattr(result, 'content') and result.content else str(result)

def state_tool(use_vision: bool = False):
    """Call State-Tool on Windows-MCP server"""
    client = get_connected_client()
    loop = get_event_loop()
    result = loop.run_until_complete(client.call_tool('State-Tool', {'use_vision': use_vision}))
    if hasattr(result, 'content') and result.content:
        return result.content[0].text
    return str(result)


class ActionPrimitives:
    """
    Library of primitive GUI actions
    All methods are stateless and reusable
    """

    def __init__(self, app_name: str = "asammdf 8.6.10"):
        self.app_name = app_name

    # ============================================================================
    # Primitive Actions
    # ============================================================================

    def click_by_text(
        self,
        element_name: str,
        control_type: Optional[str] = None,
        prefer_bottom: bool = False
    ) -> str:
        """
        Click an element by its text label

        Args:
            element_name: Text of the element
            control_type: Control type filter (Button, TabItem, etc.)
            prefer_bottom: Prefer bottom-most element if multiple matches

        Returns:
            Status message
        """
        switch_tool(self.app_name)
        wait_tool(1)

        state_output = state_tool(use_vision=False)
        state_text = state_output[0] if isinstance(state_output, list) else state_output

        coords = self._parse_element_from_state(
            state_text,
            element_name,
            control_type=control_type,
            prefer_bottom=prefer_bottom
        )

        if coords:
            click_tool(loc=coords)
            wait_tool(1)
            return f"Clicked '{element_name}'"
        else:
            raise Exception(f"Element '{element_name}' not found")

    def type_in_field(
        self,
        text: str,
        field_name: Optional[str] = None,
        clear: bool = True,
        press_enter: bool = False
    ) -> str:
        """
        Type text into a field

        Args:
            text: Text to type
            field_name: Name of field (if None, types at current focus)
            clear: Clear field before typing
            press_enter: Press Enter after typing

        Returns:
            Status message
        """
        switch_tool(self.app_name)
        wait_tool(1)

        if field_name:
            # Find field first
            state_output = state_tool(use_vision=False)
            state_text = state_output[0] if isinstance(state_output, list) else state_output

            coords = self._parse_element_from_state(
                state_text,
                field_name,
                control_type="Edit"
            )

            if coords:
                type_tool(loc=coords, text=text, clear=clear, press_enter=press_enter)
            else:
                # Fallback: type directly
                if clear:
                    shortcut_tool(["ctrl", "a"])
                for char in text:
                    key_tool(char)
                if press_enter:
                    key_tool("enter")
        else:
            # Type at current focus
            if clear:
                shortcut_tool(["ctrl", "a"])
            for char in text:
                key_tool(char)
            if press_enter:
                key_tool("enter")

        wait_tool(1)
        return f"Typed '{text}'"

    def select_tab(self, tab_name: str) -> str:
        """
        Select a tab by name

        Args:
            tab_name: Name of tab

        Returns:
            Status message
        """
        return self.click_by_text(tab_name, control_type="TabItem")

    def select_mode(self, mode_name: str) -> str:
        """
        Select a mode/option (radio button or dropdown)

        Args:
            mode_name: Name of mode

        Returns:
            Status message
        """
        # Try radio button first
        try:
            return self.click_by_text(mode_name, control_type="RadioButton")
        except:
            # Try as regular button
            return self.click_by_text(mode_name, control_type="Button")

    def press_shortcut(self, keys: List[str]) -> str:
        """
        Press keyboard shortcut

        Args:
            keys: List of keys (e.g., ["ctrl", "o"])

        Returns:
            Status message
        """
        switch_tool(self.app_name)
        shortcut_tool(keys)
        wait_tool(2)
        return f"Pressed {'+'.join(keys)}"

    def press_key(self, key: str) -> str:
        """
        Press single key

        Args:
            key: Key name

        Returns:
            Status message
        """
        switch_tool(self.app_name)
        key_tool(key)
        wait_tool(1)
        return f"Pressed {key}"

    def wait(self, seconds: float) -> str:
        """
        Wait for specified duration

        Args:
            seconds: Wait duration

        Returns:
            Status message
        """
        wait_tool(seconds)
        return f"Waited {seconds}s"

    def open_file_dialog(self, file_path: str) -> str:
        """
        Open file dialog and select file

        Args:
            file_path: Path to file

        Returns:
            Status message
        """
        # Press Ctrl+O
        self.press_shortcut(["ctrl", "o"])

        # Type file path
        self.type_in_field(file_path, field_name="File name", clear=True, press_enter=False)

        # Click Open button
        self.click_by_text("Open", control_type="Button", prefer_bottom=True)

        return f"Opened '{file_path}'"

    def type_in_dialog(self, text: str, field_name: str = "File name") -> str:
        """
        Type in a dialog field (e.g., file picker)

        Args:
            text: Text to type
            field_name: Field name

        Returns:
            Status message
        """
        switch_tool(self.app_name)
        wait_tool(1)

        state_output = state_tool(use_vision=False)
        state_text = state_output[0] if isinstance(state_output, list) else state_output

        coords = self._parse_element_from_state(
            state_text,
            field_name,
            control_type="Edit"
        )

        if coords:
            type_tool(loc=coords, text=text, clear=True, press_enter=False)
        else:
            # Fallback: type directly
            shortcut_tool(["ctrl", "a"])
            for char in text:
                key_tool(char)

        wait_tool(1)
        return f"Typed '{text}' in '{field_name}'"

    def click_button(self, button_name: str, prefer_bottom: bool = False) -> str:
        """
        Click a button by name

        Args:
            button_name: Button text
            prefer_bottom: Prefer bottom-most if multiple

        Returns:
            Status message
        """
        return self.click_by_text(button_name, control_type="Button", prefer_bottom=prefer_bottom)

    def drag_element(self, from_text: str, to_x_offset: int, to_y_offset: int = 0) -> str:
        """
        Drag an element to a relative position

        Args:
            from_text: Source element text
            to_x_offset: X offset from source
            to_y_offset: Y offset from source

        Returns:
            Status message
        """
        switch_tool(self.app_name)
        wait_tool(1)

        state_output = state_tool(use_vision=False)
        state_text = state_output[0] if isinstance(state_output, list) else state_output

        coords = self._parse_element_from_state(state_text, from_text, control_type="Tree Item")

        if not coords:
            raise Exception(f"Element '{from_text}' not found")

        target_x = coords[0] + to_x_offset
        target_y = coords[1] + to_y_offset

        drag_tool(from_loc=coords, to_loc=[target_x, target_y])
        wait_tool(2)

        return f"Dragged '{from_text}' to ({target_x}, {target_y})"

    # ============================================================================
    # Helper methods
    # ============================================================================

    def _parse_element_from_state(
        self,
        state_text: str,
        element_name: str,
        control_type: Optional[str] = None,
        prefer_bottom: bool = False
    ) -> Optional[List[int]]:
        """
        Parse state tool output to find element coordinates
        """
        lines = state_text.split('\n')
        in_interactive_section = False
        matches = []

        for line in lines:
            if "List of Interactive Elements:" in line:
                in_interactive_section = True
                continue

            if in_interactive_section:
                if "List of Informative Elements:" in line or "List of Scrollable Elements:" in line:
                    break

                if re.search(r'\bName:\s*' + re.escape(element_name) + r'\b', line, re.IGNORECASE):
                    if control_type:
                        if f"ControlType: {control_type}" not in line:
                            continue

                    match = re.search(r'Coordinates:\s*\((\d+),\s*(\d+)\)', line)
                    if match:
                        x = int(match.group(1))
                        y = int(match.group(2))

                        if prefer_bottom:
                            matches.append([x, y])
                        else:
                            return [x, y]

        if matches:
            return max(matches, key=lambda coord: coord[1])

        return None


# Singleton instance for easy import
primitives = ActionPrimitives()
