"""
Demonstration Workflow

Records human GUI demonstrations and converts them to verified skills.
Human provides operation + parameters upfront, then demonstrates the workflow.
"""

import json
import time
from typing import Dict, List, Optional
from datetime import datetime
from pynput import keyboard
import sys, os, asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from agent.recording.action_recorder import ActionRecorder
from agent.recording.action_normalizer import ActionNormalizer
from agent.learning.skill_library import SkillLibrary, VerifiedSkill, VerifiedSkillMetadata
from agent.planning.schemas import ActionSchema, PlanSchema


class DemonstrationWorkflow:
    """
    Main workflow for recording human demonstrations

    Flow:
    1. User provides operation + parameters
    2. User demonstrates workflow on GUI
    3. System records actions → normalizes → generates reasoning
    4. Creates verified skill (same format as LLM-generated)
    """

    def __init__(self, target_app: str = "asammdf"):
        """
        Initialize demonstration workflow

        Args:
            target_app: Target application to record
        """
        self.target_app = target_app
        self.skill_library = SkillLibrary()

    def record_demonstration(
        self,
        operation: str,
        parameters: Dict[str, str],
        generate_reasoning: bool = True
    ) -> VerifiedSkill:
        """
        Complete demonstration recording pipeline

        Args:
            operation: High-level operation description (e.g., "Concatenate all .MF4 files and save")
            parameters: Parameter dict (e.g., {"input_folder": "...", "output_filename": "..."})
            generate_reasoning: Whether to use LLM to generate step reasoning

        Returns:
            Created VerifiedSkill
        """
        print("\n" + "="*80)
        print("HUMAN DEMONSTRATION RECORDER")
        print("="*80)
        print(f"Target Application: {self.target_app}")
        print(f"\nOperation: {operation}")
        print(f"Parameters:")
        for param_name, param_value in parameters.items():
            display_value = param_value
            print(f"  - {param_name}: {display_value}")

        print("\n" + "-"*80)
        print("INSTRUCTIONS:")
        print("1. Click on asammdf GUI to start recording (first click begins recording)")
        print("2. Perform your workflow using the ACTUAL parameter values shown above")
        print("3. Press ESC when done")
        print("-"*80)

        # Phase 1: Record raw actions (no MCP calls during recording)
        print("\n[Phase 1] Starting recorder...")

        recorder = ActionRecorder(target_app=self.target_app)
        recorder.start_recording()

        # Wait for ESC key
        recording_complete = False
        def on_esc(key):
            nonlocal recording_complete
            if key == keyboard.Key.esc:
                recording_complete = True
                return False  # Stop listener

        with keyboard.Listener(on_press=on_esc) as listener:
            listener.join()

        recorded_actions = recorder.recorded_actions
        print(f"\n[Phase 1] ✓ Recorded {len(recorded_actions)} raw actions")

        # Phase 1.5: Enrich actions with UI state (after recording complete)
        print(f"\n[Phase 1.5] Enriching actions with UI state...")
        from agent.execution.mcp_client import MCPClient
        import asyncio

        async def enrich_actions():
            async with MCPClient() as client:
                enriched_actions = await recorder.enrich_with_ui_state(client, recorded_actions)
                return enriched_actions

        recorded_actions = asyncio.run(enrich_actions())
        print(f"[Phase 1.5] ✓ Enriched {len(recorded_actions)} actions with UI state")

        # Phase 2: Normalize to ActionSchema
        print(f"\n[Phase 2] Normalizing actions...")
        normalizer = ActionNormalizer()
        normalized_actions = normalizer.normalize(recorded_actions)
        print(f"[Phase 2] ✓ Normalized to {len(normalized_actions)} actions")

        # Phase 3: Replace concrete values with placeholders
        print(f"\n[Phase 3] Parameterizing actions...")
        parameterized_actions = self._parameterize_actions(
            normalized_actions,
            parameters
        )
        print(f"[Phase 3] ✓ Parameterized {len(parameterized_actions)} actions")

        # Phase 4: Generate reasoning for each step (optional)
        if generate_reasoning:
            print(f"\n[Phase 4] Generating step reasoning with LLM...")
            actions_with_reasoning = self._generate_step_reasoning(
                parameterized_actions,
                operation,
                parameters
            )
            print(f"[Phase 4] ✓ Generated reasoning for {len(actions_with_reasoning)} steps")
        else:
            actions_with_reasoning = parameterized_actions
            print(f"\n[Phase 4] Skipped reasoning generation")

        # Phase 5: Set kb_source to "human" for all actions
        final_actions = []
        for action in actions_with_reasoning:
            action_dict = action.model_dump()
            action_dict["kb_source"] = "human"  # Mark as human-demonstrated
            final_actions.append(ActionSchema(**action_dict))

        # Phase 6: Create verified skill
        print(f"\n[Phase 5] Creating verified skill...")
        skill = self._create_verified_skill(
            operation=operation,
            parameters=parameters,
            actions=final_actions
        )

        # Phase 7: Save skill
        skill_path = self.skill_library.save_skill(skill)
        print(f"[Phase 6] ✓ Verified skill saved: {skill_path}")

        print("\n" + "="*80)
        print("✓ DEMONSTRATION COMPLETE")
        print("="*80)
        print(f"Skill ID: {skill.skill_id}")
        print(f"Total Steps: {len(final_actions)}")
        print(f"Skill can now be used by autonomous workflow!")
        print("="*80 + "\n")

        return skill

    def _parameterize_actions(
        self,
        actions: List[ActionSchema],
        parameters: Dict[str, str]
    ) -> List[ActionSchema]:
        """
        Replace concrete parameter values with placeholders in actions

        Args:
            actions: Normalized actions with concrete values
            parameters: Parameter dict with actual values

        Returns:
            Actions with placeholders
        """
        parameterized = []

        for action in actions:
            # Only Type-Tool actions need parameterization
            if action.tool_name == "Type-Tool":
                text = action.tool_arguments.get("text", "")

                # Check if text matches any parameter value
                replaced_text = text
                for param_name, param_value in parameters.items():
                    if param_value in text:
                        # Replace actual value with placeholder
                        replaced_text = replaced_text.replace(param_value, f"{{{param_name}}}")

                # Create new action with placeholders
                if replaced_text != text:
                    parameterized_action = ActionSchema(
                        tool_name=action.tool_name,
                        tool_arguments={
                            **action.tool_arguments,
                            "text": replaced_text
                        },
                        reasoning=action.reasoning,
                        kb_source=action.kb_source
                    )
                    parameterized.append(parameterized_action)
                    print(f"  → Parameterized: {text[:50]}... → {replaced_text}")
                else:
                    parameterized.append(action)
            else:
                parameterized.append(action)

        return parameterized

    def _generate_step_reasoning(
        self,
        actions: List[ActionSchema],
        operation: str,
        parameters: Dict[str, str]
    ) -> List[ActionSchema]:
        """
        Use LLM to generate reasoning for each action step

        Args:
            actions: Parameterized actions
            operation: Overall operation description
            parameters: Parameter definitions

        Returns:
            Actions with LLM-generated reasoning
        """
        from openai import OpenAI
        from agent.utils.cost_tracker import track_api_call

        client = OpenAI()
        model = "gpt-4o-mini"

        # Build action summary
        action_summary = []
        for i, action in enumerate(actions, 1):
            if action.tool_name == "State-Tool":
                action_summary.append(f"{i}. Capture UI state")
            elif action.tool_name == "Click-Tool":
                loc = action.tool_arguments.get("loc", [])
                if isinstance(loc, list) and loc and isinstance(loc[0], str):
                    element = loc[0].split(":")[-1]
                    action_summary.append(f"{i}. Click {element}")
                else:
                    action_summary.append(f"{i}. Click at coordinates")
            elif action.tool_name == "Type-Tool":
                text = action.tool_arguments.get("text", "")
                action_summary.append(f"{i}. Type: {text}")
            elif action.tool_name == "Shortcut-Tool":
                shortcut = action.tool_arguments.get("shortcut", [])
                shortcut_str = "+".join(shortcut) if isinstance(shortcut, list) else str(shortcut)
                action_summary.append(f"{i}. Press {shortcut_str}")
            else:
                action_summary.append(f"{i}. {action.tool_name}")

        # Create prompt
        prompt = f"""You are analyzing a human-demonstrated GUI automation workflow.

OPERATION: {operation}

PARAMETERS:
{json.dumps(parameters, indent=2)}

DEMONSTRATED STEPS:
{chr(10).join(action_summary)}

For each step, provide a brief reasoning explaining WHY this step is necessary in the context of the overall operation.
Keep reasoning concise (1-2 sentences per step).
Reference parameters using {{placeholder}} syntax where applicable.

Respond with a JSON object:
{{
  "step_reasonings": [
    {{"step": 1, "reasoning": "Brief explanation..."}},
    {{"step": 2, "reasoning": "Brief explanation..."}},
    ...
  ]
}}
"""

        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2000,
                temperature=0.3,
                response_format={"type": "json_object"}
            )

            # Track cost
            usage = response.usage
            cost = track_api_call(
                model=model,
                component="demonstration_reasoning",
                input_tokens=usage.prompt_tokens,
                output_tokens=usage.completion_tokens,
                task_context=f"Generate reasoning for {len(actions)} steps"
            )
            print(f"  💰 Reasoning generation cost: ${cost:.6f} ({usage.prompt_tokens:,} in + {usage.completion_tokens:,} out tokens)")

            # Parse response
            result = json.loads(response.choices[0].message.content.strip())
            step_reasonings = {r["step"]: r["reasoning"] for r in result.get("step_reasonings", [])}

            # Apply reasoning to actions
            actions_with_reasoning = []
            for i, action in enumerate(actions, 1):
                if i in step_reasonings:
                    reasoning = step_reasonings[i]
                    action_dict = action.model_dump()
                    action_dict["reasoning"] = reasoning
                    actions_with_reasoning.append(ActionSchema(**action_dict))
                else:
                    actions_with_reasoning.append(action)

            return actions_with_reasoning

        except Exception as e:
            print(f"  [Warning] LLM reasoning generation failed: {e}")
            print(f"  [Warning] Using default reasoning from normalization")
            return actions

    def _create_verified_skill(
        self,
        operation: str,
        parameters: Dict[str, str],
        actions: List[ActionSchema]
    ) -> VerifiedSkill:
        """
        Create verified skill from demonstrated workflow

        Args:
            operation: Operation description
            parameters: Parameters used
            actions: Recorded and parameterized actions

        Returns:
            VerifiedSkill object
        """
        # Generate task description with parameters
        param_str = ", ".join([f"{k}={v}" for k, v in parameters.items()])
        task_description = f"{operation} (Parameters: {param_str})"

        # Create metadata
        metadata = VerifiedSkillMetadata(
            verified_by="human",
            verified_at=datetime.now().isoformat(),
            session_id=f"demo_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            human_feedbacks_count=0,
            agent_recoveries_count=0,
            times_used=0,
            success_count=0,
            success_rate=1.0,  # Assumed successful since human demonstrated
            source="human_demonstration"  # Mark source
        )

        # Create skill
        skill = VerifiedSkill(
            task_description=task_description,
            operation=operation,
            parameters=parameters,
            action_plan=actions,
            metadata=metadata,
            tags=["human_demonstrated"]
        )

        return skill


