"""
Autonomous workflow orchestrator using LangGraph
"""
import sys, os, asyncio
from typing import TypedDict, Optional, List, Annotated
from langgraph.graph import StateGraph, END
import operator

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from agent.planning.schemas import KnowledgeSchema, PlanSchema, ExecutionResult, VerifiedSkillSchema, ActionSchema
from agent.knowledge_base.retriever import KnowledgeRetriever
from agent.planning.workflow_planner import WorkflowPlanner
from agent.execution.mcp_client import MCPClient
from agent.execution.adaptive_executor import AdaptiveExecutor
from agent.utils.cost_tracker import get_global_tracker

# HITL imports
try:
    from agent.feedback.human_observer import HumanObserver
    from agent.learning.skill_library import SkillLibrary
    from agent.feedback.schemas import VerificationStatus
    HITL_AVAILABLE = True
except ImportError:
    HITL_AVAILABLE = False
    print("[Warning] HITL components not available")


class WorkflowState(TypedDict):
    task: str
    retrieved_knowledge: List[KnowledgeSchema]
    verified_skills: List[VerifiedSkillSchema]
    plan: Optional[PlanSchema]
    current_step: int
    execution_log: Annotated[List[ExecutionResult], operator.add]
    error: Optional[str]
    completed: bool
    retry_count: int
    replan_count: int
    force_regenerate_plan: bool


