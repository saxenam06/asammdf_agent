# LangGraph + Mem0 Integration Analysis

## Current Implementation Status

Your asammdf agent **already uses both LangGraph and Mem0**, but there are opportunities to enhance the integration based on the official documentation pattern.

### What You Already Have ✅

1. **LangGraph State Management**
   - `WorkflowState` TypedDict for state tracking
   - 6-node state machine (retrieve → plan → validate → execute → verify → final_verification)
   - Conditional edges for routing
   - Proper error handling nodes

2. **Mem0 Integration**
   - `LearningMemoryManager` using Mem0 for storing learnings
   - Session-based memory (`session_id`)
   - Multi-source learning (human proactive, human interrupt, agent self-exploration)
   - Memory retrieval in planning phase

### What Could Be Enhanced 🚀

Based on the official LangGraph + Mem0 customer support example, here are **recommended improvements**:

---

## 1. **Enhanced State Structure**

### Current:
```python
class WorkflowState(TypedDict):
    task: str
    retrieved_knowledge: List[KnowledgeSchema]
    plan: Optional[PlanSchema]
    current_step: int
    execution_log: Annotated[List[ExecutionResult], operator.add]
    error: Optional[str]
    completed: bool
    retry_count: int
    replan_count: int
    force_regenerate_plan: bool
```

### Suggested Enhancement:
```python
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage, AIMessage

class WorkflowState(TypedDict):
    # Existing fields
    task: str
    retrieved_knowledge: List[KnowledgeSchema]
    plan: Optional[PlanSchema]
    current_step: int
    execution_log: Annotated[List[ExecutionResult], operator.add]
    error: Optional[str]
    completed: bool
    retry_count: int
    replan_count: int
    force_regenerate_plan: bool

    # NEW: Message-based conversation tracking (LangGraph best practice)
    messages: Annotated[List[HumanMessage | AIMessage], add_messages]

    # NEW: Mem0 session tracking
    mem0_user_id: str
```

**Benefits:**
- Enables conversation history tracking
- Better integration with LangChain's message system
- More structured memory context for Mem0

---

## 2. **Improved Memory Context Injection**

### Current Pattern (in `workflow_planner.py`):
```python
# Retrieve learnings and append to prompt
learnings = self.memory_manager.retrieve_all_learnings_for_task(task=task, session_id=self.session_id)
learnings_context = format_learnings(learnings)
user_prompt += learnings_context
```

### Suggested Pattern (from official docs):
```python
def _generate_plan_node(self, state: WorkflowState) -> WorkflowState:
    """Generate plan with Mem0 context injection"""

    # 1. Retrieve memories from Mem0
    memories = self._memory_manager.memory.search(
        query=state["task"],
        user_id=state["mem0_user_id"],
        agent_id="asammdf_executor"
    )

    # 2. Format as system context
    context = "Relevant learnings from past executions:\n"
    for mem in memories.get('results', []):
        context += f"- {mem['memory']} (relevance: {mem.get('score', 0):.2f})\n"

    # 3. Inject into planning prompt
    system_message = SystemMessage(content=f"""You are an expert workflow planner.

{context}

Generate a plan for the following task: {state['task']}""")

    # 4. Generate plan with context
    plan = self.planner.generate_plan(
        task=state["task"],
        available_knowledge=state["retrieved_knowledge"],
        memory_context=context  # Pass as structured parameter
    )

    return {"plan": plan}
```

**Benefits:**
- More structured memory retrieval
- Better relevance scoring visibility
- Cleaner separation of concerns

---

## 3. **Automatic Memory Storage After Each Step**

### Current Pattern:
Memory is stored manually in specific locations (final verification, human corrections).

### Suggested Pattern:
```python
def _execute_step_node(self, state: WorkflowState) -> WorkflowState:
    """Execute step and auto-store in Mem0"""

    step_num = state["current_step"]
    action = state["plan"].plan[step_num]

    # Execute action
    result = self.executor.execute_action(action, ...)

    # Auto-store execution result in Mem0
    if self._memory_manager and self._memory_manager.memory:
        interaction = [
            {
                "role": "user",
                "content": f"Step {step_num + 1}: {action.tool_name} with {action.tool_arguments}"
            },
            {
                "role": "assistant",
                "content": f"Result: {'Success' if result.success else 'Failed'} - {result.reasoning}"
            }
        ]

        try:
            self._memory_manager.memory.add(
                messages=interaction,
                user_id=state["mem0_user_id"],
                agent_id="asammdf_executor",
                metadata={
                    "task": state["task"],
                    "step_num": step_num,
                    "tool_name": action.tool_name,
                    "success": result.success,
                    "timestamp": datetime.now().isoformat()
                }
            )
        except Exception as e:
            print(f"[Warning] Failed to store step memory: {e}")

    return {"execution_log": [result], "current_step": step_num + 1}
```

