# Intent-Based Learning Architecture for ASAMMDF Agent

**Date**: 2025-01-19
**Status**: Proposed Design
**Problem**: Current task-level learning retrieval misses relevant step-specific learnings when planning similar tasks

---

## The Core Problem

### Current Issue
When planning a new task, Mem0 retrieval uses the **full task description** as query:
- Query: `"Concatenate MF4 files in folder X"`
- Result: Retrieves generic concatenation learnings
- **Misses**: Specific failures like "Add Files button doesn't exist, use File->Open"

### Example Scenario
**Previous Task A**: `"Concatenate MF4 files in C:\logs\session1"`
- **Step 5 Failed**: Click-Tool on "Add Files" button → `"Element not found"`
- **Recovery**: Used File->Open menu instead

**New Task B**: `"Merge measurement data in C:\data\vehicle"`
- **Needs**: Same "add files" operation
- **Current Retrieval**: Misses the "Add Files button" learning (different task wording)
- **Result**: Plan fails again on same step

### Real-World Evidence (Mem0 Memories)
```
✓ "No button labeled 'Add files' found in the current UI state"
✓ "Assistant can use File->Open to add files"
✓ "Assistant can use knowledge base guidance for File->Open"
```

These learnings exist but aren't retrieved when planning a new concatenation task!

---

## Proposed Solution: Intent-Based Learning Storage & Retrieval

### Key Insight
**Don't store learnings by "task" — store by "functional step intent"**

A task like "Concatenate files" decomposes into functional steps:
1. **add_files** (intent)
2. **set_mode** (intent)
3. **configure_output** (intent)
4. **execute_operation** (intent)

Each step's learnings should be **tagged with its intent** and **queried by intent** when planning similar steps in different tasks.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│ 1. TASK INPUT                                               │
│    "Concatenate MF4 files in folder X. Save as Y.mf4"      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. DECOMPOSE TASK (using TaskDecomposer + LLM)             │
│    Step 0: "Add files" [intent=add_files]                  │
│    Step 1: "Set mode" [intent=set_mode]                    │
│    Step 2: "Configure output" [intent=configure_output]    │
│    Step 3: "Execute" [intent=execute_operation]            │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. RETRIEVE LEARNINGS PER STEP (IntentBasedRetriever)      │
│                                                             │
│    For Step 0 (add_files):                                 │
│      Query: "add files to list asammdf"                    │
│      Filter: metadata.step_intent == "add_files"           │
│      Result: ✓ Retrieved "No Add Files button" learning    │
│                                                             │
│    For Step 1 (set_mode):                                  │
│      Query: "set concatenate mode asammdf"                 │
│      Filter: metadata.step_intent == "set_mode"            │
│      Result: ✓ Retrieved "Use Concatenate tab" learning    │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. FORMAT LEARNINGS PER STEP                               │
│                                                             │
│    ## Step 0: Add Files to List                            │
│    ❌ DON'T: Click 'Add Files' button (doesn't exist)      │
│    ✅ DO: Use File->Open menu                              │
│                                                             │
│    ## Step 1: Set Operation Mode                           │
│    ✅ DO: Click Concatenate tab                            │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. GENERATE PLAN (WorkflowPlanner)                         │
│    LLM receives:                                            │
│      - Task description                                     │
│      - Knowledge base patterns                              │
│      - Decomposed steps with per-step learnings ← NEW!     │
│                                                             │
│    LLM generates plan that:                                 │
│      ✓ Avoids "Add Files" button                           │
│      ✓ Uses File->Open (from learning)                     │
│      ✓ Applies other step-specific learnings               │
└─────────────────────────────────────────────────────────────┘
```

---

## Component 1: Enhanced Learning Storage

### Current Storage (memory_manager.py)
```python
{
    "message": "When executing 'Concatenate MF4 files...' at step 5,
                Click-Tool failed on 'Add Files' button...",
    "metadata": {
        "task": "Concatenate all MF4 files in folder...",  # Full task
        "step": 5  # Just a number, not semantic
    }
}
```

**Problem**: Step 5 is meaningless without the plan. The functional goal ("add files") is lost.

### Enhanced Storage (Proposed)
```python
{
    "message": "When adding files to list in asammdf,
                the 'Add Files' button does not exist.
                Use File->Open menu instead.",

    "metadata": {
        # Existing fields
        "task": "Concatenate all MF4 files...",
        "step_num": 5,
        "source": "agent_self_exploration",
        "timestamp": "2025-01-19T10:30:00",
        "json_file": "session_xxx_learn_xxx.json",

        # NEW: Semantic step information
        "step_intent": "add_files",  # ← KEY ADDITION
        "step_description": "Add MF4 files to concatenation list",
        "domain_operation": "file_operations",

        # NEW: UI elements involved
        "ui_elements": ["Add Files button", "File menu", "Open"],

        # NEW: Failure classification
        "failure_type": "element_not_found"
    }
}
```

### Implementation in `store_learning()`
```python
def store_learning(
    self,
    session_id: str,
    source: LearningSource,
    learning_data: Dict[str, Any],
    context: Dict[str, Any],
    step_intent: Optional[str] = None,  # NEW parameter
    domain_operation: Optional[str] = None  # NEW parameter
) -> str:
    """
    Store learning with semantic step tagging

    Args:
        step_intent: Functional goal of the step (e.g., "add_files", "set_mode")
        domain_operation: High-level category (e.g., "file_operations", "configuration")
    """

    # Enhanced metadata
    metadata = {
        # Existing fields
        "learning_id": learning_id,
        "source": source.value,
        "task": learning.task[:200],
        "step": learning.step_num,
        "timestamp": learning.timestamp,
        "json_file": f"{session_id}_{learning_id}.json",

        # NEW: Semantic step tags
        "step_intent": step_intent or "unknown",
        "domain_operation": domain_operation or "unknown"
    }

    # Store in Mem0
    self.memory.add(
        messages=[{"role": "user", "content": concise_message}],
        agent_id="asammdf_executor",
        run_id=session_id,
        metadata=metadata
    )