class AutonomousWorkflow:
    """Orchestrates RAG → Planning → Execution → Recovery workflow"""

    def __init__(
        self,
        app_name: str = "asammdf 8.6.10",
        catalog_path: str = "agent/knowledge_base/parsed_knowledge/knowledge_catalog.json",
        vector_db_path: str = "agent/knowledge_base/vector_store",
        max_retries: int = 2,
        max_replan_attempts: int = 3,
        enable_hitl: bool = True,
        session_id: Optional[str] = None
    ):
        self.app_name = app_name
        self.max_retries = max_retries
        self.max_replan_attempts = max_replan_attempts
        self.catalog_path = catalog_path
        self.vector_db_path = vector_db_path
        self.task = None
        self._retriever = None
        self._planner = None
        self._graph = None
        self._client = None
        self._executor = None

        # HITL components
        self.enable_hitl = enable_hitl and HITL_AVAILABLE
        self.session_id = "session_fe2424ebd"
        self._human_observer = None
        self._skill_library = None

        if self.enable_hitl:
            print(f"[HITL] Enabled (session: {self.session_id})")
            self._skill_library = SkillLibrary()
            # Observer will be started in run() method
        else:
            print("[HITL] Disabled")

    @property
    def retriever(self):
        if self._retriever is None:
            self._retriever = KnowledgeRetriever(
                catalog_path=self.catalog_path,
                vector_db_path=self.vector_db_path
            )
        return self._retriever

    @property
    def planner(self):
        if self._planner is None:
            self._planner = WorkflowPlanner(
                mcp_client=self.client,
                skill_library=self._skill_library if self.enable_hitl else None,
                memory_manager=None,  # Removed - using KB-attached learnings instead
                session_id=self.session_id
            )
        return self._planner

    @property
    def graph(self):
        if self._graph is None:
            self._graph = self._build_graph()
        return self._graph

    @property
    def client(self):
        if self._client is None:
            raise RuntimeError("MCP client not initialized")
        return self._client

    @property
    def executor(self):
        if self._executor is None and self.task is not None:
            from agent.planning.workflow_planner import get_latest_plan_filepath
            plan_path = get_latest_plan_filepath(self.task)
            if plan_path:
                self._executor = AdaptiveExecutor(
                    self.client,
                    knowledge_retriever=self.retriever,
                    plan_filepath=plan_path,
                    human_observer=self._human_observer if self.enable_hitl else None,
                    memory_manager=None,  # Removed - using KB-attached learnings instead
                    session_id=self.session_id
                )
        return self._executor

    def _build_graph(self) -> StateGraph:
        workflow = StateGraph(WorkflowState)

        workflow.add_node("retrieve_knowledge", self._retrieve_knowledge_node)
        workflow.add_node("generate_plan", self._generate_plan_node)
        workflow.add_node("validate_plan", self._validate_plan_node)
        workflow.add_node("execute_step", self._execute_step_node)
        workflow.add_node("verify_step", self._verify_step_node)
        workflow.add_node("handle_error", self._handle_error_node)

        # HITL node for final verification
        if self.enable_hitl:
            workflow.add_node("final_verification", self._final_verification_node)

        workflow.set_entry_point("retrieve_knowledge")
        workflow.add_edge("retrieve_knowledge", "generate_plan")
        workflow.add_edge("generate_plan", "validate_plan")
        workflow.add_conditional_edges("validate_plan", self._route_after_validation, {"execute": "execute_step", "error": END})
        workflow.add_edge("execute_step", "verify_step")

        if self.enable_hitl:
            # Route to final_verification instead of END on completion
            workflow.add_conditional_edges("verify_step", self._route_after_verification, {"next_step": "execute_step", "error": "handle_error", "done": "final_verification"})
            workflow.add_edge("final_verification", END)
        else:
            workflow.add_conditional_edges("verify_step", self._route_after_verification, {"next_step": "execute_step", "error": "handle_error", "done": END})

        workflow.add_conditional_edges("handle_error", self._route_after_error, {"retry": "execute_step", "failed": END})

        return workflow.compile()
    def _retrieve_knowledge_node(self, state: WorkflowState) -> WorkflowState:
        print(f"\n[1/5] Retrieving knowledge for: '{state['task']}'")
        knowledge_patterns = self.retriever.retrieve(state["task"], top_k=5)
        print(f"  ✓ Retrieved {len(knowledge_patterns)} patterns")
        state["retrieved_knowledge"] = knowledge_patterns
        return state

    def _generate_plan_node(self, state: WorkflowState) -> WorkflowState:
        print(f"\n[2/5] Generating plan...")

        try:
            latest_state = None
            try:
                state_result = self.client.call_tool_sync('State-Tool', {'use_vision': False})
                if not state_result.isError:
                    latest_state = state_result.content[0].text if hasattr(state_result, 'content') else str(state_result)
            except:
                pass

            plan = self.planner.generate_plan(
                task=state["task"],
                available_knowledge=state["retrieved_knowledge"],
                force_regenerate=state.get("force_regenerate_plan", False),
                latest_state=latest_state
            )

            print(f"  ✓ Generated {len(plan.plan)} steps")
            state["plan"] = plan
            state["current_step"] = 0

            if self._executor is None:
                _ = self.executor

        except Exception as e:
            print(f"  ✗ Failed: {e}")
            state["error"] = f"Plan generation failed: {e}"

        return state

    def _validate_plan_node(self, state: WorkflowState) -> WorkflowState:
        print(f"\n[3/5] Validating plan...")

        if not state["plan"]:
            state["error"] = "No plan generated"
            print("  ✗ No plan")
            return state

        is_valid, error_msg = self.planner.validate_plan(state["plan"])
        print(f"  {'✓ Valid' if is_valid else '✗ Invalid: ' + error_msg}")

        if not is_valid:
            state["error"] = error_msg

        return state

    def _execute_step_node(self, state: WorkflowState) -> WorkflowState:
        step_num = state["current_step"]
        total_steps = len(state["plan"].plan) if state["plan"] else 0
        action = state["plan"].plan[step_num]

        print(f"\n[4/5] Executing step {step_num + 1}/{total_steps}: {action.tool_name}")
        sys.stdout.flush()

        context_actions = state["plan"].plan[:step_num]
        result = self.executor.execute_action(action, context=context_actions, step_num=step_num)

        if self.executor.recovery_manager:
            if result.success:
                self.executor.recovery_manager.mark_step_completed(step_num, result)
            elif result.action != "REPLAN_TRIGGERED":
                self.executor.recovery_manager.mark_step_failed(step_num, result)

        state["execution_log"] = [result]
        state["current_step"] += 1
        return state

    def _verify_step_node(self, state: WorkflowState) -> WorkflowState:
        print(f"\n[5/5] Verifying...")
        sys.stdout.flush()

        total_steps = len(state["plan"].plan) if state["plan"] else 0
        if state["current_step"] >= total_steps:
            print(f"  ✓ All {total_steps} steps completed!")
            state["completed"] = True
            state["error"] = None
            return state

        last_result = state["execution_log"][-1] if state["execution_log"] else None

        if last_result and not last_result.success:
            if last_result.action == "REPLAN_TRIGGERED":
                print(f"\n🔄 Replanning...")

                if self.executor.recovery_manager:
                    merged_plan = self.executor.recovery_manager.plan
                    state["plan"] = merged_plan

                    import re
                    match = re.search(r'Completed (\d+) steps', merged_plan.reasoning)
                    completed_count = int(match.group(1)) if match else 0
                    state["current_step"] = completed_count

                    print(f"  ✓ Merged plan: {len(merged_plan.plan)} steps, resume from {completed_count + 1}")

                    state["replan_count"] = state.get("replan_count", 0) + 1
                    if state["replan_count"] > self.max_replan_attempts:
                        state["error"] = f"Max replanning attempts reached"
                    else:
                        state["error"] = None
                        state["retry_count"] = 0
                else:
                    state["error"] = "No recovery manager"
            else:
                print(f"  ✗ Failed: {last_result.error}")
                state["error"] = last_result.error
        else:
            print(f"  ✓ Success")
            state["error"] = None

        return state

    def _handle_error_node(self, state: WorkflowState) -> WorkflowState:
        print(f"\n[Error] {state['error']}")
        state["retry_count"] = state.get("retry_count", 0) + 1

        if state["retry_count"] < self.max_retries:
            print(f"  → Retry {state['retry_count']}/{self.max_retries}")
            state["current_step"] = max(0, state["current_step"] - 1)
            state["error"] = None
        else:
            print(f"  → Max retries reached")

        return state

    def _final_verification_node(self, state: WorkflowState) -> WorkflowState:
        """HITL final verification and skill creation"""
        print(f"\n[HITL] Final Verification")

        if not self._human_observer:
            print("  [Warning] Observer not available, skipping verification")
            return state

        # Prepare execution summary
        execution_summary = {
            "steps_completed": state.get("current_step", 0),
            "human_feedbacks": 0,  # TODO: Track this in executor
            "agent_recoveries": state.get("replan_count", 0)
        }

        # Request human verification
        verification = self._human_observer.request_verification(
            task=state["task"],
            execution_summary=execution_summary
        )

        if verification.status == VerificationStatus.COMPLETED:
            print(f"  ✓ Human verified task completion")

            # Create verified skill if requested
            if verification.create_skill and self._skill_library and state.get("plan"):
                try:
                    skill_id = self._skill_library.add_skill(
                        task=state["task"],
                        plan=state["plan"].model_dump(),
                        success_rate=1.0,
                        metadata={
                            "session_id": self.session_id,
                            "human_verified": True,
                            "verification_reasoning": verification.reasoning,
                            "steps_completed": state.get("current_step", 0)
                        }
                    )
                    print(f"  [HITL] Created verified skill: {skill_id}")
                except Exception as e:
                    print(f"  [Warning] Failed to create skill: {e}")

            # Verification feedback (no longer stored in Mem0, using KB-attached learnings instead)
            print(f"  [HITL] Verification complete: {verification.reasoning}")
        else:
            print(f"  ✗ Verification status: {verification.status}")
            print(f"     Reason: {verification.reasoning}")
            if verification.status == VerificationStatus.NOT_COMPLETED:
                state["completed"] = False
                state["error"] = f"Human verification: {verification.reasoning}"

        return state

    def _route_after_validation(self, state: WorkflowState) -> str:
        return "error" if state.get("error") else "execute"

    def _route_after_verification(self, state: WorkflowState) -> str:
        if state.get("completed"):
            return "done"
        return "error" if state.get("error") else "next_step"

    def _route_after_error(self, state: WorkflowState) -> str:
        return "retry" if state.get("retry_count", 0) < self.max_retries else "failed"

    async def run(self, task: str, force_regenerate_plan: bool = False) -> dict:
        print("\n" + "="*80)
        print(f"Task: {task}")
        print("="*80)

        self.task = task
        initial_state = WorkflowState(
            task=task, retrieved_knowledge=[], verified_skills=[], plan=None,
            current_step=0, execution_log=[], error=None, completed=False,
            retry_count=0, replan_count=0, force_regenerate_plan=force_regenerate_plan
        )

        # Start HITL observer if enabled
        if self.enable_hitl and HITL_AVAILABLE:
            self._human_observer = HumanObserver(session_id=self.session_id)
            self._human_observer.start()
            print("[HITL] Observer started (press Ctrl+I to interrupt)")

        async with MCPClient() as client:
            self._client = client

            try:
                final_state = self.graph.invoke(initial_state, {"recursion_limit": 100})

                results = {
                    "success": final_state.get("completed", False) and not final_state.get("error"),
                    "task": task,
                    "plan": final_state["plan"].model_dump() if final_state.get("plan") else None,
                    "steps_completed": final_state.get("current_step", 0),
                    "execution_log": [],
                    "error": final_state.get("error")
                }

                print("\n" + "="*80)
                print("✓ Success!" if results["success"] else f"✗ Failed: {results['error']}")
                print("="*80)

                # Display cost summary
                tracker = get_global_tracker()
                if tracker.calls:
                    tracker.print_summary()

                return results

            except Exception as e:
                print(f"\n✗ Error: {e}")
                return {"success": False, "task": task, "error": str(e)}

            finally:
                # Stop HITL observer
                if self.enable_hitl and self._human_observer:
                    self._human_observer.stop()
                    print("[HITL] Observer stopped")

    def run_sync(self, task: str, force_regenerate_plan: bool = False) -> dict:
        """
        Sync wrapper for run() - for backward compatibility

        Args:
            task: Natural language task description
            force_regenerate_plan: If True, regenerate plan even if cached plan exists

        Returns:
            Execution results
        """
        return asyncio.run(self.run(task, force_regenerate_plan))