**Benefits:**
- Comprehensive execution history
- Better recovery context for replanning
- Automatic learning without manual triggers

---

## 4. **Enhanced Recovery with Mem0 Context**

### Current Pattern (in `plan_recovery.py`):
```python
# Retrieve KB knowledge for recovery
recovery_knowledge = self.knowledge_retriever.retrieve(...)
```

### Suggested Enhancement:
```python
def replan_with_memory_context(
    self,
    task: str,
    progress_summary: str,
    error_info: str,
    state: WorkflowState
) -> PlanSchema:
    """Replan with both KB knowledge AND Mem0 memories"""

    # 1. Retrieve KB knowledge (existing)
    kb_knowledge = self.knowledge_retriever.retrieve(...)

    # 2. NEW: Retrieve similar failure memories from Mem0
    failure_query = f"Task: {task}. Error: {error_info}"
    past_failures = self._memory_manager.memory.search(
        query=failure_query,
        user_id=state["mem0_user_id"],
        metadata_filter={"success": False},  # Filter for failed steps
        limit=3
    )

    # 3. NEW: Retrieve successful recovery memories
    recovery_memories = self._memory_manager.memory.search(
        query=f"Recovery from {error_info}",
        user_id=state["mem0_user_id"],
        metadata_filter={"source": "agent_self_exploration"},
        limit=3
    )

    # 4. Combine contexts
    context = f"""
## Knowledge Base Patterns:
{format_kb_knowledge(kb_knowledge)}

## Past Similar Failures:
{format_memories(past_failures)}

## Successful Recoveries:
{format_memories(recovery_memories)}

## Current Situation:
{progress_summary}
Error: {error_info}
"""

    # 5. Generate recovery plan with full context
    return self.planner.generate_plan(
        task=task,
        context=context,
        force_regenerate=True
    )
```

**Benefits:**
- Learn from past failures
- Reuse successful recovery strategies
- More intelligent replanning

---

## 5. **Conversational Message History**

### Suggested Addition:
```python
class AutonomousWorkflow:
    """Add message tracking for better Mem0 integration"""

    def _add_message_to_state(
        self,
        state: WorkflowState,
        role: str,
        content: str
    ) -> WorkflowState:
        """Helper to add messages to state"""
        if role == "user":
            msg = HumanMessage(content=content)
        else:
            msg = AIMessage(content=content)

        state["messages"] = state.get("messages", []) + [msg]
        return state

    def _retrieve_knowledge_node(self, state: WorkflowState) -> WorkflowState:
        """Enhanced with message tracking"""

        # Track as user message
        state = self._add_message_to_state(
            state,
            role="user",
            content=f"Task: {state['task']}"
        )

        # Retrieve knowledge
        knowledge_patterns = self.retriever.retrieve(state["task"], top_k=5)

        # Track as assistant response
        state = self._add_message_to_state(
            state,
            role="assistant",
            content=f"Retrieved {len(knowledge_patterns)} relevant patterns"
        )

        state["retrieved_knowledge"] = knowledge_patterns
        return state
```

**Benefits:**
- Complete audit trail in LangChain message format
- Better visualization with LangSmith/LangFuse
- Easier debugging and analysis

---

## 6. **Structured Memory Retrieval API**

### Suggested Wrapper:
```python
class Mem0LangGraphBridge:
    """Bridge between LangGraph state and Mem0 memory"""

    def __init__(self, memory_manager: LearningMemoryManager):
        self.memory = memory_manager.memory

    def get_context_for_planning(
        self,
        task: str,
        user_id: str,
        limit: int = 5
    ) -> str:
        """Get formatted context for planning"""
        memories = self.memory.search(
            query=task,
            user_id=user_id,
            agent_id="asammdf_executor",
            limit=limit
        )

        context = "## Past Learnings:\n"
        for mem in memories.get('results', []):
            metadata = mem.get('metadata', {})
            context += f"- {mem['memory']}\n"
            context += f"  Source: {metadata.get('source', 'unknown')}\n"
            context += f"  Relevance: {mem.get('score', 0):.2f}\n\n"

        return context

    def store_step_execution(
        self,
        user_id: str,
        task: str,
        step_num: int,
        action: ActionSchema,
        result: ExecutionResult
    ):
        """Store step execution in Mem0"""
        message = f"Task '{task}', Step {step_num}: {action.tool_name} -> {'Success' if result.success else 'Failed'}"

        self.memory.add(
            messages=[{"role": "assistant", "content": message}],
            user_id=user_id,
            agent_id="asammdf_executor",
            metadata={
                "task": task,
                "step_num": step_num,
                "tool_name": action.tool_name,
                "success": result.success
            }
        )
```

