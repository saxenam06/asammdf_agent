"""
Autonomous workflow orchestrator using LangGraph
Coordinates RAG, planning, execution, and verification
"""

import sys
import os
from typing import TypedDict, Optional, List, Annotated
from langgraph.graph import StateGraph, END
import operator

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from agent.planning.schemas import KnowledgeSchema, PlanSchema, ExecutionResult, VerifiedSkillSchema, ActionSchema
from agent.rag.knowledge_retriever import KnowledgeRetriever
from agent.planning.workflow_planner import WorkflowPlanner
from agent.execution.mcp_client import get_mcp_client
from agent.execution.adaptive_executor import AdaptiveExecutor


class WorkflowState(TypedDict):
    """State of the autonomous workflow"""
    task: str  # The user's task description
    retrieved_knowledge: List[KnowledgeSchema]  # Knowledge patterns retrieved from documentation using RAG
    verified_skills: List[VerifiedSkillSchema]  # Human-verified skills available for this task (if any)
    plan: Optional[PlanSchema]  # Generated execution plan (sequence of MCP tool actions)
    current_step: int  # Current step index in plan execution (0-based)
    execution_log: Annotated[List[ExecutionResult], operator.add]  # Log of executed actions and their results
    error: Optional[str]  # Error message if workflow failed
    completed: bool  # Whether the workflow has completed successfully
    retry_count: int  # Current retry count for the current step
    replan_count: int  # Number of replanning attempts made
    force_regenerate_plan: bool  # Whether to force plan regeneration even if cached plan exists


