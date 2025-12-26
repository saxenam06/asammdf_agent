"""
Parameter Substitution Utilities

Provides functions to:
- Substitute placeholders in text with actual parameter values
- Detect placeholders in text
- Validate parameter completeness
"""

import re
from typing import Dict, List, Any, Optional


def find_placeholders(text: str) -> List[str]:
    """
    Find all placeholders in text using {placeholder_name} syntax

    Args:
        text: Text that may contain placeholders

    Returns:
        List of placeholder names found (without braces)

    Examples:
        >>> find_placeholders("Open {input_folder} and save to {output_file}")
        ['input_folder', 'output_file']
    """
    pattern = r'\{([a-zA-Z0-9_]+)\}'
    matches = re.findall(pattern, text)
    return matches


def substitute_parameters(
    text: str,
    parameters: Dict[str, str],
    strict: bool = True
) -> str:
    """
    Replace placeholders in text with parameter values

    Args:
        text: Text containing placeholders like {input_folder}
        parameters: Dict mapping placeholder names to values
        strict: If True, raise error for missing parameters. If False, leave unmatched placeholders as-is

    Returns:
        Text with placeholders replaced

    Raises:
        ValueError: If strict=True and required parameter is missing

    Examples:
        >>> substitute_parameters(
        ...     "Open {input_folder}",
        ...     {"input_folder": "C:\\\\Users\\\\data"}
        ... )
        'Open C:\\\\Users\\\\data'
    """
    if not parameters:
        if strict and find_placeholders(text):
            raise ValueError(f"Parameters required but none provided. Found placeholders: {find_placeholders(text)}")
        return text

    # Find all placeholders
    placeholders = find_placeholders(text)

    # Check for missing parameters in strict mode
    if strict:
        missing = [p for p in placeholders if p not in parameters]
        if missing:
            raise ValueError(f"Missing required parameters: {missing}")

    # Substitute each placeholder
    result = text
    for placeholder in placeholders:
        if placeholder in parameters:
            # Use regex to replace all occurrences of {placeholder}
            # Escape the replacement value to handle backslashes correctly
            pattern = r'\{' + re.escape(placeholder) + r'\}'
            replacement = parameters[placeholder].replace('\\', r'\\')  # Escape backslashes for regex
            result = re.sub(pattern, replacement, result)

    return result


def substitute_in_action(
    action: Dict[str, Any],
    parameters: Dict[str, str],
    strict: bool = True
) -> Dict[str, Any]:
    """
    Substitute placeholders in action dictionary (recursive)

    Replaces placeholders in all string values within the action dict,
    including nested dictionaries and lists.

    Args:
        action: Action dictionary (e.g., {"tool_name": "Type-Tool", "tool_arguments": {...}})
        parameters: Parameter mappings
        strict: If True, raise error for missing parameters

    Returns:
        New action dict with substituted values

    Examples:
        >>> action = {
        ...     "tool_name": "Type-Tool",
        ...     "tool_arguments": {
        ...         "text": "{input_folder}",
        ...         "clear": True
        ...     }
        ... }
        >>> substitute_in_action(action, {"input_folder": "C:\\\\data"})
        {'tool_name': 'Type-Tool', 'tool_arguments': {'text': 'C:\\\\data', 'clear': True}}
    """
    if isinstance(action, dict):
        return {
            key: substitute_in_action(value, parameters, strict)
            for key, value in action.items()
        }
    elif isinstance(action, list):
        return [
            substitute_in_action(item, parameters, strict)
            for item in action
        ]
    elif isinstance(action, str):
        return substitute_parameters(action, parameters, strict)
    else:
        # Return as-is for non-string types (int, bool, None, etc.)
        return action


