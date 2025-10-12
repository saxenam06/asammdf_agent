"""
Plan Recovery and Replanning System

Handles plan execution tracking, failure recovery, and adaptive replanning
by maintaining execution state directly in plan JSON files.
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from openai import OpenAI
from dotenv import load_dotenv

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from agent.planning.schemas import ActionSchema, PlanSchema, ExecutionResult

load_dotenv()

PLANS_DIR = os.path.join(os.path.dirname(__file__), "..", "plans")


class PlanRecoveryManager:
    """
    Manages plan execution state, failure recovery, and replanning
    """

    def __init__(self, plan_filepath: str, knowledge_retriever=None, api_key: Optional[str] = None):
        """
        Initialize plan recovery manager

        Args:
            plan_filepath: Path to the plan JSON file (tracks on same file)
            knowledge_retriever: KnowledgeRetriever instance for KB queries
            api_key: OpenAI API key for replanning
        """
        self.plan_filepath = plan_filepath
        self.knowledge_retriever = knowledge_retriever
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY required for replanning")

        self.client = OpenAI(api_key=self.api_key, timeout=120.0)
        self.model = "gpt-5-mini"

        # Load plan data
        self.plan_data = self._load_plan()
        self.original_task = self.plan_data.get("task", "")
        self.plan = PlanSchema(**self.plan_data["plan"])

        # Load or initialize execution state (stored in same file)
        if "execution_state" not in self.plan_data:
            self.plan_data["execution_state"] = {
                "current_step": 0,
                "overall_status": "in_progress",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "steps": []
            }

        self.execution_state = self.plan_data["execution_state"]

    def _load_plan(self) -> dict:
        """Load plan from JSON file"""
        with open(self.plan_filepath, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _save_plan(self):
        """Save plan data back to JSON file (with execution state)"""
        self.plan_data["updated_at"] = datetime.now().isoformat()
        self.execution_state["updated_at"] = datetime.now().isoformat()
        self.plan_data["execution_state"] = self.execution_state
        with open(self.plan_filepath, 'w', encoding='utf-8') as f:
            json.dump(self.plan_data, f, indent=2)


    def mark_step_completed(self, step_number: int, result: ExecutionResult):
        """
        Mark a step as completed

        Args:
            step_number: Step number (0-indexed)
            result: Execution result
        """
        # Update or add step status
        step_status = {
            "step": step_number,
            "status": "completed",
            "timestamp": datetime.now().isoformat(),
            "evidence": result.evidence[:500] if result.evidence else None  # Truncate long evidence
        }

        # Update existing or append new
        existing = [s for s in self.execution_state["steps"] if s["step"] == step_number]
        if existing:
            self.execution_state["steps"] = [s if s["step"] != step_number else step_status for s in self.execution_state["steps"]]
        else:
            self.execution_state["steps"].append(step_status)

        self.execution_state["current_step"] = step_number + 1

        self._save_plan()

    def mark_step_failed(self, step_number: int, result: ExecutionResult):
        """
        Mark a step as failed

        Args:
            step_number: Step number (0-indexed)
            result: Execution result with error
        """
        step_status = {
            "step": step_number,
            "status": "failed",
            "timestamp": datetime.now().isoformat(),
            "error": result.error
        }

        # Update existing or append new
        existing = [s for s in self.execution_state["steps"] if s["step"] == step_number]
        if existing:
            self.execution_state["steps"] = [s if s["step"] != step_number else step_status for s in self.execution_state["steps"]]
        else:
            self.execution_state["steps"].append(step_status)

        self.execution_state["overall_status"] = "failed"

        self._save_plan()

    def get_execution_summary(self) -> Dict[str, Any]:
        """
        Generate execution summary: what's completed, what failed, what's pending

        Returns:
            Dictionary with summary information
        """
        steps = self.execution_state.get("steps", [])

        completed_steps = [s for s in steps if s["status"] == "completed"]
        failed_steps = [s for s in steps if s["status"] == "failed"]

        total_steps = len(self.plan.plan)
        completed_count = len(completed_steps)
        failed_count = len(failed_steps)
        pending_count = total_steps - completed_count

        # Get the actual actions
        completed_actions = [self.plan.plan[s["step"]] for s in completed_steps]
        failed_actions = [self.plan.plan[s["step"]] for s in failed_steps if s["step"] < total_steps]

        # Determine what part of the goal is pending
        # Pending actions start from the failed step (not after it)
        if failed_steps:
            pending_start = failed_steps[0]["step"]
        else:
            pending_start = self.execution_state.get("current_step", 0)
        pending_actions = self.plan.plan[pending_start:] if pending_start < total_steps else []

        summary = {
            "total_steps": total_steps,
            "completed_count": completed_count,
            "failed_count": failed_count,
            "pending_count": len(pending_actions),  # Recalculate based on actual pending actions
            "completed_steps": completed_steps,
            "failed_steps": failed_steps,
            "completed_actions": [a.model_dump() for a in completed_actions],
            "failed_actions": [a.model_dump() for a in failed_actions],
            "pending_actions": [a.model_dump() for a in pending_actions],
            "last_completed_step": completed_steps[-1]["step"] if completed_steps else -1,
            "first_failed_step": failed_steps[0]["step"] if failed_steps else None
        }

        return summary

    def summarize_progress(self) -> Tuple[str, str, str]:
        """
        Generate human-readable summaries of progress

        Returns:
            Tuple of (completed_summary, failed_summary, remaining_goal)
        """
        summary = self.get_execution_summary()

        # Completed part summary
        completed_actions = summary["completed_actions"]
        if completed_actions:
            completed_summary = f"Successfully completed {len(completed_actions)} steps:\n"
            for i, action in enumerate(completed_actions, 1):  # Show first 5
                completed_summary += f"  {i}. {action['tool_name']}: {action['reasoning']}\n"
        else:
            completed_summary = "No steps completed yet."

        # Failed part summary
        failed_actions = summary["failed_actions"]
        failed_steps = summary["failed_steps"]
        if failed_actions:
            failed_summary = f"Failed at step {failed_steps[0]['step'] + 1}:\n"
            failed_summary += f"  Action: {failed_actions[0]['tool_name']}\n"
            failed_summary += f"  Reasoning: {failed_actions[0]['reasoning']}\n"
            failed_summary += f"  Error: {failed_steps[0]['error']}\n"
        else:
            failed_summary = "No failures."

        # Remaining goal
        pending_actions = summary["pending_actions"]
        first_failed_step = summary["first_failed_step"]

        if pending_actions:
            remaining_goal = f"Remaining objective ({len(pending_actions)} steps pending):\n"
            if first_failed_step is not None and pending_actions:
                # First pending action is the failed one
                remaining_goal += f"  RETRY from failed step {first_failed_step + 1}: {pending_actions[0]['tool_name']} - {pending_actions[0]['reasoning']}\n"
            else:
                remaining_goal += f"  Starting from: {pending_actions[0]['tool_name']} - {pending_actions[0]['reasoning']}\n"
            if len(pending_actions) > 1:
                remaining_goal += f"  Ending with: {pending_actions[-1]['tool_name']} - {pending_actions[-1]['reasoning']}\n"
        else:
            remaining_goal = "All steps attempted (need to retry failed steps)."

        return completed_summary, failed_summary, remaining_goal

    def retrieve_knowledge_for_failure(self, failed_action: ActionSchema, error: str) -> List[Dict[str, Any]]:
        """
        Query knowledge base for relevant context to solve the failed part

        Args:
            failed_action: The action that failed
            error: Error message

        Returns:
            List of relevant knowledge items
        """
        if not self.knowledge_retriever:
            print("  ! No knowledge retriever available")
            return []

        # Construct query based on failure context
        query = f"{failed_action.reasoning} {error}"

        print(f"\n🔍 Querying knowledge base for failure context:")
        print(f"  Query: {query}")

        try:
            results = self.knowledge_retriever.retrieve(query, top_k=3)
            kb_items = []
            for result in results:
                kb_items.append({
                    "knowledge_id": result.knowledge_id,
                    "description": result.description,
                    "ui_location": result.ui_location,
                    "action_sequence": result.action_sequence,
                    "prerequisites": result.prerequisites
                })
                print(f"  ✓ Retrieved: {result.knowledge_id}")
            return kb_items
        except Exception as e:
            print(f"  ✗ KB query failed: {e}")
            return []

    def generate_recovery_plan(
        self,
        mcp_tools_description: str,
        valid_tool_names: List[str],
        completed_summary: Optional[str] = None,
        failed_summary: Optional[str] = None,
        remaining_goal: Optional[str] = None,
        latest_state: Optional[str] = None
    ) -> PlanSchema:
        """
        Generate a new plan to achieve the remaining goal using KB context and latest UI state

        Args:
            mcp_tools_description: Description of available MCP tools
            valid_tool_names: List of valid MCP tool names
            completed_summary: Pre-computed completed summary (optional, will compute if None)
            failed_summary: Pre-computed failed summary (optional, will compute if None)
            remaining_goal: Pre-computed remaining goal (optional, will compute if None)
            latest_state: Latest UI state from State-Tool (optional)

        Returns:
            New plan for the unsolved part
        """
        print("\n🔄 Generating recovery plan...")

        # Use provided summaries or compute them
        if completed_summary is None or failed_summary is None or remaining_goal is None:
            completed_summary, failed_summary, remaining_goal = self.summarize_progress()

        summary = self.get_execution_summary()

        # Retrieve KB knowledge for failed action
        kb_context = []
        if summary["failed_actions"]:
            failed_action = ActionSchema(**summary["failed_actions"][0])
            failed_error = summary["failed_steps"][0]["error"]
            kb_context = self.retrieve_knowledge_for_failure(failed_action, failed_error)

        # Build KB section with knowledge retrieved specifically to address the failure
        kb_section = ""
        if kb_context:
            kb_section = f"""