class AutonomousWorkflow:
    """
    Orchestrates documentation-driven GUI automation workflow
    """

    def __init__(
        self,
        app_name: str = "asammdf 8.6.10",
        knowledge_catalog_path: str = "agent/knowledge_base/json/knowledge_catalog.json",
        vector_db_path: str = "agent/knowledge_base/vector_store_gpt5_mini",
        max_retries: int = 2,
        max_replan_attempts: int = 3
    ):
        """
        Initialize autonomous workflow

        Args:
            app_name: Application window name
            knowledge_catalog_path: Path to knowledge catalog
            max_retries: Maximum retries for failed steps
            max_replan_attempts: Maximum number of replanning attempts
        """
        self.app_name = app_name
        self.max_retries = max_retries
        self.max_replan_attempts = max_replan_attempts
        self.knowledge_catalog_path = knowledge_catalog_path
        self.vector_db_path = vector_db_path
        self.task = None  # Will be set in run()

        # Lazy initialization - don't load heavy components until needed
        self._retriever = None
        self._planner = None
        self._graph = None
        self._client = None
        self._executor = None

    @property
    def retriever(self):
        """Lazy load retriever"""
        if self._retriever is None:
            print("Initializing knowledge retriever...")
            self._retriever = KnowledgeRetriever(
                knowledge_catalog_path=self.knowledge_catalog_path,
                vector_db_path=self.vector_db_path
            )
        return self._retriever

    @property
    def planner(self):
        """Lazy load planner"""
        if self._planner is None:
            print("Initializing workflow planner...")
            self._planner = WorkflowPlanner()
        return self._planner

    @property
    def graph(self):
        """Lazy load graph"""
        if self._graph is None:
            print("Building workflow graph...")
            self._graph = self._build_graph()
        return self._graph

    @property
    def client(self):
        """Lazy load MCP client"""
        if self._client is None:
            self._client = get_mcp_client()
        return self._client

    @property
    def executor(self):
        """Lazy load adaptive executor with latest plan for the task"""
        if self._executor is None and self.task is not None:
            from agent.planning.workflow_planner import get_latest_plan_filepath

            plan_path = get_latest_plan_filepath(self.task)

            if plan_path is None:
                print("  ℹ️  No existing plan found - executor will be initialized after plan generation")
                return None
            else:
                print(f"  📂 Loading latest plan: {os.path.basename(plan_path)}")
                self._executor = AdaptiveExecutor(
                    self.client,
                    knowledge_retriever=self.retriever,
                    plan_filepath=plan_path
                )
        return self._executor

    def _build_graph(self) -> StateGraph:
        """Build LangGraph workflow"""
        workflow = StateGraph(WorkflowState)

        # Add nodes
        workflow.add_node("retrieve_knowledge", self._retrieve_knowledge_node)
        workflow.add_node("generate_plan", self._generate_plan_node)
        workflow.add_node("validate_plan", self._validate_plan_node)
        workflow.add_node("execute_step", self._execute_step_node)
        workflow.add_node("verify_step", self._verify_step_node)
        workflow.add_node("handle_error", self._handle_error_node)

        # Set entry point
        workflow.set_entry_point("retrieve_knowledge")

        # Define edges
        workflow.add_edge("retrieve_knowledge", "generate_plan")
        workflow.add_edge("generate_plan", "validate_plan")

        # Conditional: valid plan → execute, invalid → end with error
        workflow.add_conditional_edges(
            "validate_plan",
            self._route_after_validation,
            {
                "execute": "execute_step",
                "error": END
            }
        )

        # Execute step
        workflow.add_edge("execute_step", "verify_step")

        # Conditional: verification → next step, error, or done
        workflow.add_conditional_edges(
            "verify_step",
            self._route_after_verification,
            {
                "next_step": "execute_step",
                "error": "handle_error",
                "done": END
            }
        )

        # Error handling → retry or end
        workflow.add_conditional_edges(
            "handle_error",
            self._route_after_error,
            {
                "retry": "execute_step",
                "failed": END
            }
        )

        # Compile with higher recursion limit to support plans with many steps
        return workflow.compile()
    # ============================================================================
    # Node implementations
    # ============================================================================

    def _retrieve_knowledge_node(self, state: WorkflowState) -> WorkflowState:
        """Retrieve relevant knowledge patterns from RAG"""
        print(f"\n[1/5] Retrieving knowledge patterns for task: '{state['task']}'")

        knowledge_patterns = self.retriever.retrieve(state["task"], top_k=5)

        print(f"  Retrieved {len(knowledge_patterns)} relevant knowledge patterns:")
        for knowledge in knowledge_patterns:
            print(f"    - {knowledge.knowledge_id}: {knowledge.description}")

        state["retrieved_knowledge"] = knowledge_patterns
        return state

    def _generate_plan_node(self, state: WorkflowState) -> WorkflowState:
        """Generate execution plan using GPT"""
        print(f"\n[2/5] Generating plan with GPT...")

        try:
            # Optionally capture current UI state to help planner understand state format
            latest_state = None
            try:
                print("  → Capturing current UI state for planning context...")
                state_result = self.client.call_tool('State-Tool', {'use_vision': False})
                if not state_result.isError:
                    if hasattr(state_result, 'content') and state_result.content:
                        latest_state = state_result.content[0].text
                    else:
                        latest_state = str(state_result)
                    print(f"  ✓ UI state captured ({len(latest_state)} chars)")
            except Exception as e:
                print(f"  ! Could not capture UI state (non-critical): {e}")
                # Continue without state - planner will work without it

            plan = self.planner.generate_plan(
                task=state["task"],
                available_knowledge=state["retrieved_knowledge"],
                force_regenerate=state.get("force_regenerate_plan", False),
                latest_state=latest_state
            )

            print(f"  Generated plan with {len(plan.plan)} steps:")
            for i, action in enumerate(plan.plan, 1):
                print(f"    {i}. {action.tool_name} {action.tool_arguments}")

            print(f"\n  Reasoning: {plan.reasoning}")

            state["plan"] = plan
            state["current_step"] = 0

            # Force re-initialization of executor with the newly generated plan (Plan_0)
            if self._executor is None:
                print("  🔧 Initializing executor with new plan...")
                # Trigger executor property to load the new Plan_0
                _ = self.executor

        except Exception as e:
            print(f"  ✗ Plan generation failed: {e}")
            state["error"] = f"Plan generation failed: {e}"

        return state

    def _validate_plan_node(self, state: WorkflowState) -> WorkflowState:
        """Validate generated plan"""
        print(f"\n[3/5] Validating plan...")

        if state["plan"] is None:
            state["error"] = "No plan generated"
            print("  ✗ No plan to validate")
            return state

        is_valid, error_msg = self.planner.validate_plan(state["plan"])

        if is_valid:
            print("  ✓ Plan is valid")
        else:
            print(f"  ✗ Plan validation failed: {error_msg}")
            state["error"] = error_msg

        return state

    def _execute_step_node(self, state: WorkflowState) -> WorkflowState:
        """Execute current step using adaptive executor"""
        step_num = state["current_step"]
        total_steps = len(state["plan"].plan) if state["plan"] else 0

        if step_num >= total_steps:
            state["completed"] = True
            return state

        action = state["plan"].plan[step_num]

        print(f"\n[4/5] Executing step {step_num + 1}/{total_steps}: {action.tool_name}")
        print(f"  Tool arguments: {action.tool_arguments}")

        # # Focus application window
        # self.client.call_tool('Switch-Tool', {'name': self.app_name})

        # Execute action with adaptive resolution (passes context for better interpretation)
        context_actions = state["plan"].plan[:step_num]
        result = self.executor.execute_action(action, context=context_actions, step_num=step_num)

        # Track execution in recovery manager
        if self.executor.recovery_manager:
            if result.success:
                self.executor.recovery_manager.mark_step_completed(step_num, result)
                print(f"  ✓ Step {step_num + 1} tracked in recovery manager")
            elif result.action != "REPLAN_TRIGGERED":
                # Only mark as failed if NOT a replan trigger
                # (replanning already recorded the failure in _trigger_replanning)
                self.executor.recovery_manager.mark_step_failed(step_num, result)
                print(f"  ✗ Step {step_num + 1} failure tracked in recovery manager")

        state["execution_log"] = [result]
        state["current_step"] += 1

        return state

    def _verify_step_node(self, state: WorkflowState) -> WorkflowState:
        """Verify step execution and handle replanning"""
        print(f"\n[5/5] Verifying step execution...")

        last_result = state["execution_log"][-1] if state["execution_log"] else None

        if last_result and not last_result.success:
            # Check if this is a replanning trigger
            if last_result.action == "REPLAN_TRIGGERED":
                print(f"\n🔄 REPLANNING DETECTED")

                # Reload merged plan from recovery manager
                if self.executor.recovery_manager:
                    merged_plan = self.executor.recovery_manager.plan
                    state["plan"] = merged_plan

                    # After merge_plans, execution_state is reset with completed steps already in the merged plan
                    # So we start from where the completed steps end (which is tracked in the merged plan structure)
                    # The new execution_state starts fresh, so current_step should start from completed count in merged plan

                    # Get the count of completed steps that were merged into the new plan
                    # These are the actions that were successfully completed before the failure
                    previous_completed_count = merged_plan.reasoning.count("Completed")
                    # Extract number from reasoning like "Completed 5 steps successfully"
                    import re
                    match = re.search(r'Completed (\d+) steps', merged_plan.reasoning)
                    if match:
                        completed_count = int(match.group(1))
                    else:
                        completed_count = 0

                    # Start execution from after the completed steps
                    state["current_step"] = completed_count

                    print(f"  ✓ Merged plan loaded: {len(merged_plan.plan)} total steps")
                    print(f"  → Resuming from step {completed_count + 1} (after {completed_count} completed steps)")

                    # Increment replan count
                    state["replan_count"] = state.get("replan_count", 0) + 1

                    # Check if max replanning attempts reached
                    if state["replan_count"] > self.max_replan_attempts:
                        print(f"  ✗ Max replanning attempts ({self.max_replan_attempts}) reached")
                        state["error"] = f"Max replanning attempts ({self.max_replan_attempts}) reached"
                    else:
                        print(f"  ⟳ Replanning attempt {state['replan_count']}/{self.max_replan_attempts}")
                        # Clear error to continue execution
                        state["error"] = None
                        state["retry_count"] = 0  # Reset retry count for new plan
                else:
                    print(f"  ✗ Recovery manager not available")
                    state["error"] = "Replanning triggered but recovery manager not available"
            else:
                # Regular failure
                print(f"  ✗ Step failed: {last_result.error}")
                state["error"] = last_result.error
        else:
            print(f"  ✓ Step completed successfully")
            state["error"] = None

        return state

    def _handle_error_node(self, state: WorkflowState) -> WorkflowState:
        """Handle execution errors"""
        print(f"\n[Error Handler] Handling error: {state['error']}")

        state["retry_count"] = state.get("retry_count", 0) + 1

        if state["retry_count"] < self.max_retries:
            print(f"  → Retry {state['retry_count']}/{self.max_retries}")
            # Backtrack one step
            state["current_step"] = max(0, state["current_step"] - 1)
            state["error"] = None
        else:
            print(f"  → Max retries reached. Aborting.")

        return state

    # ============================================================================
    # Routing logic
    # ============================================================================

    def _route_after_validation(self, state: WorkflowState) -> str:
        """Route after plan validation"""
        if state.get("error"):
            return "error"
        return "execute"

    def _route_after_verification(self, state: WorkflowState) -> str:
        """Route after step verification"""
        if state.get("completed"):
            return "done"
        elif state.get("error"):
            return "error"
        else:
            return "next_step"

    def _route_after_error(self, state: WorkflowState) -> str:
        """Route after error handling"""
        if state.get("retry_count", 0) < self.max_retries:
            return "retry"
        return "failed"

    # ============================================================================
    # Public API
    # ============================================================================

    def run(self, task: str, force_regenerate_plan: bool = False) -> dict:
        """
        Execute a task autonomously

        Args:
            task: Natural language task description
            force_regenerate_plan: If True, regenerate plan even if cached plan exists

        Returns:
            Execution results
        """
        print("\n" + "="*80)
        print(f"Autonomous Workflow: {task}")
        print("="*80)

        # Store task for executor lazy initialization
        self.task = task

        # Initialize state
        initial_state = WorkflowState(
            task=task,
            retrieved_knowledge=[],
            verified_skills=[],
            plan=None,
            current_step=0,
            execution_log=[],
            error=None,
            completed=False,
            retry_count=0,
            replan_count=0,
            force_regenerate_plan=force_regenerate_plan
        )

        # Run workflow with higher recursion limit to support plans with many steps
        try:
            final_state = self.graph.invoke(
                initial_state,
                {"recursion_limit": 100}
            )

            # Build results
            results = {
                "success": final_state.get("completed", False) and not final_state.get("error"),
                "task": task,
                "plan": final_state["plan"].model_dump() if final_state.get("plan") else None,
                "steps_completed": final_state.get("current_step", 0),
                "execution_log": [r.model_dump() for r in final_state.get("execution_log", [])],
                "error": final_state.get("error")
            }

            if results["success"]:
                print("\n" + "="*80)
                print("✓ Task completed successfully!")
                print("="*80)
            else:
                print("\n" + "="*80)
                print(f"✗ Task failed: {results['error']}")
                print("="*80)

            return results

        except Exception as e:
            print(f"\n✗ Workflow error: {e}")
            return {
                "success": False,
                "task": task,
                "error": str(e)
            }


