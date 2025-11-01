"""
Human Observer for Interactive HITL Workflows

Provides:
- Task verification at completion
- Step feedback collection (ESC key interrupt)
- KB learning attachment
"""

import sys
from typing import Dict, Any, Optional
import json

sys.path.insert(0, "D:\\Work\\asammdf_agent")

from agent.feedback.schemas import (
    TaskVerification,
    VerificationStatus
)
from agent.planning.schemas import ActionSchema


class HumanObserver:
    """
    Interactive human observer for HITL workflows

    Features:
    - Task completion verification
    - Step-by-step feedback collection (ESC key interrupt)
    - KB learning attachment
    """

    def __init__(
        self,
        session_id: str,
        knowledge_retriever: Optional[Any] = None
    ):
        """
        Initialize human observer

        Args:
            session_id: Session identifier
            knowledge_retriever: Knowledge retriever instance for updating vector metadata
        """
        self.session_id = session_id
        self.knowledge_retriever = knowledge_retriever
        self.running = False

        print(f"[Observer] Initialized for session: {session_id}")

    def start(self):
        """Start observer (placeholder for future background tasks)"""
        if self.running:
            print("[Observer] Already running")
            return
        self.running = True
        print("[Observer] Started")

    def stop(self):
        """Stop observer"""
        self.running = False
        print("[Observer] Stopped")

    def request_verification(
        self,
        task: str,
        execution_summary: Dict[str, Any]
    ) -> TaskVerification:
        """
        Request human verification of task completion

        Args:
            task: Original task description
            execution_summary: Summary of execution

        Returns:
            Task verification result
        """
        print("\n" + "="*70)
        print("  TASK COMPLETION VERIFICATION")
        print("="*70)
        print(f"Task: {task}")
        print(f"\nExecution Summary:")
        print(f"  Steps Executed: {execution_summary.get('steps_completed', 0)}")
        print(f"  Human Interventions: {execution_summary.get('human_feedbacks', 0)}")
        print(f"  Agent Self-Recoveries: {execution_summary.get('agent_recoveries', 0)}")
        print("\n" + "-"*70)
        print("Did the task complete successfully?")
        print("  [1] Yes - Completed successfully")
        print("  [2] No - Not completed")
        print("  [3] Partial - Some steps worked, some failed")
        print("-"*70)

        choice = input("\nYour choice [1-3]: ").strip()

        if choice == "1":
            # Completed
            reasoning = input("Optional: Why was it successful? ").strip() or "Task verified as completed"

            create_skill_choice = input("\nSave as verified skill for reuse? [y/n]: ").strip().lower()
            create_skill = create_skill_choice == "y"

            verification = TaskVerification(
                session_id=self.session_id,
                status=VerificationStatus.COMPLETED,
                reasoning=reasoning,
                create_skill=create_skill
            )

            print(f"\n[Verified] Task completed successfully")
            if create_skill:
                print("[Skill] Will be saved as verified skill for future reuse")

        elif choice == "2":
            # Not completed
            reasoning = input("Why did it fail? ").strip()

            verification = TaskVerification(
                session_id=self.session_id,
                status=VerificationStatus.NOT_COMPLETED,
                reasoning=reasoning,
                create_skill=False
            )

            print(f"\n[Not Completed] {reasoning}")
            print("[Retry] Will retry with accumulated feedback")

        else:
            # Partial
            reasoning = input("What worked and what didn't? ").strip()

            # Get step numbers
            successful_input = input("Successful step numbers (comma-separated): ").strip()
            failed_input = input("Failed step numbers (comma-separated): ").strip()

            successful_steps = [int(s.strip()) for s in successful_input.split(",") if s.strip().isdigit()]
            failed_steps = [int(s.strip()) for s in failed_input.split(",") if s.strip().isdigit()]

            verification = TaskVerification(
                session_id=self.session_id,
                status=VerificationStatus.PARTIALLY_COMPLETED,
                reasoning=reasoning,
                successful_steps=successful_steps,
                failed_steps=failed_steps,
                create_skill=False
            )

            print(f"\n[Partial] Will retry failed steps with feedback")

        print("="*70 + "\n")

        return verification

    def provide_step_feedback(
        self,
        task: str,
        plan_filepath: str
    ) -> Optional[Dict[str, Any]]:
        """
        Allow human to provide feedback for any completed step

        Minimal input required:
        1. Step number
        2. Error observed
        3. Optional suggestion

        System automatically:
        - Loads the plan
        - Finds the action at that step
        - Extracts kb_source
        - Creates FailureLearning
        - Attaches to KB catalog

        Args:
            task: Current task description
            plan_filepath: Path to the plan file

        Returns:
            Dict with feedback info, or None if cancelled
        """
        print("\n" + "="*80)
        print("  PROVIDE FEEDBACK FOR A SPECIFIC STEP")
        print("="*80)

        # Step 1: Get step number
        step_input = input("\nWhich step number do you want to provide feedback for? (or 'cancel'): ").strip()

        if step_input.lower() == 'cancel':
            print("[Cancelled] No feedback provided\n")
            return None

        try:
            step_num = int(step_input)
        except ValueError:
            print(f"[Error] Invalid step number: {step_input}")
            return None

        # Step 2: Load plan to get action details
        import json
        import os
        from agent.feedback.schemas import FailureLearning

        if not os.path.exists(plan_filepath):
            print(f"[Error] Plan file not found: {plan_filepath}")
            return None

        try:
            with open(plan_filepath, 'r', encoding='utf-8') as f:
                plan_data = json.load(f)
        except Exception as e:
            print(f"[Error] Could not load plan: {e}")
            return None

        # Find the action at step_num (1-indexed in display, but plan array is 0-indexed)
        plan_actions = plan_data.get("plan", {}).get("plan", [])
        step_index = step_num - 1

        if step_index < 0 or step_index >= len(plan_actions):
            print(f"[Error] Step {step_num} not found in plan (plan has {len(plan_actions)} steps)")
            return None

        action = plan_actions[step_index]
        kb_source = action.get("kb_source")

        # Show action details
        print(f"\n📋 Step {step_num} Details:")
        print(f"   Tool: {action.get('tool_name')}")
        print(f"   Arguments: {action.get('tool_arguments')}")
        print(f"   Reasoning: {action.get('reasoning')}")
        if kb_source:
            print(f"   KB Source: {kb_source}")
        else:
            print(f"   KB Source: None (action not from KB)")

        # Step 3: Get error description
        print("\n" + "-"*80)
        error_description = input("What error did you observe? ").strip()

        if not error_description:
            print("[Cancelled] Error description required")
            return None

        # Step 4: Get optional suggestion
        suggestion = input("Any suggestions for alternative approach? (press Enter to skip): ").strip()

        # Combine error and suggestion
        full_error = error_description
        if suggestion:
            full_error += f" | Suggestion: {suggestion}"

        # Step 5: Create FailureLearning
        learning = FailureLearning(
            task=task,
            step_num=step_num,
            original_action=action,
            original_error=full_error
        )

        print(f"\n✓ Feedback recorded for step {step_num}")

        # Step 6: Attach to KB if kb_source exists
        if kb_source:
            self._attach_feedback_to_kb(kb_source, learning)
            print(f"✓ Feedback attached to KB item: {kb_source}")
        else:
            print(f"⚠️  No KB source for this action - feedback not attached to KB")
            print(f"   (This action was not derived from knowledge base)")

        print("="*80 + "\n")

        return {
            "step_num": step_num,
            "kb_source": kb_source,
            "error": full_error,
            "learning": learning.model_dump()
        }

    def _attach_feedback_to_kb(self, kb_id: str, learning: 'FailureLearning'):
        """
        Attach human feedback learning to KB catalog

        Args:
            kb_id: Knowledge base item ID
            learning: FailureLearning object
        """
        catalog_path = "agent/knowledge_base/parsed_knowledge/knowledge_catalog.json"

        try:
            # Load catalog
            with open(catalog_path, 'r', encoding='utf-8') as f:
                catalog_data = json.load(f)

            # Find KB item and attach learning
            kb_found = False
            for item in catalog_data:
                if item.get("knowledge_id") == kb_id:
                    # Initialize kb_learnings if doesn't exist
                    if "kb_learnings" not in item:
                        item["kb_learnings"] = []

                    # Append learning as dict
                    item["kb_learnings"].append(learning.model_dump())

                    # Update trust score (decrease with each failure)
                    current_trust = item.get("trust_score", 1.0)
                    item["trust_score"] = max(0.5, current_trust * 0.95)

                    kb_found = True
                    print(f"  [KB] Updated '{kb_id}': {len(item['kb_learnings'])} learnings, trust={item['trust_score']:.2f}")
                    break

            if not kb_found:
                print(f"  [Warning] KB item '{kb_id}' not found in catalog")
                return

            # Save updated catalog
            with open(catalog_path, 'w', encoding='utf-8') as f:
                json.dump(catalog_data, f, indent=2, ensure_ascii=False)

            print(f"  [KB] Catalog updated with human feedback")

            # Update vector metadata for this KB item (reloads from catalog)
            if self.knowledge_retriever:
                try:
                    self.knowledge_retriever.update_vector_metadata(kb_id=kb_id)
                    print(f"  [KB Vector] Updated metadata from catalog for: {kb_id}")
                except Exception as e:
                    print(f"  [Warning] Could not update vector metadata: {e}")

        except Exception as e:
            print(f"  [Error] Failed to attach feedback to KB: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    """Test human observer"""

    print("Testing Human Observer\n")

    # Initialize
    observer = HumanObserver(session_id="test_session")
    observer.start()

    # Test: Request verification
    print("Test: Request Verification\n")
    verification = observer.request_verification(
        task="Concatenate MF4 files",
        execution_summary={
            "steps_completed": 25,
            "human_feedbacks": 2,
            "agent_recoveries": 1
        }
    )

    print(f"Verification: {verification.status}")
    print(f"Create skill: {verification.create_skill}")

    # Stop observer
    observer.stop()

    print("\n[SUCCESS] Human observer tests completed!")
