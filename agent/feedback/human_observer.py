"""
Human Observer for Interactive HITL Workflows

Provides:
- Non-blocking observer thread for human interrupts
- Interactive CLI for approval/correction/guidance
- Task verification at completion
- Integration with communication protocol
"""

import threading
import queue
import sys
from typing import Dict, Any, Optional
from datetime import datetime
import json

sys.path.insert(0, "D:\\Work\\asammdf_agent")

from agent.feedback.communication_protocol import (
    CommunicationProtocol,
    RequestMessage,
    ResponseMessage,
    NotificationMessage
)
from agent.feedback.schemas import (
    HumanFeedback,
    TaskVerification,
    VerificationStatus,
    ConfidenceLevel,
    ProceduralGuidance
)
from agent.planning.schemas import ActionSchema


class HumanObserver:
    """
    Interactive human observer for HITL workflows

    Features:
    - Non-blocking observation (runs in background thread)
    - Keyboard interrupt support (Ctrl+C to interrupt)
    - Interactive approval/correction/guidance
    - Task completion verification
    """

    def __init__(
        self,
        session_id: str,
        protocol: Optional[CommunicationProtocol] = None,
        knowledge_retriever: Optional[Any] = None
    ):
        """
        Initialize human observer

        Args:
            session_id: Session identifier
            protocol: Communication protocol instance
            knowledge_retriever: Knowledge retriever instance for updating vector metadata
        """
        self.session_id = session_id
        self.protocol = protocol or CommunicationProtocol()
        self.knowledge_retriever = knowledge_retriever

        # State
        self.running = False
        self.paused = False
        self.current_action: Optional[ActionSchema] = None
        self.current_step: int = 0

        # Interrupt queue
        self.interrupt_queue: queue.Queue = queue.Queue()

        # Observer thread
        self.observer_thread: Optional[threading.Thread] = None

        print(f"[Observer] Initialized for session: {session_id}")

    def start(self):
        """Start non-blocking observer thread"""
        if self.running:
            print("[Observer] Already running")
            return

        self.running = True
        self.observer_thread = threading.Thread(
            target=self._observe_loop,
            daemon=True
        )
        self.observer_thread.start()
        print("[Observer] Started (Press Ctrl+C during execution to interrupt)")

    def stop(self):
        """Stop observer thread"""
        self.running = False
        if self.observer_thread:
            self.observer_thread.join(timeout=1.0)
        print("[Observer] Stopped")

    def _observe_loop(self):
        """Background observation loop (runs in separate thread)"""
        # Note: Keyboard interrupts are handled by main thread
        # This thread just manages state and queue
        while self.running:
            threading.Event().wait(0.1)  # Small sleep to avoid busy loop

    def set_current_action(self, action: ActionSchema, step_num: int):
        """
        Update current action being executed

        Args:
            action: Current action
            step_num: Step number
        """
        self.current_action = action
        self.current_step = step_num

    def has_interrupt(self) -> bool:
        """
        Check if human has interrupted

        Returns:
            True if interrupt pending
        """
        return not self.interrupt_queue.empty()

    def get_interrupt(self) -> NotificationMessage:
        """
        Get interrupt notification (blocking if none available)

        Returns:
            Interrupt notification
        """
        return self.interrupt_queue.get()

    def request_approval(
        self,
        action: ActionSchema,
        confidence: float,
        step_num: int,
        alternatives: Optional[list] = None
    ) -> HumanFeedback:
        """
        Request human approval for low-confidence action

        Args:
            action: Proposed action
            confidence: Agent's confidence (0.0-1.0)
            step_num: Step number
            alternatives: Alternative actions considered

        Returns:
            Human feedback
        """
        # Create request
        request = self.protocol.create_request(
            method="human.request_approval",
            params={
                "session_id": self.session_id,
                "step_num": step_num,
                "confidence": confidence,
                "proposed_action": action.model_dump(),
                "alternatives": alternatives or []
            }
        )

        print("\n" + "="*70)
        print(f"  HUMAN APPROVAL NEEDED (Step {step_num + 1})")
        print("="*70)
        print(f"Agent Confidence: {confidence:.2f} (LOW)")
        print(f"\nProposed Action:")
        print(f"  Tool: {action.tool_name}")
        print(f"  Arguments: {json.dumps(action.tool_arguments, indent=4)}")
        print(f"  Reasoning: {action.reasoning}")

        if alternatives:
            print(f"\nAlternatives Considered: {len(alternatives)}")

        print("\n" + "-"*70)
        print("Options:")
        print("  [1] Approve - Execute as proposed")
        print("  [2] Reject - Provide quick correction")
        print("  [3] Skip - Skip this step")
        print("  [4] Guidance - Provide general guidance")
        print("  [5] Detailed Procedure - Provide step-by-step instructions")
        print("-"*70)

        choice = input("\nYour choice [1-5]: ").strip()

        if choice == "1":
            # Approved
            feedback = HumanFeedback(
                session_id=self.session_id,
                approved=True,
                reasoning="Approved by human",
                original_action=action.model_dump(),
                agent_confidence=confidence
            )

            response = self.protocol.create_response(
                request_id=request.id,
                result={"approved": True, "feedback": feedback.model_dump()}
            )

            print("[Approved] Action will execute as proposed\n")

        elif choice == "2":
            # Rejected with correction
            print("\nProvide correction:")
            print("  Tool name (press Enter to keep same):", end=" ")
            tool_name = input().strip() or action.tool_name

            print("  Arguments (JSON, press Enter to skip):", end=" ")
            args_input = input().strip()
            if args_input:
                try:
                    tool_arguments = json.loads(args_input)
                except:
                    print("  [Warning] Invalid JSON, keeping original arguments")
                    tool_arguments = action.tool_arguments
            else:
                tool_arguments = action.tool_arguments

            reasoning = input("  Reasoning for correction: ").strip()

            corrected_action = ActionSchema(
                tool_name=tool_name,
                tool_arguments=tool_arguments,
                reasoning=reasoning or action.reasoning
            )

            feedback = HumanFeedback(
                session_id=self.session_id,
                approved=False,
                correction=corrected_action.model_dump(),
                reasoning=reasoning,
                original_action=action.model_dump(),
                agent_confidence=confidence
            )

            response = self.protocol.create_response(
                request_id=request.id,
                result={
                    "approved": False,
                    "correction": corrected_action.model_dump(),
                    "feedback": feedback.model_dump()
                }
            )

            print(f"[Corrected] Will execute: {tool_name}\n")

        elif choice == "3":
            # Skip step
            feedback = HumanFeedback(
                session_id=self.session_id,
                approved=False,
                correction={"type": "skip_step"},
                reasoning="Human requested skip",
                original_action=action.model_dump(),
                agent_confidence=confidence
            )

            response = self.protocol.create_response(
                request_id=request.id,
                result={
                    "approved": False,
                    "skip": True,
                    "feedback": feedback.model_dump()
                }
            )

            print("[Skipped] Step will be skipped\n")

        elif choice == "4":
            # Guidance
            guidance_text = input("\nProvide guidance for agent: ").strip()

            feedback = HumanFeedback(
                session_id=self.session_id,
                approved=True,  # Continue with original action
                reasoning=f"Guidance: {guidance_text}",
                original_action=action.model_dump(),
                agent_confidence=confidence
            )

            response = self.protocol.create_response(
                request_id=request.id,
                result={
                    "approved": True,
                    "guidance": guidance_text,
                    "feedback": feedback.model_dump()
                }
            )

            print(f"[Guided] Action will execute with guidance noted\n")

        else:
            # Detailed Procedural Guidance (Option 5)
            print("\n" + "="*70)
            print("  PROVIDE DETAILED PROCEDURAL GUIDANCE")
            print("="*70)
            print("Agent will learn the correct procedure for this type of task.")
            print("Be as specific as possible - this will help for similar tasks.\n")

            # Goal
            print("What is the goal of this procedure?")
            print("Example: 'Add files to concatenate list'")
            goal = input("Goal: ").strip()

            # Steps
            print("\nProvide step-by-step instructions (one per line).")
            print("Type 'DONE' when finished.\n")
            steps = []
            step_num = 1
            while True:
                step = input(f"Step {step_num}: ").strip()
                if step.upper() == "DONE":
                    break
                if step:
                    steps.append(step)
                    step_num += 1

            # Key points (optional)
            print("\nAny key points to remember? (comma-separated, or press Enter to skip)")
            key_points_input = input("Key points: ").strip()
            key_points = [kp.strip() for kp in key_points_input.split(",") if kp.strip()] if key_points_input else None

            # Mistakes to avoid (optional)
            print("\nCommon mistakes to avoid? (comma-separated, or press Enter to skip)")
            mistakes_input = input("Mistakes: ").strip()
            mistakes = [m.strip() for m in mistakes_input.split(",") if m.strip()] if mistakes_input else None

            # Alternatives (optional)
            print("\nAlternative ways to achieve the same goal? (comma-separated, or press Enter to skip)")
            alternatives_input = input("Alternatives: ").strip()
            alternatives_list = [a.strip() for a in alternatives_input.split(",") if a.strip()] if alternatives_input else None

            # Create procedural guidance
            procedural = ProceduralGuidance(
                goal=goal,
                steps=steps,
                key_points=key_points,
                mistakes_to_avoid=mistakes,
                alternatives=alternatives_list
            )

            feedback = HumanFeedback(
                session_id=self.session_id,
                approved=False,  # Don't execute proposed action, need to replan
                reasoning=f"Detailed procedure provided for: {goal}",
                original_action=action.model_dump(),
                agent_confidence=confidence,
                procedural_guidance=procedural
            )

            response = self.protocol.create_response(
                request_id=request.id,
                result={
                    "approved": False,
                    "procedural_guidance": procedural.model_dump(),
                    "feedback": feedback.model_dump()
                }
            )

            print("\n" + "="*70)
            print("  PROCEDURAL GUIDANCE CAPTURED")
            print("="*70)
            print(f"Goal: {goal}")
            print(f"Steps: {len(steps)}")
            if key_points:
                print(f"Key points: {len(key_points)}")
            if mistakes:
                print(f"Mistakes to avoid: {len(mistakes)}")
            print("\n[Stored] Agent will replan using this procedure")
            print("="*70 + "\n")

        return feedback

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

    def notify_interrupt_available(self):
        """Notify user that they can interrupt (called before each step)"""
        # This is just informational - actual interrupt happens via Ctrl+C
        pass


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

    # Test 1: Request approval
    print("Test 1: Request Approval\n")
    test_action = ActionSchema(
        tool_name="Click-Tool",
        tool_arguments={"loc": [450, 300], "button": "left", "clicks": 1},
        reasoning="Click the concatenate button"
    )

    feedback = observer.request_approval(
        action=test_action,
        confidence=0.35,
        step_num=5,
        alternatives=[
            {"tool_name": "Shortcut-Tool", "shortcut": ["ctrl", "m"]},
            {"tool_name": "State-Tool", "use_vision": False}
        ]
    )

    print(f"Feedback received: Approved={feedback.approved}")
    print(f"Reasoning: {feedback.reasoning}\n")

    # Test 2: Request verification
    print("\nTest 2: Request Verification\n")
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
