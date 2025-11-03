"""
Parameter Extractor

Identifies parameterizable values in demonstrated workflows (file paths, folder names)
and replaces them with {placeholder} syntax for reusability.
"""

import os
import re
from typing import List, Dict, Tuple, Any
from agent.planning.schemas import ActionSchema


class ParameterExtractor:
    """
    Extracts parameters from demonstrated workflows

    Identifies:
    - File paths (input/output folders and filenames)
    - Reusable values that should become parameters

    Replaces with {placeholder} syntax
    """

    def __init__(self):
        pass

    def extract_parameters(
        self,
        actions: List[ActionSchema]
    ) -> Tuple[List[ActionSchema], Dict[str, str]]:
        """
        Identify and extract parameters from action sequence

        Args:
            actions: Normalized actions with concrete values

        Returns:
            Tuple of (parameterized_actions, parameters_dict)
        """
        print(f"[ParameterExtractor] Analyzing {len(actions)} actions for parameters...")

        parameters = {}
        parameterized_actions = []

        for action in actions:
            # Only Type-Tool actions typically contain parameterizable values
            if action.tool_name == "Type-Tool":
                text = action.tool_arguments.get("text", "")

                # Check if text is a file path
                if self._is_file_path(text):
                    # Extract folder and filename
                    folder, filename = self._split_path(text)

                    # Determine parameter names based on context
                    param_name_folder, param_name_file = self._infer_parameter_names(
                        folder, filename, actions, parameterized_actions
                    )

                    # Store parameters
                    if folder:
                        parameters[param_name_folder] = folder
                    if filename:
                        parameters[param_name_file] = filename

                    # Replace with placeholders
                    if folder and filename:
                        placeholder_text = f"{{{param_name_folder}}}\\{{{param_name_file}}}"
                    elif folder:
                        placeholder_text = f"{{{param_name_folder}}}"
                    else:
                        placeholder_text = f"{{{param_name_file}}}"

                    # Create new action with placeholders
                    parameterized_action = ActionSchema(
                        tool_name=action.tool_name,
                        tool_arguments={
                            **action.tool_arguments,
                            "text": placeholder_text
                        },
                        reasoning=action.reasoning + " (parameterized)",
                        kb_source=action.kb_source
                    )
                    parameterized_actions.append(parameterized_action)
                    print(f"  → Parameterized: {text[:50]}... → {placeholder_text}")
                else:
                    # Not a path, keep as-is
                    parameterized_actions.append(action)
            else:
                # Non-Type-Tool action, keep as-is
                parameterized_actions.append(action)

        print(f"[ParameterExtractor] Extracted {len(parameters)} parameters:")
        for param_name, param_value in parameters.items():
            print(f"  - {param_name}: {param_value[:60]}{'...' if len(param_value) > 60 else ''}")

        return parameterized_actions, parameters

    def _is_file_path(self, text: str) -> bool:
        """
        Heuristic to detect if text is a file path

        Args:
            text: Text to check

        Returns:
            True if text appears to be a file path
        """
        # Check for path-like patterns
        if len(text) < 3:
            return False

        # Windows path patterns
        if re.match(r'^[A-Za-z]:\\', text):  # C:\, D:\, etc.
            return True

        # Unix path patterns
        if text.startswith('/') and len(text) > 1:
            return True

        # UNC paths
        if text.startswith('\\\\'):
            return True

        # Relative paths with multiple segments
        if ('\\' in text or '/' in text) and len(text.split(max(['\\', '/']))) > 2:
            return True

        return False

    def _split_path(self, path: str) -> Tuple[str, str]:
        """
        Split path into folder and filename

        Args:
            path: Full file path

        Returns:
            Tuple of (folder, filename)
        """
        # Normalize path separators
        normalized = path.replace('/', '\\')

        # Check if path ends with a separator (folder only, no file)
        if normalized.endswith('\\'):
            return (normalized.rstrip('\\'), "")

        # Split into folder and filename
        folder = os.path.dirname(normalized)
        filename = os.path.basename(normalized)

        return (folder, filename)

    def _infer_parameter_names(
        self,
        folder: str,
        filename: str,
        all_actions: List[ActionSchema],
        processed_actions: List[ActionSchema]
    ) -> Tuple[str, str]:
        """
        Infer semantic parameter names based on context

        Heuristics:
        - If typed before "Open" action → input_folder/input_file
        - If typed before "Save" action → output_folder/output_filename
        - Look at previous actions for clues

        Args:
            folder: Folder path
            filename: Filename
            all_actions: All actions in sequence
            processed_actions: Actions processed so far

        Returns:
            Tuple of (folder_param_name, file_param_name)
        """
        # Determine context from previous actions
        context = self._get_context(processed_actions)

        # Check if this is input or output
        if "open" in context.lower() or "load" in context.lower():
            folder_param = "input_folder"
            file_param = "input_file" if filename and not filename.startswith("*.") else "file_pattern"
        elif "save" in context.lower() or "export" in context.lower():
            folder_param = "output_folder"
            file_param = "output_filename"
        else:
            # Default naming
            folder_param = "folder_path"
            file_param = "filename"

        # Ensure unique parameter names if already used
        if folder_param in [p for a in processed_actions for p in self._extract_placeholders(a)]:
            # Already have input_folder, use input_folder_2
            suffix = 2
            while f"{folder_param}_{suffix}" in [p for a in processed_actions for p in self._extract_placeholders(a)]:
                suffix += 1
            folder_param = f"{folder_param}_{suffix}"

        if file_param in [p for a in processed_actions for p in self._extract_placeholders(a)]:
            suffix = 2
            while f"{file_param}_{suffix}" in [p for a in processed_actions for p in self._extract_placeholders(a)]:
                suffix += 1
            file_param = f"{file_param}_{suffix}"

        return (folder_param, file_param)

    def _get_context(self, processed_actions: List[ActionSchema]) -> str:
        """
        Get context from recent actions

        Args:
            processed_actions: Actions processed so far

        Returns:
            Context string (e.g., "click open", "click save")
        """
        # Look at last few actions
        recent_actions = processed_actions[-5:] if len(processed_actions) >= 5 else processed_actions

        context_parts = []
        for action in recent_actions:
            if action.tool_name == "Click-Tool":
                # Extract clicked element text from reasoning
                reasoning = action.reasoning.lower()
                context_parts.append(reasoning)

        return " ".join(context_parts)

    def _extract_placeholders(self, action: ActionSchema) -> List[str]:
        """
        Extract placeholder names from action

        Args:
            action: Action to check

        Returns:
            List of placeholder names (e.g., ["input_folder", "output_filename"])
        """
        placeholders = []

        # Check tool_arguments for placeholders
        for key, value in action.tool_arguments.items():
            if isinstance(value, str):
                # Find all {placeholder} patterns
                matches = re.findall(r'\{(\w+)\}', value)
                placeholders.extend(matches)

        return placeholders
