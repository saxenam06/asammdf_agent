"""
Task Inferencer

Uses LLM to infer high-level task description from demonstrated action sequence.
"""

import json
from typing import List, Dict
from openai import OpenAI

from agent.planning.schemas import ActionSchema
from agent.utils.cost_tracker import CostTracker


class TaskInferencer:
    """
    Infers task description from action sequence using LLM

    Uses GPT-4o-mini to analyze demonstrated actions and generate
    a concise, reusable task description.
    """

    def __init__(self, model: str = "gpt-4o-mini"):
        """
        Initialize task inferencer

        Args:
            model: OpenAI model to use for inference
        """
        self.model = model
        self.client = OpenAI()
        self.cost_tracker = CostTracker()

    def infer_task(
        self,
        actions: List[ActionSchema],
        parameters: Dict[str, str]
    ) -> str:
        """
        Infer task description from demonstrated actions

        Args:
            actions: Parameterized action sequence
            parameters: Extracted parameters

        Returns:
            Task description string
        """
        print(f"[TaskInferencer] Inferring task description using {self.model}...")

        # Build action summary for LLM
        action_summary = self._build_action_summary(actions)

        # Create prompt
        prompt = self._create_inference_prompt(action_summary, parameters)

        try:
            # Call LLM
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_tokens=150,
                temperature=0.3  # Lower temperature for more consistent descriptions
            )

            task_description = response.choices[0].message.content.strip()

            # Track cost
            self.cost_tracker.track_call(
                model=self.model,
                input_tokens=response.usage.prompt_tokens,
                output_tokens=response.usage.completion_tokens,
                purpose="task_inference"
            )

            print(f"[TaskInferencer] ✓ Inferred task: {task_description}")

            return task_description

        except Exception as e:
            print(f"[TaskInferencer] Warning: LLM inference failed: {e}")
            print(f"[TaskInferencer] Using fallback description")
            return self._fallback_description(actions, parameters)

    def _build_action_summary(self, actions: List[ActionSchema]) -> str:
        """
        Build human-readable summary of action sequence

        Args:
            actions: Actions to summarize

        Returns:
            Formatted action summary
        """
        summary_lines = []

        for i, action in enumerate(actions, 1):
            # Skip State-Tool actions (internal, not user-visible)
            if action.tool_name == "State-Tool":
                continue

            # Format action based on type
            if action.tool_name == "Click-Tool":
                loc = action.tool_arguments.get("loc", [])
                if isinstance(loc, list) and len(loc) > 0 and isinstance(loc[0], str):
                    # Symbolic reference
                    element = loc[0].split(":")[-1]  # Extract element text
                    summary_lines.append(f"{i}. Click on '{element}'")
                else:
                    summary_lines.append(f"{i}. Click at coordinates")

            elif action.tool_name == "Type-Tool":
                text = action.tool_arguments.get("text", "")
                # Truncate long text
                display_text = text if len(text) < 50 else text[:47] + "..."
                summary_lines.append(f"{i}. Type: {display_text}")

            elif action.tool_name == "Shortcut-Tool":
                shortcut = action.tool_arguments.get("shortcut", [])
                shortcut_str = "+".join(shortcut) if isinstance(shortcut, list) else str(shortcut)
                summary_lines.append(f"{i}. Press {shortcut_str}")

            elif action.tool_name == "Key-Tool":
                key = action.tool_arguments.get("key", "")
                summary_lines.append(f"{i}. Press {key}")

            elif action.tool_name == "Wait-Tool":
                duration = action.tool_arguments.get("duration", 0)
                summary_lines.append(f"{i}. Wait {duration}s")

            else:
                summary_lines.append(f"{i}. {action.tool_name}")

        return "\n".join(summary_lines)

    def _create_inference_prompt(
        self,
        action_summary: str,
        parameters: Dict[str, str]
    ) -> str:
        """
        Create prompt for LLM task inference

        Args:
            action_summary: Summary of actions
            parameters: Extracted parameters

        Returns:
            Prompt string
        """
        prompt = f"""Analyze this GUI automation workflow and describe the task in ONE concise sentence.

ACTIONS PERFORMED:
{action_summary}

PARAMETERS:
{json.dumps(parameters, indent=2)}

Requirements for task description:
1. Describe the HIGH-LEVEL GOAL (not low-level UI clicks)
2. Use parameter names in curly braces where applicable (e.g., {{input_folder}}, {{output_filename}})
3. Make it reusable across different parameter values
4. Keep it under 20 words
5. Focus on WHAT is accomplished, not HOW

Examples of good task descriptions:
- "Concatenate all .MF4 files in {{input_folder}} and save as {{output_filename}}"
- "Export signals from {{input_file}} to CSV format in {{output_folder}}"
- "Plot first signal from {{mf4_file}} and save visualization as {{output_image}}"

TASK DESCRIPTION:"""

        return prompt

    def _fallback_description(
        self,
        actions: List[ActionSchema],
        parameters: Dict[str, str]
    ) -> str:
        """
        Generate basic task description without LLM

        Used as fallback if LLM call fails

        Args:
            actions: Action sequence
            parameters: Parameters

        Returns:
            Basic task description
        """
        # Count action types
        click_count = sum(1 for a in actions if a.tool_name == "Click-Tool")
        type_count = sum(1 for a in actions if a.tool_name == "Type-Tool")

        # Extract key actions
        key_verbs = []
        for action in actions:
            reasoning = action.reasoning.lower()
            if "open" in reasoning:
                key_verbs.append("open")
            elif "save" in reasoning or "export" in reasoning:
                key_verbs.append("save")
            elif "concatenate" in reasoning or "merge" in reasoning:
                key_verbs.append("concatenate")
            elif "plot" in reasoning:
                key_verbs.append("plot")

        # Build basic description
        if "concatenate" in key_verbs:
            return f"Concatenate files using demonstrated workflow (Parameters: {', '.join(parameters.keys())})"
        elif "plot" in key_verbs:
            return f"Plot and visualize data using demonstrated workflow (Parameters: {', '.join(parameters.keys())})"
        elif "save" in key_verbs or "export" in key_verbs:
            return f"Process and save data using demonstrated workflow (Parameters: {', '.join(parameters.keys())})"
        else:
            return f"Perform GUI workflow with {click_count} clicks and {type_count} inputs (Parameters: {', '.join(parameters.keys())})"