def validate_parameters(
    required_placeholders: List[str],
    provided_parameters: Dict[str, str]
) -> tuple[bool, List[str]]:
    """
    Validate that all required placeholders have corresponding parameters

    Args:
        required_placeholders: List of placeholder names that must be provided
        provided_parameters: Dict of provided parameter mappings

    Returns:
        Tuple of (is_valid, missing_parameters)

    Examples:
        >>> validate_parameters(
        ...     ["input_folder", "output_file"],
        ...     {"input_folder": "C:\\\\data"}
        ... )
        (False, ['output_file'])
    """
    missing = [p for p in required_placeholders if p not in provided_parameters]
    return (len(missing) == 0, missing)


def extract_parameters_from_action_plan(action_plan: List[Dict[str, Any]]) -> List[str]:
    """
    Extract all unique placeholders from an action plan

    Args:
        action_plan: List of action dictionaries

    Returns:
        Sorted list of unique placeholder names found

    Examples:
        >>> actions = [
        ...     {"tool_arguments": {"text": "{input_folder}"}},
        ...     {"tool_arguments": {"text": "{output_file}"}}
        ... ]
        >>> extract_parameters_from_action_plan(actions)
        ['input_folder', 'output_file']
    """
    placeholders = set()

    def extract_from_value(value):
        """Recursively extract placeholders from any value"""
        if isinstance(value, str):
            placeholders.update(find_placeholders(value))
        elif isinstance(value, dict):
            for v in value.values():
                extract_from_value(v)
        elif isinstance(value, list):
            for item in value:
                extract_from_value(item)

    for action in action_plan:
        extract_from_value(action)

    return sorted(list(placeholders))


if __name__ == "__main__":
    """Test parameter substitution"""

    print("Testing Parameter Substitution Utilities\n")

    # Test 1: Find placeholders
    print("Test 1: Find placeholders")
    text = "Open {input_folder} and save to {output_file}"
    found = find_placeholders(text)
    print(f"  Text: {text}")
    print(f"  Found: {found}")
    assert found == ['input_folder', 'output_file'], "Failed to find placeholders"
    print("  [OK] Passed\n")

    # Test 2: Substitute parameters
    print("Test 2: Substitute parameters")
    params = {
        "input_folder": "C:\\Users\\data",
        "output_file": "C:\\Users\\output.mf4"
    }
    result = substitute_parameters(text, params)
    print(f"  Original: {text}")
    print(f"  Params: {params}")
    print(f"  Result: {result}")
    assert result == "Open C:\\Users\\data and save to C:\\Users\\output.mf4"
    print("  [OK] Passed\n")

    # Test 3: Substitute in action
    print("Test 3: Substitute in action")
    action = {
        "tool_name": "Type-Tool",
        "tool_arguments": {
            "text": "{input_folder}",
            "clear": True,
            "press_enter": True
        },
        "reasoning": "Enter the folder path {input_folder}"
    }
    result_action = substitute_in_action(action, {"input_folder": "C:\\data"})
    print(f"  Original action text: {action['tool_arguments']['text']}")
    print(f"  Substituted action text: {result_action['tool_arguments']['text']}")
    assert result_action['tool_arguments']['text'] == "C:\\data"
    assert result_action['tool_arguments']['clear'] == True
    print("  [OK] Passed\n")

    # Test 4: Extract parameters from action plan
    print("Test 4: Extract parameters from action plan")
    actions = [
        {"tool_arguments": {"text": "{input_folder}"}},
        {"tool_arguments": {"text": "{output_file}"}},
        {"reasoning": "Use {input_folder} again"}
    ]
    extracted = extract_parameters_from_action_plan(actions)
    print(f"  Extracted: {extracted}")
    assert extracted == ['input_folder', 'output_file']
    print("  [OK] Passed\n")

    # Test 5: Validate parameters
    print("Test 5: Validate parameters")
    valid, missing = validate_parameters(
        ["input_folder", "output_file"],
        {"input_folder": "C:\\data"}
    )
    print(f"  Required: ['input_folder', 'output_file']")
    print(f"  Provided: {{'input_folder': 'C:\\\\data'}}")
    print(f"  Valid: {valid}, Missing: {missing}")
    assert not valid and missing == ['output_file']
    print("  [OK] Passed\n")

    print("[SUCCESS] All parameter substitution tests passed!")
