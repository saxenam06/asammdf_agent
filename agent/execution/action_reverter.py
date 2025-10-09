"""
Action reversal strategies for local planning
Knows how to undo different types of GUI actions
"""

import json
import re
from typing import Optional, List, Dict, Any
from openai import OpenAI
import os

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from agent.planning.schemas import ActionSchema


class ActionReverter:
    """
    Generates reversal actions for different GUI interaction types
    Uses heuristics + LLM reasoning to determine best revert strategy
    """

    def __init__(self, mcp_client, llm_client: Optional[OpenAI] = None):
        """
        Initialize action reverter

        Args:
            mcp_client: MCP client for executing actions
            llm_client: Optional OpenAI client for LLM-based reasoning
        """
        self.mcp_client = mcp_client
        self.llm_client = llm_client
        self.model = "gpt-4o-mini"

    def can_revert(self, action: ActionSchema) -> bool:
        """
        Check if an action can be reverted

        Args:
            action: Action to check

        Returns:
            True if action is revertible
        """
        # State-Tool calls don't need reversion (they're read-only)
        if action.tool_name == 'State-Tool':
            return False

        # Most other actions can be reverted with varying strategies
        revertible_tools = ['Click-Tool', 'Type-Tool', 'Key-Tool', 'Hotkey-Tool']
        return action.tool_name in revertible_tools

    def generate_revert_action(
        self,
        action: ActionSchema,
        state_after: str,
        state_before: Optional[str] = None
    ) -> Optional[ActionSchema]:
        """
        Generate an action that reverts the given action

        Args:
            action: Original action to revert
            state_after: UI state after the action
            state_before: UI state before the action (optional, for context)

        Returns:
            Revert action, or None if not revertible
        """
        if not self.can_revert(action):
            return None

        # Use heuristic-based strategies
        if action.tool_name == 'Click-Tool':
            return self._revert_click(action, state_after, state_before)
        elif action.tool_name == 'Type-Tool':
            return self._revert_type(action, state_after)
        elif action.tool_name == 'Key-Tool':
            return self._revert_key(action, state_after)
        elif action.tool_name == 'Hotkey-Tool':
            return self._revert_hotkey(action, state_after)

        # Fallback: use LLM to determine revert strategy
        return self._llm_generate_revert(action, state_after, state_before)

    def _revert_click(
        self,
        action: ActionSchema,
        state_after: str,
        state_before: Optional[str] = None
    ) -> Optional[ActionSchema]:
        """
        Revert a click action

        Strategy depends on what was clicked:
        - Checkbox/Toggle: Click same location again
        - Button that opened dialog: Find Cancel/Close button
        - Menu item: Click elsewhere or ESC
        """
        reasoning = action.reasoning.lower() if action.reasoning else ""

        # Checkbox/Toggle - click same location to toggle back
        if any(word in reasoning for word in ['checkbox', 'toggle', 'radio', 'switch']):
            return ActionSchema(
                tool_name='Click-Tool',
                tool_arguments=action.tool_arguments,  # Same location
                reasoning=f"Revert: Toggle checkbox back (was: {action.reasoning})"
            )

        # Button that opened dialog - find Cancel/Close
        if any(word in reasoning for word in ['open', 'dialog', 'window', 'popup']):
            return self._find_cancel_button(state_after, action)

        # Default: Use LLM to determine best revert strategy
        return self._llm_generate_revert(action, state_after, state_before)

    def _find_cancel_button(self, state: str, original_action: ActionSchema) -> Optional[ActionSchema]:
        """Find and click Cancel/Close button in current state"""
        if not self.llm_client:
            # Fallback: try ESC key
            return ActionSchema(
                tool_name='Key-Tool',
                tool_arguments={'key': 'esc'},
                reasoning=f"Revert: Close dialog with ESC (was: {original_action.reasoning})"
            )

        prompt = f"""Find the Cancel or Close button in this UI state.

UI State:
```
{state[:3000]}  # Limit to avoid token overflow
```

Look for buttons with text like: Cancel, Close, X, No, Abort
Or close buttons typically in top-right corner.

Respond with JSON:
{{
  "found": true/false,
  "button_type": "cancel|close|x|esc",
  "coordinates": [x, y],  # If found
  "alternative": "esc_key"  # If not found, suggest alternative
}}
"""
        try:
            response = self.llm_client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0,
                response_format={"type": "json_object"}
            )

            result = json.loads(response.choices[0].message.content.strip())

            if result.get('found') and result.get('coordinates'):
                coords = result['coordinates']
                return ActionSchema(
                    tool_name='Click-Tool',
                    tool_arguments={'loc': coords, 'button': 'left', 'clicks': 1},
                    reasoning=f"Revert: Click {result.get('button_type')} button to close dialog"
                )
            else:
                # Fallback: ESC key
                return ActionSchema(
                    tool_name='Key-Tool',
                    tool_arguments={'key': 'esc'},
                    reasoning=f"Revert: Close dialog with ESC (no cancel button found)"
                )

        except Exception as e:
            print(f"  ! Error finding cancel button: {e}")
            # Fallback: ESC key
            return ActionSchema(
                tool_name='Key-Tool',
                tool_arguments={'key': 'esc'},
                reasoning=f"Revert: Close dialog with ESC (error finding cancel)"
            )

    def _revert_type(self, action: ActionSchema, state_after: str) -> ActionSchema:
        """
        Revert a type action by clearing the text field

        Strategy: Select all (Ctrl+A) + Delete
        """
        return ActionSchema(
            tool_name='Hotkey-Tool',
            tool_arguments={'keys': 'ctrl+a', 'wait_time': 0.1},
            reasoning=f"Revert: Clear text field (was: {action.reasoning})"
        )

    def _revert_key(self, action: ActionSchema, state_after: str) -> Optional[ActionSchema]:
        """
        Revert a key press

        Most key presses can't be directly reverted, but some have inverses:
        - ESC -> (no revert needed, it's already a cancel action)
        - Enter -> ESC (if it opened something)
        """
        key = action.tool_arguments.get('key', '').lower()

        if key == 'enter':
            return ActionSchema(
                tool_name='Key-Tool',
                tool_arguments={'key': 'esc'},
                reasoning=f"Revert: ESC to undo Enter action"
            )

        # Most key presses can't be reverted
        return None

    def _revert_hotkey(self, action: ActionSchema, state_after: str) -> Optional[ActionSchema]:
        """
        Revert a hotkey action

        Some hotkeys have inverses:
        - Ctrl+Z -> Ctrl+Y (redo)
        - Ctrl+C -> (no revert needed, copy is non-destructive)
        """
        keys = action.tool_arguments.get('keys', '').lower()

        # Undo -> Redo
        if keys in ['ctrl+z', 'ctrl+shift+z']:
            return ActionSchema(
                tool_name='Hotkey-Tool',
                tool_arguments={'keys': 'ctrl+y', 'wait_time': 0.1},
                reasoning=f"Revert: Redo to undo the undo"
            )

        # Most hotkeys can't be easily reverted
        return None

    def _llm_generate_revert(
        self,
        action: ActionSchema,
        state_after: str,
        state_before: Optional[str] = None
    ) -> Optional[ActionSchema]:
        """
        Use LLM to generate a revert action when heuristics fail

        Args:
            action: Original action
            state_after: UI state after action
            state_before: UI state before action

        Returns:
            Revert action or None
        """
        if not self.llm_client:
            return None

        state_before_text = state_before if state_before else "Not available"

        prompt = f"""You are reverting a GUI action to restore the previous state.

Original Action:
- Tool: {action.tool_name}
- Arguments: {json.dumps(action.tool_arguments)}
- Reasoning: {action.reasoning}

State Before Action:
```
{state_before_text[:1500]}
```

State After Action:
```
{state_after[:1500]}
```

Generate an action that reverts the original action and restores the state.

Examples:
- If clicked a checkbox, click it again to toggle back
- If opened a dialog, find and click Cancel/Close
- If typed text, select all and delete
- If clicked a button, find undo option or close opened window

Respond with JSON:
{{
  "can_revert": true/false,
  "revert_action": {{
    "tool_name": "Click-Tool|Type-Tool|Key-Tool|Hotkey-Tool",
    "tool_arguments": {{}},
    "reasoning": "explanation of how this reverts the action"
  }},
  "explanation": "why this strategy reverts the action"
}}

If action cannot be reverted, set can_revert to false.
"""

        try:
            response = self.llm_client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=400,
                temperature=0.2,
                response_format={"type": "json_object"}
            )

            result = json.loads(response.choices[0].message.content.strip())

            if result.get('can_revert') and result.get('revert_action'):
                ra = result['revert_action']
                print(f"  → LLM revert strategy: {result.get('explanation')}")
                return ActionSchema(
                    tool_name=ra['tool_name'],
                    tool_arguments=ra['tool_arguments'],
                    reasoning=ra.get('reasoning', 'LLM-generated revert action')
                )
            else:
                print(f"  ! LLM determined action cannot be reverted")
                return None

        except Exception as e:
            print(f"  ! Error generating LLM revert action: {e}")
            return None

    def suggest_exploration_options(
        self,
        action: ActionSchema,
        state_after: str,
        goal: str
    ) -> List[Dict[str, str]]:
        """
        Suggest alternative exploration options before reverting

        Args:
            action: Action that was just executed
            state_after: Current UI state
            goal: High-level goal we're trying to achieve

        Returns:
            List of exploration options with keys: name, description, action_hint
        """
        if not self.llm_client:
            return []

        prompt = f"""We executed an action but haven't reached our goal yet.
Before reverting, suggest alternative exploration options from the current state.

Goal: {goal}

Action Just Executed:
- Tool: {action.tool_name}
- Reasoning: {action.reasoning}

Current State After Action:
```
{state_after[:2000]}
```

Suggest 2-3 alternative actions we could try from this state to move toward the goal.
Think about:
- Different form field values
- Different button choices
- Different menu paths
- Different dialog options

Respond with JSON:
{{
  "options": [
    {{
      "name": "short_name",
      "description": "what to try",
      "action_hint": "which button/field/menu to interact with"
    }}
  ]
}}
"""

        try:
            response = self.llm_client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0.4,
                response_format={"type": "json_object"}
            )

            result = json.loads(response.choices[0].message.content.strip())
            options = result.get('options', [])

            print(f"  → {len(options)} exploration options suggested:")
            for opt in options:
                print(f"    - {opt.get('name')}: {opt.get('description')}")

            return options

        except Exception as e:
            print(f"  ! Error suggesting exploration options: {e}")
            return []
