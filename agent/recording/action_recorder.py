"""
Action Recorder

Captures human GUI interactions (mouse clicks, keyboard input) and converts them
to structured actions with UI element identification.
"""

import time
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from pynput import mouse, keyboard
import json


class ActionRecorder:
    """
    Records human interactions on a target application

    Captures:
    - Mouse clicks with coordinate-to-element mapping
    - Keyboard input (individual keys and shortcuts)
    - UI state before each interaction
    """

    def __init__(self, target_app: str = "asammdf"):
        """
        Initialize recorder

        Args:
            target_app: Name of the target application to monitor
        """
        self.target_app = target_app
        self.recorded_actions: List[Dict[str, Any]] = []
        self.recording = False
        self.recording_started = False  # Track if recording has actually begun

        # Keyboard state tracking for shortcuts
        self.pressed_keys = set()

        # Listeners (initialized in start_recording)
        self.mouse_listener: Optional[mouse.Listener] = None
        self.keyboard_listener: Optional[keyboard.Listener] = None

    def start_recording(self) -> None:
        """Start recording user actions (will begin on first click)"""
        print(f"[Recorder] Ready to record on {self.target_app}")
        self.recording = True
        self.recording_started = False
        self.recorded_actions = []

        # Start event listeners (just record raw events, no MCP calls)
        self.mouse_listener = mouse.Listener(on_click=self._on_click)
        self.keyboard_listener = keyboard.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release
        )

        self.mouse_listener.start()
        self.keyboard_listener.start()

        print(f"[Recorder] Waiting for first click on {self.target_app} to begin recording...")
        print(f"[Recorder] Press ESC to stop recording when done")

    def stop_recording(self) -> List[Dict[str, Any]]:
        """
        Stop recording and return captured actions (raw events only, no UI enrichment)

        Returns:
            List of recorded actions with raw coordinates
        """
        self.recording = False

        # Stop listeners
        if self.mouse_listener:
            self.mouse_listener.stop()
        if self.keyboard_listener:
            self.keyboard_listener.stop()

        print(f"\n[Recorder] Recording stopped")
        print(f"[Recorder] Captured {len(self.recorded_actions)} raw actions")

        return self.recorded_actions

    async def enrich_with_ui_state(self, mcp_client, actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Enrich recorded actions with UI state information (called after recording)

        This method simulates the actions by clicking at the recorded coordinates
        and capturing the UI state before each click to identify which element was clicked.

        Args:
            mcp_client: Connected MCP client (from async with context)
            actions: Raw recorded actions

        Returns:
            Actions enriched with UI state and element identification
        """
        from agent.planning.schemas import ActionSchema

        print(f"[Enrichment] Switching to {self.target_app}...")

        # Switch to target app
        switch_action = ActionSchema(
            tool_name="Switch-Tool",
            tool_arguments={"name": self.target_app},
            reasoning="Switch to target app"
        )
        await mcp_client.execute_action(switch_action)
        await asyncio.sleep(0.5)

        # Capture initial state
        print(f"[Enrichment] Capturing initial UI state...")
        state_action = ActionSchema(
            tool_name="State-Tool",
            tool_arguments={"use_vision": False},
            reasoning="Capture initial state"
        )
        state_result = await mcp_client.execute_action(state_action)
        last_state = state_result.evidence if state_result.success else None

        enriched_actions = []

        for i, action in enumerate(actions, 1):
            if action["type"] == "click":
                x, y = action["raw_coords"]

                print(f"[Enrichment] Processing click {i}/{len(actions)} at ({x}, {y})...")

                # Find element at coordinates in current state
                clicked_element = self._find_element_at_coords(x, y, last_state)

                # Enrich action with UI context
                enriched_action = {
                    **action,
                    "element": clicked_element,
                    "state_before": last_state
                }

                enriched_actions.append(enriched_action)

                if clicked_element.get("type") != "unknown":
                    print(f"  → Identified: {clicked_element['type']} '{clicked_element.get('text', 'N/A')}'")

                # Actually perform the click to advance UI state
                click_action = ActionSchema(
                    tool_name="Click-Tool",
                    tool_arguments={"coords": [x, y]},
                    reasoning="Replay recorded click for enrichment"
                )
                await mcp_client.execute_action(click_action)
                await asyncio.sleep(0.3)  # Wait for UI to settle

                # Capture new state after click
                state_result = await mcp_client.execute_action(state_action)
                if state_result.success:
                    last_state = state_result.evidence

            elif action["type"] == "key":
                # Handle single key press
                print(f"[Enrichment] Processing key: {action['key']}")

                enriched_action = {
                    **action,
                    "state_before": last_state
                }
                enriched_actions.append(enriched_action)

                # Replay the key
                type_action = ActionSchema(
                    tool_name="Type-Tool",
                    tool_arguments={"text": action["key"]},
                    reasoning="Replay recorded key press"
                )
                await mcp_client.execute_action(type_action)
                await asyncio.sleep(0.1)

                # Capture new state
                state_result = await mcp_client.execute_action(state_action)
                if state_result.success:
                    last_state = state_result.evidence

            elif action["type"] == "shortcut":
                # Handle keyboard shortcut
                shortcut_keys = action["keys"]
                shortcut_str = "+".join(shortcut_keys)
                print(f"[Enrichment] Processing shortcut: {shortcut_str}")

                enriched_action = {
                    **action,
                    "state_before": last_state
                }
                enriched_actions.append(enriched_action)

                # Replay the shortcut
                shortcut_action = ActionSchema(
                    tool_name="Shortcut-Tool",
                    tool_arguments={"shortcut": shortcut_keys},
                    reasoning="Replay recorded shortcut"
                )
                await mcp_client.execute_action(shortcut_action)
                await asyncio.sleep(0.2)

                # Capture new state
                state_result = await mcp_client.execute_action(state_action)
                if state_result.success:
                    last_state = state_result.evidence

            elif action["type"] == "special_key":
                # Handle special keys like Enter
                print(f"[Enrichment] Processing special key: {action['key']}")

                enriched_action = {
                    **action,
                    "state_before": last_state
                }
                enriched_actions.append(enriched_action)

                # Replay special key as shortcut
                key_name = action["key"]
                shortcut_action = ActionSchema(
                    tool_name="Shortcut-Tool",
                    tool_arguments={"shortcut": [key_name]},
                    reasoning="Replay special key"
                )
                await mcp_client.execute_action(shortcut_action)
                await asyncio.sleep(0.2)

                # Capture new state
                state_result = await mcp_client.execute_action(state_action)
                if state_result.success:
                    last_state = state_result.evidence

            else:
                # Unknown action type - pass through
                enriched_actions.append(action)

        return enriched_actions

    def _on_click(self, x: int, y: int, button: mouse.Button, pressed: bool) -> None:
        """
        Handle mouse click events - just record raw coordinates

        Args:
            x, y: Click coordinates
            button: Mouse button (left/right)
            pressed: True if pressed, False if released
        """
        # Only capture press events (not release)
        if not pressed or not self.recording:
            return

        # Start recording on first click
        if not self.recording_started:
            self.recording_started = True
            print(f"\n[Recorder] ✓ Recording started! First click detected at ({x}, {y})")
            print(f"[Recorder] Perform your workflow. Press ESC when done.\n")

        print(f"[Recorder] Click detected at ({x}, {y})")

        # Record action with raw coordinates only
        action = {
            "type": "click",
            "raw_coords": [x, y],
            "button": "left" if button == mouse.Button.left else "right",
            "timestamp": time.time()
        }

        self.recorded_actions.append(action)

    def _on_key_press(self, key: keyboard.Key) -> None:
        """
        Handle keyboard press events

        Args:
            key: Key that was pressed
        """
        if not self.recording:
            return

        # Check for ESC key first (stop recording)
        if key == keyboard.Key.esc:
            self.stop_recording()
            return

        # Only record keys if recording has started (after first click)
        if not self.recording_started:
            return

        # Track pressed keys for shortcut detection
        try:
            # Special keys (Ctrl, Alt, Shift, etc.)
            if hasattr(key, 'name'):
                key_name = key.name
                self.pressed_keys.add(key_name)
            # Regular character keys
            elif hasattr(key, 'char') and key.char:
                key_name = key.char
            else:
                key_name = str(key)

            # Detect shortcuts (Ctrl+key, Alt+key)
            if self._is_shortcut():
                shortcut_keys = list(self.pressed_keys) + ([key_name] if hasattr(key, 'char') else [])
                action = {
                    "type": "shortcut",
                    "keys": shortcut_keys,
                    "timestamp": time.time()
                }
                self.recorded_actions.append(action)
                print(f"[Recorder] Shortcut: {'+'.join(shortcut_keys)}")
            else:
                # Regular key press
                if hasattr(key, 'char') and key.char:
                    # Printable character
                    action = {
                        "type": "key",
                        "key": key.char,
                        "timestamp": time.time()
                    }
                    self.recorded_actions.append(action)
                elif key == keyboard.Key.enter:
                    action = {
                        "type": "special_key",
                        "key": "enter",
                        "timestamp": time.time()
                    }
                    self.recorded_actions.append(action)
                    print(f"[Recorder] Key: Enter")

        except Exception as e:
            print(f"[Recorder] Warning: Error recording key press: {e}")

    def _on_key_release(self, key: keyboard.Key) -> None:
        """
        Handle keyboard release events

        Args:
            key: Key that was released
        """
        # Remove from pressed keys set
        try:
            if hasattr(key, 'name'):
                self.pressed_keys.discard(key.name)
        except Exception:
            pass

    def _is_shortcut(self) -> bool:
        """Check if current key combination is a shortcut (has modifier)"""
        modifiers = {'ctrl', 'ctrl_l', 'ctrl_r', 'alt', 'alt_l', 'alt_r', 'shift', 'shift_l', 'shift_r'}
        return bool(self.pressed_keys & modifiers)

    def _find_element_at_coords(self, x: int, y: int, state: Dict) -> Dict[str, Any]:
        """
        Find UI element at given coordinates using State-Tool output

        Args:
            x, y: Click coordinates
            state: State-Tool output (UI element tree)

        Returns:
            Dict with element info: {"type": "button", "text": "Save", "bounds": {...}}
        """
        # Parse State-Tool output to find element at coordinates
        # State-Tool output format varies, need to handle different structures

        try:
            # Try to extract elements from state
            elements = self._extract_elements_from_state(state)

            for element in elements:
                bounds = element.get("bounds", {})
                if self._point_in_bounds(x, y, bounds):
                    return {
                        "type": element.get("type", "unknown"),
                        "text": element.get("text", ""),
                        "name": element.get("name", ""),
                        "bounds": bounds
                    }

        except Exception as e:
            print(f"[Recorder] Warning: Could not identify element at ({x}, {y}): {e}")

        # Fallback: unknown element with coordinates
        return {
            "type": "unknown",
            "coords": [x, y]
        }

    def _extract_elements_from_state(self, state: Dict) -> List[Dict]:
        """
        Extract UI elements from State-Tool output

        State-Tool returns different formats depending on the tool.
        This method tries to parse common formats.

        Args:
            state: State-Tool output

        Returns:
            List of UI elements with bounds
        """
        elements = []

        # Try different state formats
        if isinstance(state, dict):
            # Format 1: Direct elements list
            if "elements" in state:
                elements = state["elements"]

            # Format 2: Nested structure
            elif "ui_tree" in state:
                elements = self._flatten_ui_tree(state["ui_tree"])

            # Format 3: State is itself an element
            elif "bounds" in state:
                elements = [state]

        return elements

    def _flatten_ui_tree(self, tree: Any) -> List[Dict]:
        """Recursively flatten UI tree structure"""
        elements = []

        if isinstance(tree, dict):
            if "bounds" in tree:
                elements.append(tree)
            if "children" in tree:
                for child in tree["children"]:
                    elements.extend(self._flatten_ui_tree(child))
        elif isinstance(tree, list):
            for item in tree:
                elements.extend(self._flatten_ui_tree(item))

        return elements

    def _point_in_bounds(self, x: int, y: int, bounds: Dict) -> bool:
        """
        Check if point (x, y) is within element bounds

        Args:
            x, y: Point coordinates
            bounds: Element bounds dict (various formats)

        Returns:
            True if point is within bounds
        """
        try:
            # Handle different bound formats
            if "left" in bounds and "top" in bounds and "right" in bounds and "bottom" in bounds:
                return (bounds["left"] <= x <= bounds["right"] and
                        bounds["top"] <= y <= bounds["bottom"])
            elif "x" in bounds and "y" in bounds and "width" in bounds and "height" in bounds:
                return (bounds["x"] <= x <= bounds["x"] + bounds["width"] and
                        bounds["y"] <= y <= bounds["y"] + bounds["height"])
        except Exception:
            pass

        return False