def execute_autonomous_task(
    task: str,
    app_name: str = "asammdf 8.6.10",
    catalog_path: str = "agent/knowledge_base/parsed_knowledge/knowledge_catalog.json",
    vector_db_path: str = "agent/knowledge_base/vector_store",
) -> dict:
    """
    Convenience function to execute a task autonomously

    Args:
        task: Natural language task description
        app_name: Application window name
        catalog_path: Path to knowledge catalog

    Returns:
        Execution results
    """
    workflow = AutonomousWorkflow(
        app_name=app_name,
        catalog_path=catalog_path,
        vector_db_path=vector_db_path
    )

    return workflow.run_sync(task)


if __name__ == "__main__":
    """
    Test autonomous workflow
    """
    import argparse

    parser = argparse.ArgumentParser(description="Run autonomous workflow")
    parser.add_argument(
        "task",
        nargs="?",
        default=None,
        help="Task description"
    )
    parser.add_argument(
        "--gui-instructions",
        default=None,
        help="Optional GUI-specific instructions"
    )
    args = parser.parse_args()

    # Default task and GUI instructions (separated for clarity)
    default_task = (
        "Concatenate all .MF4 files in the folder "
        r"C:\Users\ADMIN\Downloads\ev-data-pack-v10\ev-data-pack-v10\electric_cars\log_files\Kia EV6\LOG\2F6913DB\00001026\."
        "Save the concatenated file as Kia_EV_6_2F6913DB.mf4 in the same folder."
    )

    default_gui_instructions = (
        # "To load all MF4 files:"
        # " Go to File → Open, then enter the path of the desired folder, select any .MF4 file, press Ctrl + A to highlight all files in the folder, and then press Enter to load them all."
    )

    # Build final task
    if args.task is None:
        # Use defaults
        task = default_task
        gui_instructions = default_gui_instructions
    else:
        # Use provided arguments
        task = args.task
        gui_instructions = args.gui_instructions

    # Combine task with GUI instructions if available
    if gui_instructions:
        full_task = f"{task} GUI instructions: {gui_instructions}"
    else:
        full_task = task

    results = execute_autonomous_task(task=full_task, catalog_path="agent/knowledge_base/parsed_knowledge/knowledge_catalog.json", vector_db_path="agent/knowledge_base/vector_store")

    print(f"\n\nFinal Results:")
    print(f"  Success: {results['success']}")
    print(f"  Steps completed: {results.get('steps_completed', 0)}")
    if results.get('error'):
        print(f"  Error: {results['error']}")