---

## Implementation Priority

### High Priority (Quick Wins):
1. ✅ **Auto-store step executions** (Section 3)
   - Small change, big impact
   - Immediate learning benefits

2. ✅ **Enhanced recovery context** (Section 4)
   - Improves self-healing
   - Reuses past recovery strategies

### Medium Priority:
3. **Structured memory context** (Section 2)
   - Cleaner architecture
   - Better prompt engineering

4. **Message history tracking** (Section 5)
   - Better observability
   - Audit trail

### Low Priority (Nice to Have):
5. **Enhanced state structure** (Section 1)
   - Requires refactoring
   - Better LangChain integration

6. **Bridge abstraction** (Section 6)
   - Code organization
   - Easier testing

---

## Code Change Examples

### Quick Win #1: Auto-store Executions

**File:** `agent/workflows/autonomous_workflow.py`

```python
def _execute_step_node(self, state: WorkflowState) -> WorkflowState:
    step_num = state["current_step"]
    action = state["plan"].plan[step_num]

    # Execute
    result = self.executor.execute_action(action, ...)

    # NEW: Auto-store in Mem0
    if self.enable_hitl and self._memory_manager:
        try:
            self._store_execution_memory(state["task"], step_num, action, result)
        except Exception as e:
            print(f"[Warning] Memory storage failed: {e}")

    state["execution_log"] = [result]
    state["current_step"] += 1
    return state

def _store_execution_memory(
    self,
    task: str,
    step_num: int,
    action: ActionSchema,
    result: ExecutionResult
):
    """Store execution in Mem0"""
    if not self._memory_manager.memory:
        return

    interaction = [
        {
            "role": "user",
            "content": f"Step {step_num + 1}: Execute {action.tool_name}"
        },
        {
            "role": "assistant",
            "content": f"{'✓ Success' if result.success else '✗ Failed'}: {result.reasoning}"
        }
    ]

    self._memory_manager.memory.add(
        messages=interaction,
        user_id=self.session_id,
        agent_id="asammdf_executor",
        metadata={
            "task": task,
            "step_num": step_num,
            "tool_name": action.tool_name,
            "success": result.success,
            "timestamp": datetime.now().isoformat()
        }
    )
```

### Quick Win #2: Enhanced Recovery

**File:** `agent/planning/plan_recovery.py`

```python
def recover_and_replan(
    self,
    task: str,
    failed_step_index: int,
    error: str,
    session_id: str  # NEW parameter
) -> PlanSchema:
    """Generate recovery plan with Mem0 context"""

    # Get progress summary
    summary = self.get_execution_summary()

    # Retrieve KB knowledge (existing)
    error_keywords = extract_keywords(error)
    kb_knowledge = self.knowledge_retriever.retrieve(...)

    # NEW: Retrieve failure memories from Mem0
    memory_context = ""
    if self.memory_manager and self.memory_manager.memory:
        try:
            memories = self.memory_manager.memory.search(
                query=f"Failed execution: {error}",
                user_id=session_id,
                limit=3
            )

            memory_context = "\n## Past Similar Failures:\n"
            for mem in memories.get('results', []):
                memory_context += f"- {mem['memory']}\n"
        except Exception as e:
            print(f"[Warning] Mem0 retrieval failed: {e}")

    # Generate recovery plan with enhanced context
    context = f"""
{format_kb_knowledge(kb_knowledge)}
{memory_context}

Current progress: {summary['completed_count']}/{len(self.plan.plan)} steps
Error at step {failed_step_index + 1}: {error}
"""

    return self.planner.generate_plan(
        task=task,
        available_knowledge=kb_knowledge,
        context=context,
        force_regenerate=True
    )
```

---

## Summary

Your implementation is **already quite advanced** with both LangGraph and Mem0 integrated. The suggested enhancements focus on:

1. **Automatic memory capture** - Store every execution step
2. **Richer recovery context** - Use Mem0 to learn from past failures
3. **Structured memory API** - Clean abstraction layer
4. **Message-based tracking** - Better observability

These changes align with the official LangGraph + Mem0 pattern and will enhance your agent's learning and recovery capabilities.

**Next Steps:**
1. Start with Quick Win #1 (auto-store executions)
2. Test with a few tasks
3. Verify Mem0 storage is working
4. Implement Quick Win #2 (enhanced recovery)
5. Measure improvement in success rates
