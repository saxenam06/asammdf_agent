"""
Action Normalizer

Converts raw recorded actions (coordinates, key presses) into structured ActionSchema
objects with symbolic references (compatible with autonomous workflow format).
"""

from typing import List, Dict, Any, Tuple
from agent.planning.schemas import ActionSchema


class ActionNormalizer:
    """
    Transforms raw recorded actions into ActionSchema format

    Conversions:
    - Raw click coordinates → Symbolic references (last_state:button:Save)
    - Key sequences → Type-Tool actions
    - Keyboard shortcuts → Shortcut-Tool actions
    - Inserts State-Tool calls before UI interactions
    """

    def __init__(self):
        pass

    def normalize(self, recorded_actions: List[Dict[str, Any]]) -> List[ActionSchema]:
        """
        Convert raw actions to ActionSchema list

        Args:
            recorded_actions: List of raw actions from ActionRecorder

        Returns:
            List of ActionSchema objects ready for plan creation
        """
        if not recorded_actions:
            return []

        print(f"[Normalizer] Normalizing {len(recorded_actions)} raw actions...")

        # Step 1: Group related actions (consecutive keys → typing)
        action_groups = self._group_actions(recorded_actions)
        print(f"[Normalizer] Grouped into {len(action_groups)} action groups")

        # Step 2: Convert each group to ActionSchema
        normalized = []
        for group in action_groups:
            action = self._normalize_action_group(group)
            if action:
                normalized.append(action)

        # Step 3: Insert State-Tool calls before each UI interaction
        normalized_with_state = self._insert_state_tools(normalized)

        print(f"[Normalizer] Produced {len(normalized_with_state)} normalized actions")

        return normalized_with_state

    def _group_actions(self, actions: List[Dict]) -> List[Dict]:
        """
        Group consecutive actions into logical units

        Groups:
        - Consecutive key presses → Single typing action
        - Click + immediate special_key → Click (ignore redundant keys)
        - Shortcut detection

        Args:
            actions: Raw actions

        Returns:
            Grouped actions
        """
        grouped = []
        typing_buffer = []
        i = 0

        while i < len(actions):
            action = actions[i]

            if action["type"] == "key":
                # Accumulate printable characters
                typing_buffer.append(action["key"])
                i += 1

            elif action["type"] == "special_key" and action["key"] == "enter":
                # Flush typing buffer with Enter
                if typing_buffer:
                    grouped.append({
                        "type": "typing",
                        "text": "".join(typing_buffer),
                        "press_enter": True,
                        "timestamp": action["timestamp"]
                    })
                    typing_buffer = []
                else:
                    # Just Enter key
                    grouped.append({
                        "type": "enter_key",
                        "timestamp": action["timestamp"]
                    })
                i += 1

            else:
                # Flush typing buffer without Enter
                if typing_buffer:
                    grouped.append({
                        "type": "typing",
                        "text": "".join(typing_buffer),
                        "press_enter": False,
                        "timestamp": action["timestamp"]
                    })
                    typing_buffer = []

                # Add current action
                grouped.append(action)
                i += 1

        # Flush remaining typing buffer
        if typing_buffer:
            grouped.append({
                "type": "typing",
                "text": "".join(typing_buffer),
                "press_enter": False,
                "timestamp": actions[-1]["timestamp"]
            })

        return grouped

    def _normalize_action_group(self, group: Dict) -> ActionSchema:
        """
        Convert single action group to ActionSchema

        Args:
            group: Grouped action

        Returns:
            ActionSchema object or None
        """
        action_type = group["type"]

        if action_type == "click":
            return self._normalize_click(group)
        elif action_type == "typing":
            return self._normalize_typing(group)
        elif action_type == "shortcut":
            return self._normalize_shortcut(group)
        elif action_type == "enter_key":
            return self._normalize_enter_key(group)
        else:
            # Unknown action type
            print(f"[Normalizer] Warning: Unknown action type: {action_type}")
            return None

    def _normalize_click(self, action: Dict) -> ActionSchema:
        """
        Convert click action to Click-Tool ActionSchema

        Args:
            action: Raw click action with element info

        Returns:
            ActionSchema for Click-Tool
        """
        element = action.get("element", {})
        button = action.get("button", "left")

        # Create symbolic reference if element identified
        if element.get("type") != "unknown":
            elem_type = element["type"]
            elem_text = element.get("text", element.get("name", ""))

            if elem_text:
                symbolic_ref = [f"last_state:{elem_type}:{elem_text}"]
                reasoning = f"Click {elem_text} {elem_type} (from demonstration)"
            else:
                # No text, use coordinates as fallback
                symbolic_ref = action["raw_coords"]
                reasoning = f"Click at coordinates {action['raw_coords']} (from demonstration)"
        else:
            # Unknown element, use raw coordinates
            symbolic_ref = action["raw_coords"]
            reasoning = f"Click at coordinates {action['raw_coords']} (from demonstration)"

        return ActionSchema(
            tool_name="Click-Tool",
            tool_arguments={
                "loc": symbolic_ref,
                "button": button,
                "clicks": 1
            },
            reasoning=reasoning,
            kb_source=None  # No KB source for demonstrated actions
        )

    def _normalize_typing(self, action: Dict) -> ActionSchema:
        """
        Convert typing action to Type-Tool ActionSchema

        Args:
            action: Grouped typing action

        Returns:
            ActionSchema for Type-Tool
        """
        text = action["text"]
        press_enter = action.get("press_enter", False)

        return ActionSchema(
            tool_name="Type-Tool",
            tool_arguments={
                "text": text,
                "clear": False,  # Assume no clearing unless specified
                "press_enter": press_enter
            },
            reasoning=f"Type '{text[:30]}{'...' if len(text) > 30 else ''}' (from demonstration)"
        )

    def _normalize_shortcut(self, action: Dict) -> ActionSchema:
        """
        Convert keyboard shortcut to Shortcut-Tool ActionSchema

        Args:
            action: Shortcut action

        Returns:
            ActionSchema for Shortcut-Tool
        """
        keys = action.get("keys", [])

        # Normalize key names (ctrl_l → ctrl, etc.)
        normalized_keys = []
        for key in keys:
            if key in ["ctrl_l", "ctrl_r"]:
                if "ctrl" not in normalized_keys:
                    normalized_keys.append("ctrl")
            elif key in ["alt_l", "alt_r"]:
                if "alt" not in normalized_keys:
                    normalized_keys.append("alt")
            elif key in ["shift_l", "shift_r"]:
                if "shift" not in normalized_keys:
                    normalized_keys.append("shift")
            else:
                normalized_keys.append(key)

        return ActionSchema(
            tool_name="Shortcut-Tool",
            tool_arguments={
                "shortcut": normalized_keys
            },
            reasoning=f"Press {'+'.join(normalized_keys)} shortcut (from demonstration)"
        )

    def _normalize_enter_key(self, action: Dict) -> ActionSchema:
        """
        Convert standalone Enter key to Key-Tool ActionSchema

        Args:
            action: Enter key action

        Returns:
            ActionSchema for Key-Tool
        """
        return ActionSchema(
            tool_name="Key-Tool",
            tool_arguments={
                "key": "enter"
            },
            reasoning="Press Enter key (from demonstration)"
        )

    def _insert_state_tools(self, actions: List[ActionSchema]) -> List[ActionSchema]:
        """
        Insert State-Tool calls before each UI interaction

        Matches the pattern used in autonomous workflow where State-Tool
        is called before each Click/Type action.

        Args:
            actions: Normalized actions without State-Tool calls

        Returns:
            Actions with State-Tool calls inserted
        """
        augmented = []
        needs_state_before = ["Click-Tool", "Type-Tool"]

        for action in actions:
            # Insert State-Tool before certain actions
            if action.tool_name in needs_state_before:
                augmented.append(ActionSchema(
                    tool_name="State-Tool",
                    tool_arguments={"use_vision": False},
                    reasoning="Capture UI state before interaction (auto-inserted)"
                ))

            augmented.append(action)

        # Add initial State-Tool at the beginning if not present
        if not augmented or augmented[0].tool_name != "State-Tool":
            augmented.insert(0, ActionSchema(
                tool_name="State-Tool",
                tool_arguments={"use_vision": False},
                reasoning="Capture initial UI state"
            ))

        return augmented