if __name__ == "__main__":
    """
    Record human demonstration as verified skill
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Record human GUI demonstration as verified skill",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Use default task
  python demonstration_workflow.py

  # Custom task with parameters
  python demonstration_workflow.py \\
    --operation "Concatenate all .MF4 files and save with specified name" \\
    --parameters '{"input_folder": "C:\\\\data", "output_folder": "C:\\\\output", "output_filename": "merged.mf4"}'
        """
    )
    parser.add_argument(
        "--operation",
        type=str,
        help="Operation description (e.g., 'Concatenate all .MF4 files and save')"
    )
    parser.add_argument(
        "--parameters",
        type=str,
        help='Parameters as JSON (e.g., \'{"input_folder": "C:\\\\...", "output_filename": "file.mf4"}\')'
    )
    parser.add_argument(
        "--app",
        type=str,
        default="asammdf",
        help="Target application (default: asammdf)"
    )
    parser.add_argument(
        "--no-reasoning",
        action="store_true",
        help="Skip LLM reasoning generation (faster, less context)"
    )

    args = parser.parse_args()

    # Parse parameters
    if args.operation and args.parameters:
        # User-provided operation and parameters
        operation = args.operation
        parameters = json.loads(args.parameters)
    elif args.operation or args.parameters:
        # Only one provided - error
        parser.error("--operation and --parameters must be provided together")
    else:
        # Use default task
        operation = "DBC Decode the concatenated MF4 file and Extract the bus signals. Export the decoded MF4 file to CSV after applying Single time base and Time as date settings."
        parameters = {
            "input_folder": r"C:\Users\ADMIN\Downloads\ev-data-pack-v10\ev-data-pack-v10\electric_cars\log_files\Kia EV6\LOG\2F6913DB\00001045",
            "output_folder": r"C:\Users\ADMIN\Downloads\ev-data-pack-v10\ev-data-pack-v10\electric_cars\log_files\Kia EV6\LOG\2F6913DB\00001045",
            "input_concatenated_filename": "Kia_EV_6_2F6913DB_00001045.MF4",
            "input_CAN_database_file": r"C:\Users\ADMIN\Downloads\ev-data-pack-v10\ev-data-pack-v10\electric_cars\log_files\Kia EV6\can2-canmod-gnss.dbc",
            "output_decoded_filename": "Kia_EV_6_2F6913DB_00001045_decoded.mf4",
            "output_csv_filename": "Kia_EV_6_2F6913DB_00001045.csv",
        }
        print(f"\n[Using Default Task]")

    # Create workflow and record
    workflow = DemonstrationWorkflow(target_app=args.app)

    skill = workflow.record_demonstration(
        operation=operation,
        parameters=parameters,
        generate_reasoning=not args.no_reasoning
    )

    print(f"\n✓ Skill created: {skill.skill_id}")
    print(f"  Location: agent/learning/verified_skills/")
    print(f"  Can now be used by: python agent/workflows/autonomous_workflow.py")