KNOWLEDGE BASE CONTEXT (Retrieved to address the failure):
{json.dumps(kb_context, indent=2)}

The above knowledge provides guidance on how to properly handle the failed action."""

        # Build latest UI state section
        state_section = ""
        if latest_state:
            # Truncate if too long to avoid token overflow
            state_display = latest_state
            state_section = f"""

CURRENT UI STATE (Captured just before failure):
```
{state_display}
```

This is the ACTUAL current state of the application. Use this to understand:
- What UI elements are currently visible and available
- What the application state is after the completed steps
- What alternative paths or elements might be available to achieve the goal
- Why the original approach failed (missing elements, wrong state, etc.)"""
        else:
            state_section = """

CURRENT UI STATE: Not available (recommend adding State-Tool as first step of recovery plan)"""

        # Get pending actions for context
        pending_actions = summary["pending_actions"]
        pending_plan_section = ""
        if len(pending_actions) > 1:
            # Format pending actions (excluding the failed one)
            pending_steps_formatted = []
            for i, action in enumerate(pending_actions[1:], 1):  # Skip first (failed) action
                pending_steps_formatted.append(f"  {i}. {action['tool_name']}: {action['reasoning']}")

            if pending_steps_formatted:
                pending_plan_section = f"""

ORIGINAL PENDING PLAN (Steps that were planned but not yet executed):
{chr(10).join(pending_steps_formatted)}