```

---

## Component 2: Intent Taxonomy

Define a **taxonomy of functional operations** in asammdf:

```python
ASAMMDF_INTENT_TAXONOMY = {
    "file_operations": {
        "add_files": [
            "add files to list",
            "load files",
            "import files",
            "open files"
        ],
        "save_output": [
            "save file",
            "export file",
            "write output"
        ],
        "browse_folder": [
            "select folder",
            "navigate to folder",
            "choose directory"
        ]
    },

    "data_operations": {
        "concatenate": [
            "merge files",
            "combine files",
            "join files"
        ],
        "filter": [
            "apply filter",
            "select channels",
            "filter signals"
        ],
        "export": [
            "export to CSV",
            "save as format",
            "convert to"
        ]
    },

    "configuration": {
        "set_mode": [
            "set operation mode",
            "choose mode",
            "select mode"
        ],
        "enable_option": [
            "enable sync",
            "check option",
            "activate feature"
        ],
        "configure_output": [
            "set output path",
            "configure destination"
        ]
    },

    "ui_navigation": {
        "open_menu": [
            "open menu",
            "access menu",
            "click menu"
        ],
        "click_button": [
            "click button",
            "press button",
            "activate button"
        ],
        "navigate_tab": [
            "switch tab",
            "open tab",
            "navigate to tab"
        ]
    }
}
```

**Purpose**: Map natural language step descriptions → canonical intent labels

---

## Component 3: Task Decomposer

**Before querying Mem0, decompose the task into functional steps:**

```python
class TaskDecomposer:
    """Decomposes high-level task into functional steps with intents"""

    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = "gpt-4o-mini"  # Lightweight model

    def decompose_task(self, task: str) -> List[Dict[str, Any]]:
        """
        Use LLM to decompose task into functional steps

        Args:
            task: "Concatenate all MF4 files in folder X. Save as Y.mf4"

        Returns:
            [
                {
                    "step_description": "Add MF4 files from folder to list",
                    "intent": "add_files",
                    "domain_operation": "file_operations",
                    "entities": ["MF4 files", "folder X"]
                },
                {
                    "step_description": "Set operation mode to concatenate",
                    "intent": "set_mode",
                    "domain_operation": "configuration",
                    "entities": ["concatenate mode"]
                },
                ...
            ]
        """

        prompt = f"""
Decompose this asammdf GUI task into functional steps:

Task: "{task}"

Available intent taxonomy:
{json.dumps(ASAMMDF_INTENT_TAXONOMY, indent=2)}

For each step, identify:
1. step_description: What needs to be done (natural language)
2. intent: Functional goal (choose from taxonomy)
3. domain_operation: High-level category (file_operations, data_operations, etc.)
4. entities: Specific items involved (files, paths, settings)

Return JSON:
{{
  "steps": [
    {{
      "step_description": "...",
      "intent": "...",
      "domain_operation": "...",
      "entities": [...]
    }}
  ]
}}
"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )

        result = json.loads(response.choices[0].message.content)
        return result["steps"]
```

### Example Output

**Input Task:**
```
"Concatenate all MF4 files in folder C:\Users\ADMIN\Downloads\...\00001026\.
 Save as Kia_EV_6_2F6913DB.mf4 in same folder."
```

**Decomposed Steps:**
```json
{
  "steps": [
    {
      "step_description": "Add MF4 files from folder to concatenation list",
      "intent": "add_files",
      "domain_operation": "file_operations",
      "entities": ["MF4 files", "C:\\Users\\ADMIN\\...\\00001026\\"]
    },
    {
      "step_description": "Set operation mode to concatenate",
      "intent": "set_mode",
      "domain_operation": "configuration",
      "entities": ["concatenate"]
    },
    {
      "step_description": "Enable timestamp synchronization option",
      "intent": "enable_option",
      "domain_operation": "configuration",
      "entities": ["timestamp sync"]
    },
    {
      "step_description": "Configure output file path and name",
      "intent": "configure_output",
      "domain_operation": "configuration",
      "entities": ["Kia_EV_6_2F6913DB.mf4", "C:\\Users\\ADMIN\\...\\00001026\\"]
    },
    {
      "step_description": "Start concatenation operation",
      "intent": "execute_operation",
      "domain_operation": "data_operations",
      "entities": ["concatenate"]
    }
  ]
}
```

---

## Component 4: Intent-Based Retriever

**Query Mem0 for EACH decomposed step using its intent:**

```python
class IntentBasedRetriever:
    """Retrieves learnings based on functional intent, not full task"""

    def retrieve_for_decomposed_task(
        self,
        decomposed_steps: List[Dict[str, Any]],
        session_id: Optional[str] = None
    ) -> Dict[str, List[Dict]]:
        """
        For each functional step, retrieve relevant past learnings

        Returns:
            {
                "step_0_add_files": [learning1, learning2, ...],
                "step_1_set_mode": [learning3, ...],
                ...
            }
        """

        step_learnings = {}

        for idx, step in enumerate(decomposed_steps):
            intent = step["intent"]
            operation = step["domain_operation"]
            description = step["step_description"]

            # Build multiple query variants for this specific step
            queries = self._build_intent_queries(intent, operation, description)

            # Retrieve from Mem0 with metadata filters
            learnings = self._retrieve_with_filters(
                queries=queries,
                filters={
                    "step_intent": intent,  # Filter by intent
                    "domain_operation": operation  # Filter by domain
                },
                session_id=session_id,
                limit_per_query=3
            )

            step_learnings[f"step_{idx}_{intent}"] = learnings

        return step_learnings

    def _build_intent_queries(
        self,
        intent: str,
        operation: str,
        description: str
    ) -> List[str]:
        """
        Build multiple query variants for an intent

        Example for intent="add_files":
            [
                "add files to list in asammdf",
                "load files into application",
                "import MF4 files",
                "file selection asammdf error",
                "Add Files button not found"
            ]
        """

        queries = []

        # Query 1: Natural language intent
        queries.append(description)

        # Query 2: Intent synonyms from taxonomy
        intent_synonyms = ASAMMDF_INTENT_TAXONOMY.get(operation, {}).get(intent, [])
        for synonym in intent_synonyms:
            queries.append(f"{synonym} in asammdf")

        # Query 3: Error-focused queries
        queries.append(f"{intent} error failure asammdf")
        queries.append(f"{intent} button not found")

        # Query 4: UI element-specific queries (if known)
        if intent == "add_files":
            queries.extend([
                "Add Files button asammdf",
                "File menu Open asammdf",
                "load files dialog"
            ])
        elif intent == "set_mode":
            queries.append("Concatenate tab asammdf")

        return queries

    def _retrieve_with_filters(
        self,
        queries: List[str],
        filters: Dict[str, Any],
        session_id: Optional[str] = None,
        limit_per_query: int = 3
    ) -> List[Dict]:
        """
        Execute multiple queries with metadata filters and aggregate results
        """

        all_memories = []
        seen_learning_ids = set()

        for query in queries:
            # Query Mem0 with metadata filters
            search_params = {
                "query": query,
                "agent_id": "asammdf_executor",
                "limit": limit_per_query
            }

            if session_id:
                search_params["run_id"] = session_id

            # Note: Mem0 metadata filtering syntax may vary
            # This is conceptual - check Mem0 docs for exact API
            if filters:
                search_params["filters"] = filters

            results = self.memory.search(**search_params)

            # Deduplicate by learning_id
            for mem in results:
                learning_id = mem.get("metadata", {}).get("learning_id")
                if learning_id and learning_id not in seen_learning_ids:
                    all_memories.append(mem)
                    seen_learning_ids.add(learning_id)

        # Sort by relevance score
        all_memories.sort(key=lambda x: x.get("score", 0.0), reverse=True)

        return all_memories
```

---

## Component 5: Enhanced Planning Integration

**Modify `workflow_planner.py` to use intent-based retrieval:**

```python
class WorkflowPlanner:
    def __init__(self, ...):
        # ... existing code ...
        self.task_decomposer = TaskDecomposer()  # NEW
        self.intent_retriever = IntentBasedRetriever(memory_manager=memory_manager)  # NEW

    def generate_plan(
        self,
        task: str,
        available_knowledge: List[KnowledgeSchema],
        context: Optional[str] = None,
        force_regenerate: bool = False,
        latest_state: Optional[str] = None
    ) -> PlanSchema:
        """
        Generate plan with intent-based learning retrieval
        """

        # ... existing skill library check ...

        # NEW: Decompose task into functional steps
        if HITL_AVAILABLE and self.memory_manager:
            print("  [HITL] Decomposing task into functional steps...")
            decomposed_steps = self.task_decomposer.decompose_task(task)
            print(f"  [HITL] Decomposed into {len(decomposed_steps)} steps")

            # Retrieve learnings for each step based on intent
            print("  [HITL] Retrieving intent-based learnings...")
            step_learnings = self.intent_retriever.retrieve_for_decomposed_task(
                decomposed_steps=decomposed_steps,
                session_id=self.session_id
            )

            # Format learnings per step
            learnings_context = self._format_step_learnings(
                decomposed_steps=decomposed_steps,
                step_learnings=step_learnings
            )

            total_learnings = sum(len(v) for v in step_learnings.values())
            print(f"  [HITL] Retrieved {total_learnings} learnings across {len(decomposed_steps)} steps")
        else:
            learnings_context = ""

        # ... existing plan generation with learnings_context ...

    def _format_step_learnings(
        self,
        decomposed_steps: List[Dict],
        step_learnings: Dict[str, List[Dict]]
    ) -> str:
        """
        Format learnings structured by step with DO/DON'T patterns
        """

        formatted = ["\n## Past Learnings by Functional Step\n"]

        for idx, step in enumerate(decomposed_steps):
            intent = step["intent"]
            description = step["step_description"]
            step_key = f"step_{idx}_{intent}"

            learnings = step_learnings.get(step_key, [])

            if not learnings:
                continue

            formatted.append(f"\n### Step {idx + 1}: {description} [{intent}]\n")

            # Extract DO/DON'T patterns
            for learning in learnings[:3]:  # Top 3 per step
                complete = learning.get("complete_learning")
                if not complete:
                    continue

                source = complete.get("source")
                original_action = complete.get("original_action", {})
                original_error = complete.get("original_error", "")
                recovery_approach = complete.get("recovery_approach", "")
                human_reasoning = complete.get("human_reasoning", "")
                corrected_action = complete.get("corrected_action", {})

                # Format based on source
                if source == "agent_self_exploration":
                    formatted.append(
                        f"❌ **AVOID**: {original_action.get('tool_name')} "
                        f"→ Failed with '{original_error}'\n"
                        f"✅ **USE INSTEAD**: {recovery_approach}\n"
                    )
                elif source == "human_interrupt":
                    formatted.append(
                        f"👤 **HUMAN CORRECTION**: {human_reasoning}\n"
                        f"   Original: {original_action.get('tool_name')}\n"
                        f"   Corrected: {corrected_action}\n"
                    )

        return "\n".join(formatted)
```

---

## Example: Complete Workflow

### Input Task
```
"Concatenate all MF4 files in folder C:\Users\ADMIN\Downloads\...\00001026\.
 Save as Kia_EV_6_2F6913DB.mf4 in same folder."
```

### Step 1: Task Decomposition
```
Step 0: "Add MF4 files from folder to list" [intent=add_files]
Step 1: "Set operation to concatenate" [intent=set_mode]
Step 2: "Enable timestamp sync" [intent=enable_option]
Step 3: "Configure output path" [intent=configure_output]
Step 4: "Start concatenation" [intent=execute_operation]
```

### Step 2: Intent-Based Retrieval

**For Step 0 (add_files):**
- **Queries sent to Mem0:**
  - `"Add MF4 files from folder to list"`
  - `"add files to list in asammdf"`
  - `"load files into application"`
  - `"add_files error failure asammdf"`
  - `"Add Files button not found"`
  - `"File menu Open asammdf"`

- **Metadata filter**: `{"step_intent": "add_files", "domain_operation": "file_operations"}`

- **Retrieved (MATCH!):**
  ```json
  {
    "memory": "When adding files to list in asammdf,
               the 'Add Files' button does not exist.
               Use File->Open menu instead.",
    "metadata": {
      "step_intent": "add_files",  // ← MATCHES FILTER
      "failure_type": "element_not_found"
    }
  }
  ```

**For Step 1 (set_mode):**
- **Queries**: `"Set operation to concatenate"`, `"Concatenate tab asammdf"`
- **Filter**: `{"step_intent": "set_mode"}`
- **Retrieved**: Learnings about using Concatenate tab

### Step 3: Format Learnings
```markdown
## Past Learnings by Functional Step

### Step 1: Add MF4 files from folder to list [add_files]

❌ **AVOID**: Click-Tool on 'Add Files' button
   → Failed with 'Element not found'
✅ **USE INSTEAD**: Use File->Open menu to load files

### Step 2: Set operation to concatenate [set_mode]

✅ **USE**: Click Concatenate tab to set mode
```

### Step 4: LLM Generates Plan
The LLM receives:
- Task description
- Knowledge base patterns
- **Decomposed steps with per-step learnings** ← Key difference!

LLM generates plan that:
- ✅ Avoids "Add Files" button
- ✅ Uses File->Open menu (from learning)
- ✅ Uses Concatenate tab
- ✅ Applies other step-specific learnings

---

## Comparison: Current vs Proposed

| Aspect | Current (Task-Level) | Proposed (Intent-Level) |
|--------|---------------------|------------------------|
| **Storage** | Tagged with full task | Tagged with step intent |
| **Query** | "Concatenate MF4 files" | "add files to list in asammdf" |
| **Retrieval** | Generic task matches | Specific step intent matches |
| **Reusability** | Only for identical tasks | Across all tasks needing same step |
| **Precision** | Low (full task must match) | High (step intent matches) |
| **Example Match** | ❌ Misses "Add Files" learning | ✅ Retrieves "Add Files" learning |
| **Cross-Task Learning** | ❌ Limited | ✅ Yes (intent-based) |

---

## Implementation Phases

### Phase 1: Minimal Viable Change (1-2 days)
**Goal**: Add semantic step tagging to existing system

1. **Update `schemas.py`**: Add `step_intent` and `domain_operation` fields to `LearningEntry`
2. **Update `memory_manager.py`**:
   - Add `step_intent` and `domain_operation` parameters to `store_learning()`
   - Include these in Mem0 metadata
3. **Manual tagging**: When storing learnings, manually provide intent (e.g., "add_files", "set_mode")
4. **Test retrieval**: Query with intent-based queries alongside task queries

**Deliverables**:
- Enhanced metadata in Mem0
- Ability to filter by intent
- Immediate improvement in retrieval precision

---

### Phase 2: Task Decomposition (3-5 days)
**Goal**: Automatically decompose tasks before planning

1. **Create `task_decomposer.py`**:
   - Implement `TaskDecomposer` class
   - Use gpt-4o-mini to decompose tasks
   - Map to intent taxonomy

2. **Update `workflow_planner.py`**:
   - Call `TaskDecomposer` before retrieving learnings
   - Query Mem0 for each decomposed step
   - Aggregate learnings by step

3. **Update `adaptive_executor.py`**:
   - Automatically detect step intent during execution
   - Tag learnings with intent when storing

**Deliverables**:
- Automatic task decomposition
- Intent-based retrieval working end-to-end
- Learnings automatically tagged with intent

---

### Phase 3: Full Intent Taxonomy (1 week)
**Goal**: Comprehensive intent classification system

1. **Build taxonomy**: Define complete ASAMMDF intent hierarchy
2. **Intent classifier**: Auto-classify step intents from action descriptions
3. **UI element mapping**: Map intents to expected UI elements
4. **Failure taxonomy**: Classify error types (element_not_found, wrong_path, etc.)
5. **Multi-query strategy**: Implement sophisticated query expansion per intent

**Deliverables**:
- Complete intent taxonomy
- Automatic intent classification
- Multi-dimensional retrieval (intent + failure type + UI elements)
- Maximum learning reusability across tasks

---

## Key Benefits

### 1. Learning Reusability
- **Current**: Learning from "Concatenate task A" only helps "Concatenate task B"
- **Proposed**: Learning from "add_files in any task" helps ALL tasks needing "add_files"

### 2. Precision
- **Current**: Retrieves generic task-level learnings (low precision)
- **Proposed**: Retrieves exact step-level learnings (high precision)

### 3. Failure Prevention
- **Current**: Same failures repeat in similar tasks
- **Proposed**: Step-level failures learned once, avoided everywhere

### 4. Scalability
- **Current**: Learning corpus grows with every unique task
- **Proposed**: Learning corpus grows with every unique STEP TYPE (much slower)

### 5. Composability
- **Current**: Can't compose learnings from different tasks
- **Proposed**: Compose learnings from different tasks if steps match

---

## Open Questions

1. **Intent Taxonomy Completeness**: How do we ensure taxonomy covers all asammdf operations?
   - *Approach*: Start with core operations, expand iteratively based on observed tasks

2. **Intent Auto-Classification Accuracy**: How accurate is LLM at classifying step intents?
   - *Mitigation*: Start with manual tagging in Phase 1, measure auto-classification accuracy in Phase 2

3. **Mem0 Metadata Filtering**: Does Mem0 support complex metadata filters?
   - *Fallback*: If not, retrieve broader results and filter in Python

4. **Decomposition Granularity**: How fine-grained should step decomposition be?
   - *Guideline*: One intent per atomic UI operation (click, type, navigate)

5. **Cross-Domain Generalization**: Can intents generalize to other GUI apps?
   - *Potential*: Yes, many intents (add_files, save_output) are universal

---

## Success Metrics

### Metric 1: Retrieval Precision
- **Baseline**: % of relevant learnings retrieved with current system
- **Target**: >80% relevant learnings retrieved with intent-based system

### Metric 2: Plan Success Rate
- **Baseline**: % of plans that succeed without recovery
- **Target**: +20% improvement with intent-based learnings

### Metric 3: Learning Reuse
- **Baseline**: Average times a learning is retrieved (currently low)
- **Target**: 5x increase in learning reuse across different tasks

### Metric 4: Recovery Reduction
- **Baseline**: Average replanning attempts per task
- **Target**: -30% reduction in replanning (learnings prevent failures)

---

## References

- Current implementation: `agent/feedback/memory_manager.py`
- Planning integration: `agent/planning/workflow_planner.py`
- Learning schemas: `agent/feedback/schemas.py`
- Mem0 documentation: https://docs.mem0.ai/

---

## Next Steps

1. ✅ Document architecture (this file)
2. ⏳ Review and validate approach
3. ⏳ Implement Phase 1 (minimal viable change)
4. ⏳ Measure baseline metrics
5. ⏳ Implement Phase 2 (task decomposition)
6. ⏳ Evaluate improvement in retrieval precision
7. ⏳ Implement Phase 3 (full taxonomy)

---

**End of Document**