def execute_autonomous_task(
    task: str,
    app_name: str = "asammdf 8.6.10",
    knowledge_catalog_path: str = "agent/knowledge_base/json/knowledge_catalog_gpt5_mini.json",
    vector_db_path: str = "agent/knowledge_base/vector_store_gpt5_mini",
) -> dict:
    """
    Convenience function to execute a task autonomously

    Args:
        task: Natural language task description
        app_name: Application window name
        knowledge_catalog_path: Path to knowledge catalog

    Returns:
        Execution results
    """
    workflow = AutonomousWorkflow(
        app_name=app_name,
        knowledge_catalog_path=knowledge_catalog_path,
        vector_db_path=vector_db_path
    )

    return workflow.run(task)


if __name__ == "__main__":
    """
    Test autonomous workflow
    """
    import argparse

    parser = argparse.ArgumentParser(description="Run autonomous workflow")
    parser.add_argument(
        "task",
        nargs="?",
        default=(
            "Concatenate all .MF4 files in the folder "
            r"C:\Users\ADMIN\Downloads\ev-data-pack-v10\ev-data-pack-v10\electric_cars\log_files\Tesla Model 3\LOG\3F78A21D\00000001. "
            "Save the concatenated file as Tesla_Model_3_3F78A21D.mf4 in the same folder. "
            "GUI instructions: open the folder in the file dialog, click any file to focus the list, "
            "press CTRL+A to select all files, then press ENTER to load them."
        ),
        help="High-level task: by default, concatenate all MF4 files in the specified folder and save the result there."
    )
    args = parser.parse_args()

    results = execute_autonomous_task(task=args.task, knowledge_catalog_path="agent/knowledge_base/json/knowledge_catalog_gpt5_mini.json",vector_db_path="agent/knowledge_base/vector_store_gpt5_mini")

    print(f"\n\nFinal Results:")
    print(f"  Success: {results['success']}")
    print(f"  Steps completed: {results.get('steps_completed', 0)}")
    if results.get('error'):
        print(f"  Error: {results['error']}")
