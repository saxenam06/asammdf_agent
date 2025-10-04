"""
Generic action executor that interprets skill action_sequences dynamically
No hardcoded task-specific methods - fully driven by skill catalog
"""

import sys
import os
import re
from typing import Dict, Any

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from agent.planning.schemas import ActionSchema, ExecutionResult, SkillSchema
from agent.execution.action_primitives import ActionPrimitives


class StateBasedExecutor:
    """
    Generic executor that interprets action_sequence from skills
    """

    def __init__(self, app_name: str = "asammdf 8.6.10"):
        """
        Initialize executor

        Args:
            app_name: Application window name
        """
        self.app_name = app_name
        self.primitives = ActionPrimitives(app_name=app_name)

    def execute_action(self, action: ActionSchema, skill: SkillSchema) -> ExecutionResult:
        """
        Execute a skill by interpreting its action_sequence

        Args:
            action: Action from plan (contains skill_id and args)
            skill: Skill definition (contains action_sequence)

        Returns:
            Execution result
        """
        print(f"[Executing] {action.skill_id} with args {action.args}")

        try:
            # Execute each step in action_sequence
            for step in skill.action_sequence:
                # Substitute arguments from action.args into step
                step_with_args = self._substitute_args(step, action.args)

                print(f"  → {step_with_args}")

                # Parse and execute primitive action
                self._execute_primitive(step_with_args)

            return ExecutionResult(
                success=True,
                action=action.skill_id,
                evidence=f"Completed {len(skill.action_sequence)} steps"
            )

        except Exception as e:
            print(f"  ✗ Execution failed: {e}")
            return ExecutionResult(
                success=False,
                action=action.skill_id,
                error=str(e)
            )

    def _substitute_args(self, action_string: str, args: Dict[str, Any]) -> str:
        """
        Substitute arguments into action string

        Example:
            action_string = "type_in_dialog('{folder}/*.mf4')"
            args = {"folder": "C:\\data"}
            returns = "type_in_dialog('C:\\data/*.mf4')"

        Args:
            action_string: Action with placeholders
            args: Argument values

        Returns:
            Action string with substituted values
        """
        result = action_string
        for key, value in args.items():
            result = result.replace(f'{{{key}}}', str(value))
        return result

    def _execute_primitive(self, action_string: str):
        """
        Parse and execute a primitive action

        Supports formats:
            - click_button('Export')
            - select_tab('Multiple files')
            - type_in_field('sample.mf4', field_name='File name')
            - press_shortcut(['ctrl', 'o'])
            - wait(2)

        Args:
            action_string: Primitive action to execute

        Raises:
            Exception: If action cannot be parsed or executed
        """
        # Parse: "function_name(arg1, arg2, kwarg=value)"
        match = re.match(r'(\w+)\((.*)\)', action_string.strip())

        if not match:
            raise ValueError(f"Invalid action format: {action_string}")

        function_name = match.group(1)
        args_string = match.group(2)

        # Parse arguments
        args, kwargs = self._parse_arguments(args_string)

        # Get primitive function
        if not hasattr(self.primitives, function_name):
            raise ValueError(f"Unknown primitive action: {function_name}")

        primitive_func = getattr(self.primitives, function_name)

        # Execute
        result = primitive_func(*args, **kwargs)

        return result

    def _parse_arguments(self, args_string: str) -> tuple[list, dict]:
        """
        Parse function arguments from string

        Examples:
            "'Export'" → (['Export'], {})
            "'File name', clear=True" → (['File name'], {'clear': True})
            "['ctrl', 'o']" → ([['ctrl', 'o']], {})

        Args:
            args_string: Arguments as string

        Returns:
            (positional_args, keyword_args)
        """
        if not args_string.strip():
            return ([], {})

        args = []
        kwargs = {}

        # Simple parser (handles common cases)
        # Split by comma (not inside quotes or brackets)
        parts = self._split_args(args_string)

        for part in parts:
            part = part.strip()

            if '=' in part:
                # Keyword argument
                key, value = part.split('=', 1)
                kwargs[key.strip()] = self._parse_value(value.strip())
            else:
                # Positional argument
                args.append(self._parse_value(part))

        return (args, kwargs)

    def _split_args(self, args_string: str) -> list[str]:
        """
        Split arguments by comma, respecting quotes and brackets

        Args:
            args_string: Arguments string

        Returns:
            List of argument strings
        """
        parts = []
        current = ""
        depth = 0
        in_quotes = False
        quote_char = None

        for char in args_string:
            if char in ('"', "'") and not in_quotes:
                in_quotes = True
                quote_char = char
                current += char
            elif char == quote_char and in_quotes:
                in_quotes = False
                quote_char = None
                current += char
            elif char in ('[', '{') and not in_quotes:
                depth += 1
                current += char
            elif char in (']', '}') and not in_quotes:
                depth -= 1
                current += char
            elif char == ',' and depth == 0 and not in_quotes:
                parts.append(current)
                current = ""
            else:
                current += char

        if current:
            parts.append(current)

        return parts

    def _parse_value(self, value_string: str) -> Any:
        """
        Parse value from string to Python type

        Args:
            value_string: Value as string

        Returns:
            Parsed value
        """
        value_string = value_string.strip()

        # String (quoted)
        if (value_string.startswith("'") and value_string.endswith("'")) or \
           (value_string.startswith('"') and value_string.endswith('"')):
            return value_string[1:-1]

        # List
        if value_string.startswith('[') and value_string.endswith(']'):
            # Simple list parsing
            content = value_string[1:-1]
            items = self._split_args(content)
            return [self._parse_value(item.strip()) for item in items]

        # Boolean
        if value_string.lower() == 'true':
            return True
        if value_string.lower() == 'false':
            return False

        # None
        if value_string.lower() == 'none':
            return None

        # Number
        try:
            if '.' in value_string:
                return float(value_string)
            return int(value_string)
        except ValueError:
            pass

        # Default: return as string
        return value_string


if __name__ == "__main__":
    """
    Test generic executor
    """
    from agent.planning.schemas import ActionSchema, SkillSchema

    # Define a test skill with action_sequence
    test_skill = SkillSchema(
        skill_id="open_file",
        description="Open an MF4 file",
        ui_location="File menu",
        action_sequence=[
            "press_shortcut(['ctrl', 'o'])",
            "wait(2)",
            "type_in_dialog('{filename}', field_name='File name')",
            "click_button('Open', prefer_bottom=True)",
            "wait(2)"
        ],
        prerequisites=["app_open"],
        output_state="file_loaded",
        doc_citation="test",
        parameters={"filename": "str"}
    )

    # Action with arguments
    test_action = ActionSchema(
        skill_id="open_file",
        args={"filename": "sample.mf4"},
        doc_citation="test",
        expected_state="file_loaded"
    )

    # Execute
    executor = StateBasedExecutor()

    print("\n" + "="*80)
    print("Testing Generic Action Executor")
    print("="*80 + "\n")

    print(f"Skill: {test_skill.skill_id}")
    print(f"Action sequence: {test_skill.action_sequence}")
    print(f"Args: {test_action.args}\n")

    result = executor.execute_action(test_action, test_skill)

    print(f"\nResult: {result.model_dump_json(indent=2)}")