NOTE: Evaluate if these pending steps are still valid. If they make sense for achieving the goal,
you can reuse or adapt them in your recovery plan. Do NOT discard the entire pending plan blindly -
merge what works with new steps to address the failure."""

        prompt = rf"""You are an expert recovery planner for a failed GUI automation workflow.

═══════════════════════════════════════════════════════════════════════════════
SECTION 1: TASK CONTEXT
═══════════════════════════════════════════════════════════════════════════════

ORIGINAL TASK:
{self.original_task}

EXECUTION PROGRESS:
{completed_summary}

FAILURE POINT:
{failed_summary}

REMAINING OBJECTIVE:
{remaining_goal}
{pending_plan_section}

═══════════════════════════════════════════════════════════════════════════════
SECTION 2: CURRENT REALITY (What's Actually Available)
═══════════════════════════════════════════════════════════════════════════════
{state_section}

═══════════════════════════════════════════════════════════════════════════════
SECTION 3: KNOWLEDGE BASE GUIDANCE
═══════════════════════════════════════════════════════════════════════════════
{kb_section}

═══════════════════════════════════════════════════════════════════════════════
SECTION 4: AVAILABLE MCP TOOLS
═══════════════════════════════════════════════════════════════════════════════
{mcp_tools_description}

Valid tool names: {', '.join(valid_tool_names)}

═══════════════════════════════════════════════════════════════════════════════
SECTION 5: ROOT CAUSE ANALYSIS
═══════════════════════════════════════════════════════════════════════════════

UNDERSTAND THE FAILURE:
The original plan likely ASSUMED certain UI elements would be present, but the failure
indicates these assumptions were WRONG. You must:

1. ANALYZE ASSUMPTIONS vs REALITY
   → What elements did the original plan assume existed?
   → What elements are ACTUALLY visible in the current UI state?
   → What's the gap between assumption and reality?

2. IDENTIFY THE INTENT
   → What was the original plan trying to ACCOMPLISH (not just execute)?
   → What is the END GOAL the user wants to achieve?
   → Why did the user want to perform the failed action?

3. MAP INTENT TO ACTUAL ELEMENTS
   → Which ACTUAL visible elements can achieve the same intent?
   → Are there alternative controls/menus/buttons serving the same purpose?
   → Is there a different navigation path using real elements?

4. LEVERAGE KNOWLEDGE BASE
   → What does the KB say about the CORRECT way to achieve this goal?
   → Are there proven workflows or element names documented?
   → What patterns should you follow?

5. EVALUATE PENDING PLAN
   → Which pending steps are still valid given ACTUAL element availability?
   → Which steps need modification to use real elements?
   → Which steps should be discarded because they reference non-existent elements?

═══════════════════════════════════════════════════════════════════════════════
SECTION 6: RECOVERY STRATEGY
═══════════════════════════════════════════════════════════════════════════════

APPROACH:
Follow this systematic process to generate your recovery plan:

Step 1: VERIFY CURRENT STATE
→ If UI state is not available or unclear, start with State-Tool
→ Ensure you understand what's ACTUALLY on screen right now

Step 2: FIND ALTERNATIVE PATH
→ Given the intent and actual available elements, determine alternative approach
→ Use KB guidance to identify correct element names and workflows
→ Map each intended action to actual UI elements

Step 3: ADAPT PENDING PLAN
→ Review each pending step from original plan
→ Keep steps that reference actual existing elements
→ Modify steps that need different elements
→ Discard steps that are no longer relevant

Step 4: GENERATE RECOVERY PLAN
→ Create new step sequence using ONLY actual visible elements
→ Reference elements as: ["last_state:element_type:element_name"]
→ Call State-Tool before interacting with new UI sections
→ Include clear reasoning for each step explaining the adaptation

Step 5: VALIDATE PLAN
→ Ensure all element references point to ACTUAL visible elements
→ Verify the plan achieves the original INTENT
→ Confirm all steps use valid MCP tools

═══════════════════════════════════════════════════════════════════════════════
SECTION 7: ELEMENT REFERENCE RULES (CRITICAL)
═══════════════════════════════════════════════════════════════════════════════

ELEMENT REFERENCE FORMAT
   • Menus: ["last_state:menu:Mode"]
   • Buttons: ["last_state:button:Save"]
   • File name: ["last_state:edit:File name"]
   • Select Files: ["last_state:file name:data.MF4"]
   • Wildcards: ["last_state:file name:*.MF4"] for any matching file

PATH FORMATTING (CRITICAL FOR WINDOWS):
   • ALWAYS use single backslash (\) in Windows paths
   • Example: C:\Users\ADMIN\Downloads\file.mf4
   • NEVER use double backslashes (\\) - this will cause GUI typing errors
   • When specifying paths in Type-Tool arguments, use exactly ONE backslash between path components

EXAMPLES:
• Menus: ["last_state:menu:Mode"]
• Buttons: ["last_state:button:Save"]
• Wildcards: ["last_state:file name:*.MF4"]
• Edit File name: ["last_state:edit:File name"]
• Select Files: ["last_state:file name:data.MF4"]

WORKFLOW:
1. Call State-Tool to discover elements
2. Reference discovered elements as "last_state:..."
3. If you need updated state later, call State-Tool again
4. Continue using "last_state:..." for newest elements

═══════════════════════════════════════════════════════════════════════════════
SECTION 8: CRITICAL REQUIREMENTS
═══════════════════════════════════════════════════════════════════════════════

✓ DO:
• Base ALL decisions on ACTUAL current UI state
• Use ONLY elements you can SEE in the state output
• Find ALTERNATIVE paths when original assumptions fail
• Follow KB guidance for correct workflows
• Reuse valid pending steps where appropriate
• Include clear reasoning explaining your adaptations
• Focus on achieving the INTENT, not replicating failed approach

✗ DON'T:
• Assume any elements exist without verification
• Hardcode coordinates - use State-Tool discovery
• Repeat completed steps
• Blindly copy the original failed approach
• Use numbered state references (STATE_1, STATE_2, etc.)
• Ignore the current UI state
• Discard entire pending plan without evaluation

═══════════════════════════════════════════════════════════════════════════════
SECTION 9: REQUIRED OUTPUT FORMAT
═══════════════════════════════════════════════════════════════════════════════

Return ONLY valid JSON (no explanatory text outside JSON):

{{
  "plan": [
    {{
      "tool_name": "State-Tool",
      "tool_arguments": {{"use_vision": false}},
      "reasoning": "Verify current UI state and discover actual available elements"
    }},
    {{
      "tool_name": "Click-Tool",
      "tool_arguments": {{"loc": ["last_state:menu:File"], "button": "left", "clicks": 1}},
      "reasoning": "Open File menu (alternative to non-existent Mode menu) to achieve same intent"
    }},
    {{
        "tool_name": "Type-Tool",
        "tool_arguments": {{
          "text": "C:\Users\ADMIN\Downloads\output.mf4",
          "clear": true,
          "press_enter": false
        }},
        "reasoning": "Enter the full output path and filename"
      }},
    ... additional steps ...
  ],
  "reasoning": "DETAILED EXPLANATION REQUIRED:
1. ASSUMPTION vs REALITY: [What original plan assumed vs what actually exists]
2. INTENT: [What the failed action was trying to accomplish]
3. ALTERNATIVE SOLUTION: [What actual elements will achieve the same intent]
4. KB GUIDANCE: [How knowledge base informed the new approach]
5. PENDING PLAN ADAPTATION: [Which steps reused/modified/discarded and why]
6. SUCCESS RATIONALE: [Why this reality-based approach will work]",
  "estimated_duration": 45
}}

═══════════════════════════════════════════════════════════════════════════════
Now generate your recovery plan following this systematic approach.
═══════════════════════════════════════════════════════════════════════════════
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                max_completion_tokens=120000,
                timeout=600.0,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            content = response.choices[0].message.content.strip()

            # Parse JSON
            if content.startswith('{'):
                plan_data = json.loads(content)
            elif '```json' in content:
                json_start = content.find('```json') + 7
                json_end = content.find('```', json_start)
                plan_data = json.loads(content[json_start:json_end].strip())
            elif '```' in content:
                json_start = content.find('```') + 3
                json_end = content.find('```', json_start)
                plan_data = json.loads(content[json_start:json_end].strip())
            else:
                plan_data = json.loads(content)

            new_plan = PlanSchema(**plan_data)

            print(f"\n✅ Recovery plan generated:")
            print(f"  New steps: {len(new_plan.plan)}")
            print(f"  Reasoning: {new_plan.reasoning[:200]}...")

            return new_plan

        except Exception as e:
            print(f"  ✗ Error generating recovery plan: {e}")
            raise

    def merge_plans(self, recovery_plan: PlanSchema) -> tuple[PlanSchema, str]:
        """
        Merge completed steps with the new recovery plan and save to new incremental file

        Args:
            recovery_plan: New plan for remaining work

        Returns:
            Tuple of (merged_plan, new_filepath)
        """
        print("\n🔗 Merging completed steps with recovery plan...")

        summary = self.get_execution_summary()
        completed_actions = [ActionSchema(**a) for a in summary["completed_actions"]]

        # Create merged plan
        merged_actions = completed_actions + recovery_plan.plan

        merged_reasoning = (
            f"[RECOVERY PLAN]\n"
            f"Completed {len(completed_actions)} steps successfully.\n"
            f"Recovery reasoning: {recovery_plan.reasoning}\n"
            f"Total steps in merged plan: {len(merged_actions)}"
        )

        merged_plan = PlanSchema(
            plan=merged_actions,
            reasoning=merged_reasoning,
            estimated_duration=recovery_plan.estimated_duration
        )

        print(f"  ✓ Merged plan: {len(completed_actions)} completed + {len(recovery_plan.plan)} new = {len(merged_actions)} total")

        # Determine next plan number by parsing current filename
        base_name = os.path.basename(self.plan_filepath)
        base_dir = os.path.dirname(self.plan_filepath)

        # Extract plan number from filename: task_hash_Plan_0.json -> 0
        import re
        match = re.match(r'(.+_[a-f0-9]{8})_Plan_(\d+)\.json', base_name)
        if match:
            base_prefix = match.group(1)  # e.g., "task_hash"
            current_plan_num = int(match.group(2))
            next_plan_num = current_plan_num + 1
        else:
            # Fallback if filename doesn't match pattern
            print(f"  ⚠️  Warning: Could not parse plan number from filename: {base_name}")
            base_prefix = base_name.replace('.json', '')
            next_plan_num = 1

        # Create new plan filepath
        new_plan_filepath = os.path.join(base_dir, f"{base_prefix}_Plan_{next_plan_num}.json")

        print(f"  🔄 Creating Plan_{next_plan_num} (replan from Plan_{current_plan_num if match else '?'})")

        # Update plan data with merged plan
        self.plan_data["plan"] = merged_plan.model_dump()

        # Reset execution state for new plan
        self.plan_data["execution_state"] = {
            "current_step": 0,
            "overall_status": "in_progress",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "steps": [],
            "recovery_applied": datetime.now().isoformat(),
            "previous_plan": os.path.basename(self.plan_filepath)
        }

        # Save to new plan file
        with open(new_plan_filepath, 'w', encoding='utf-8') as f:
            json.dump(self.plan_data, f, indent=2)
        print(f"  💾 New plan saved: {os.path.basename(new_plan_filepath)}")

        # Update current filepath and reload
        self.plan_filepath = new_plan_filepath
        self.execution_state = self.plan_data["execution_state"]
        self.plan = merged_plan

        return merged_plan, new_plan_filepath


if __name__ == "__main__":
    """Test plan recovery"""

    # Example: simulate a failed plan
    test_plan_path = os.path.join(PLANS_DIR, "Concatenate_all_MF4_files_in_C__Users_ADMIN_Downlo_bad75d6c.json")

    if os.path.exists(test_plan_path):
        manager = PlanRecoveryManager(test_plan_path)

        # Simulate some completed steps
        print("\n=== Simulating Execution ===")
        for i in range(3):
            result = ExecutionResult(success=True, action=f"Step {i}", evidence=f"Completed step {i}")
            manager.mark_step_completed(i, result)
            print(f"  ✓ Step {i} completed")

        # Simulate a failure
        failed_result = ExecutionResult(
            success=False,
            action="Click-Tool",
            error="Element not found: STATE_3:menu:Mode"
        )
        manager.mark_step_failed(3, failed_result)
        print(f"  ✗ Step 3 failed")

        # Save snapshot
        manager.save_snapshot("test_failure")

        # Get summary
        print("\n=== Execution Summary ===")
        completed, failed, remaining = manager.summarize_progress()
        print(f"\nCompleted:\n{completed}")
        print(f"\nFailed:\n{failed}")
        print(f"\nRemaining:\n{remaining}")
    else:
        print(f"Test plan not found: {test_plan_path}")
