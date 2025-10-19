# KB-Attached Learning Architecture (Final Design)

**Date**: 2025-01-19
**Status**: Ready for Implementation
**Decision**: Attach learnings to KB items, remove Mem0

---

## Core Principle

**Every learning corrects a specific KB item.** When a plan step fails, attach the learning to the KB item that was used to generate that step.

---

## Key Innovation: `kb_source` Field in ActionSchema

### Problem
When a step fails, we need to know which KB item was responsible so we can attach the learning to it.

### Solution
Add a `kb_source` field to every action in the plan. The LLM fills this during planning.

---

## Schema Changes

### 1. ActionSchema (agent/planning/schemas.py)

```python
class ActionSchema(BaseModel):
    """Schema for a single MCP tool action in a plan"""
    tool_name: str = Field(..., description="MCP tool name to execute")
    tool_arguments: Dict[str, Any] = Field(default_factory=dict, description="Arguments to pass to MCP tool")
    reasoning: Optional[str] = Field(None, description="Why this action is needed")

    # NEW: Track which KB item this action came from
    kb_source: Optional[str] = Field(
        None,
        description="KB item ID this action is derived from (e.g., 'open_files'). Leave empty if not from KB."
    )

    class Config:
        json_schema_extra = {
            "example": {
                "tool_name": "Click-Tool",
                "tool_arguments": {"loc": ["last_state:menu:File"], "button": "left"},
                "reasoning": "Open File menu to access Open command",
                "kb_source": "open_files"  # ← NEW FIELD
            }
        }
```

### 2. KnowledgeSchema (agent/planning/schemas.py)

```python
from agent.feedback.schemas import SelfExplorationLearning, HumanInterruptLearning

class KnowledgeSchema(BaseModel):
    """Knowledge pattern from documentation with accumulated learnings"""
    knowledge_id: str
    description: str
    ui_location: str
    action_sequence: List[str]
    shortcut: Optional[str] = None
    prerequisites: List[str]
    output_state: str
    doc_citation: str
    parameters: Dict[str, Any] = {}

    # NEW: Learnings attached to this KB item
    kb_learnings: List[Union[SelfExplorationLearning, HumanInterruptLearning]] = Field(
        default_factory=list,
        description="Learnings from failures when using this KB item"
    )

    # NEW: Trust score (decreases with failures)
    trust_score: float = Field(
        1.0,
        description="Confidence in this KB item (1.0=fully trusted, <1.0=has failures)"
    )
```

---

## Planning Prompt Changes

### Update System Prompt (agent/prompts/planning_prompt.py)

```python
def get_planning_system_prompt(tools_description: str) -> str:
    return rf"""You are an expert GUI automation planner for asammdf.

AVAILABLE MCP TOOLS:
{tools_description}

CORE RULES:
1. Follow provided knowledge patterns as reference
2. Use ONLY listed tool names with exact argument schemas
3. ALWAYS call State-Tool before interacting with UI elements
4. Start with Switch-Tool to activate asammdf
5. Reference UI elements discovered by State-Tool: ["last_state:element_type:element_name"]

KB SOURCE ATTRIBUTION (IMPORTANT):
For EACH action in your plan, set the "kb_source" field:
- If action is derived from a KB item, set kb_source to that KB item's knowledge_id
- If action is your own reasoning (not from KB), leave kb_source as null or empty
- This helps track which KB items led to failures so we can improve them

Example:
{{
  "tool_name": "Click-Tool",
  "tool_arguments": {{"loc": ["last_state:menu:File"], "button": "left"}},
  "reasoning": "Open File menu (from KB: open_files)",
  "kb_source": "open_files"  // ← Derived from KB item "open_files"
}}

JSON OUTPUT SCHEMA:
{{
  "plan": [
    {{
      "tool_name": "Switch-Tool",
      "tool_arguments": {{"name": "asammdf"}},
      "reasoning": "Activate asammdf window",
      "kb_source": null  // Not from KB, general practice
    }},
    {{
      "tool_name": "Click-Tool",
      "tool_arguments": {{"loc": ["last_state:menu:File"], "button": "left"}},
      "reasoning": "Open File menu to access Open command",
      "kb_source": "open_files"  // From KB item "open_files"
    }}
  ],
  "reasoning": "Overall strategy...",
  "estimated_duration": 60
}}

Return ONLY valid JSON."""
```

### Update User Prompt (agent/prompts/planning_prompt.py)

```python
def get_planning_user_prompt(
    task: str,
    knowledge_json: str,
    kb_items_with_learnings: str,  # NEW: Formatted KB with learnings
    context: str = "",
    latest_state: str = ""
) -> str:
    """User prompt for plan generation with KB learnings"""

    return f"""User task: "{task}"

Available knowledge patterns from documentation:
{kb_items_with_learnings}

USING KB ITEMS WITH LEARNINGS:
1. Each KB item has a "knowledge_id" (e.g., "open_files")
2. Some KB items have "PAST LEARNINGS" showing what went wrong before
3. When generating actions FROM a KB item:
   - Set kb_source to that KB item's knowledge_id
   - If KB has learnings, PREFER the recovery approach over original KB
4. When generating actions from your own reasoning:
   - Leave kb_source as null

Example:
If using KB item "open_files", set kb_source="open_files" for actions derived from it.

{context}
{latest_state}

Generate a complete execution plan. Remember to set kb_source for each action!
Return ONLY valid JSON."""
```

---

## Workflow Implementation

### 1. Planning Phase (workflow_planner.py)

```python
def generate_plan(
    self,
    task: str,
    available_knowledge: List[KnowledgeSchema],
    ...
) -> PlanSchema:
    """Generate plan with KB items and track which items were used"""

    # Format KB items WITH learnings for LLM
    kb_formatted = self._format_kb_with_learnings(available_knowledge)

    # Build prompts
    system_prompt = get_planning_system_prompt(tools_description)
    user_prompt = get_planning_user_prompt(
        task=task,
        knowledge_json="",  # Deprecated, using kb_items_with_learnings instead
        kb_items_with_learnings=kb_formatted,  # NEW
        context=context or "",
        latest_state=latest_state or ""
    )

    # Generate plan (LLM fills kb_source for each action)
    response = self.client.chat.completions.create(
        model=self.model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    )

    plan_data = json.loads(response.choices[0].message.content)
    plan = PlanSchema(**plan_data)

    # Save plan with retrieved KB metadata
    save_plan(
        task,
        plan,
        plan_number=0,
        metadata={
            "retrieved_kb_ids": [kb.knowledge_id for kb in available_knowledge],
            "retrieved_kb_items": [kb.model_dump() for kb in available_knowledge]
        }
    )

    return plan


def _format_kb_with_learnings(
    self,
    kb_items: List[KnowledgeSchema]
) -> str:
    """Format KB items with learnings for LLM context"""

    formatted_parts = []

    for kb in kb_items:
        kb_section = f"""
---
KB ID: {kb.knowledge_id}
Description: {kb.description}
UI Location: {kb.ui_location}
Action Sequence:
{chr(10).join(f"  - {action}" for action in kb.action_sequence)}
Shortcut: {kb.shortcut or 'None'}
---"""

        # Add learnings if exist
        if kb.kb_learnings:
            kb_section += f"\n\n⚠️ PAST LEARNINGS ({len(kb.kb_learnings)} corrections):\n"

            for idx, learning in enumerate(kb.kb_learnings[:3], 1):
                if hasattr(learning, 'recovery_approach'):  # SelfExplorationLearning
                    kb_section += f"""
{idx}. Agent Self-Recovery:
   - Failed Action: {learning.original_action.get('tool_name', 'N/A')}
   - Error: {learning.original_error[:150]}...
   - What Worked: {learning.recovery_approach[:200]}...
   - Task Context: {learning.task[:100]}...
"""
                elif hasattr(learning, 'human_reasoning'):  # HumanInterruptLearning
                    kb_section += f"""
{idx}. Human Correction:
   - Human Said: {learning.human_reasoning[:200]}...
   - Corrected To: {learning.corrected_action.get('tool_name', 'N/A')}
   - Task Context: {learning.task[:100]}...
"""

        # Trust score warning
        if kb.trust_score < 0.9:
            kb_section += f"\n⚠️ CAUTION: Trust score {kb.trust_score:.2f} (has known issues)\n"

        formatted_parts.append(kb_section)

    return "\n".join(formatted_parts)
```

### 2. Execution & Failure (adaptive_executor.py)

When a step fails, the `kb_source` field tells us exactly which KB item to blame:

```python
class AdaptiveExecutor:
    def execute_action(
        self,
        action: ActionSchema,
        context: List[ActionSchema],
        step_num: int
    ) -> ExecutionResult:
        """Execute action and handle failures"""

        try:
            # ... execution logic ...
            result = self._execute_with_mcp(action)

            if not result.success:
                # Action failed - create learning and attach to KB
                self._handle_step_failure(
                    step_num=step_num,
                    failed_action=action,
                    error=result.error,
                    kb_source=action.kb_source  # ← Directly from action!
                )

            return result

        except Exception as e:
            # Handle failure...
            pass

    def _handle_step_failure(
        self,
        step_num: int,
        failed_action: ActionSchema,
        error: str,
        kb_source: Optional[str]  # ← From action.kb_source
    ):
        """
        Handle failure, trigger recovery, and attach learning to KB item
        """

        # Trigger replanning/recovery
        recovery_plan = self.recovery_manager.generate_recovery_plan(...)

        # Merge and continue...
        merged_plan, new_filepath = self.recovery_manager.merge_plans(recovery_plan)

        # Create learning
        learning = SelfExplorationLearning(
            task=self.recovery_manager.original_task,
            step_num=step_num,
            original_action=failed_action.model_dump(),
            original_error=error,
            recovery_approach=recovery_plan.reasoning,
            timestamp=datetime.now().isoformat()
        )

        # Attach learning to responsible KB item
        if kb_source:  # ← LLM told us which KB item!
            self._attach_learning_to_kb(
                kb_id=kb_source,
                learning=learning
            )
            print(f"  [KB Learning] Attached to KB: {kb_source}")
        else:
            print(f"  [KB Learning] No KB source - action was not from KB")

    def _attach_learning_to_kb(
        self,
        kb_id: str,
        learning: Union[SelfExplorationLearning, HumanInterruptLearning]
    ):
        """
        Attach learning to KB item and persist to catalog
        """

        catalog_path = "agent/knowledge_base/parsed_knowledge/knowledge_catalog.json"

        # Load catalog
        with open(catalog_path, 'r') as f:
            catalog_data = json.load(f)

        # Find KB item and attach learning
        kb_found = False
        for item in catalog_data:
            if item.get("knowledge_id") == kb_id:
                # Initialize kb_learnings if doesn't exist
                if "kb_learnings" not in item:
                    item["kb_learnings"] = []

                # Append learning
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
        with open(catalog_path, 'w') as f:
            json.dump(catalog_data, f, indent=2)
```

### 3. Human Interrupt Handling

Same approach when human interrupts:

```python
def _handle_human_interrupt(
    self,
    step_num: int,
    original_action: ActionSchema,
    corrected_action: Dict[str, Any],
    human_reasoning: str
):
    """Handle human interrupt and attach learning to KB"""

    # Create learning
    learning = HumanInterruptLearning(
        task=self.current_task,
        step_num=step_num,
        original_action=original_action.model_dump(),
        corrected_action=corrected_action,
        human_reasoning=human_reasoning,
        timestamp=datetime.now().isoformat()
    )

    # Attach to KB item (if action came from KB)
    if original_action.kb_source:
        self._attach_learning_to_kb(
            kb_id=original_action.kb_source,
            learning=learning
        )
        print(f"  [Human Feedback] Attached to KB: {original_action.kb_source}")

    return learning
```

---

## Knowledge Catalog Schema

### Updated knowledge_catalog.json

Each KB item now includes:
- `kb_learnings`: List of past failures/corrections
- `trust_score`: Confidence metric (starts at 1.0, decreases with failures)

```json
{
  "knowledge_id": "open_files",
  "description": "Open one or more MDF files using the File → Open command.",
  "ui_location": "Menu → File → Open",
  "action_sequence": [
    "click_menu('File')",
    "select_option('Open')",
    "in_file_dialog(select_files)",
    "click_button('Open')"
  ],
  "shortcut": "Ctrl+O",
  "prerequisites": ["app_open"],
  "output_state": "file(s)_opened",
  "doc_citation": "GUI#Menu",
  "parameters": {},

  "kb_learnings": [
    {
      "task": "Concatenate all MF4 files in folder C:\\Users\\...",
      "step_num": 5,
      "original_action": {
        "tool_name": "Click-Tool",
        "tool_arguments": {"loc": ["last_state:button:Add Files"]},
        "reasoning": "Click Add Files button",
        "kb_source": "open_files"
      },
      "original_error": "Element not found: 'Add Files' button does not exist",
      "recovery_approach": "Used File->Open menu instead. asammdf does not have 'Add Files' button for concatenation. Use File->Open to add files to operation list.",
      "timestamp": "2025-01-19T14:30:00"
    }
  ],

  "trust_score": 0.95
}
```

---

## Example: Complete Flow

### 1. Planning

**Task**: "Concatenate MF4 files in folder X"

**Retrieved KB Items**:
- `open_files` (has 1 learning attached)
- `concatenate_mode`
- `save_output`

**LLM generates plan** with `kb_source` attribution:

```json
{
  "plan": [
    {
      "tool_name": "Switch-Tool",
      "tool_arguments": {"name": "asammdf"},
      "reasoning": "Activate asammdf",
      "kb_source": null
    },
    {
      "tool_name": "State-Tool",
      "tool_arguments": {"use_vision": false},
      "reasoning": "Get UI state",
      "kb_source": null
    },
    {
      "tool_name": "Click-Tool",
      "tool_arguments": {"loc": ["last_state:menu:File"]},
      "reasoning": "Open File menu (from KB, with learning: use File->Open, not 'Add Files' button)",
      "kb_source": "open_files"  // ← FROM KB!
    },
    {
      "tool_name": "Click-Tool",
      "tool_arguments": {"loc": ["last_state:menu:Concatenate"]},
      "reasoning": "Select Concatenate mode",
      "kb_source": "concatenate_mode"  // ← FROM KB!
    }
  ],
  "reasoning": "Use File->Open to add files (learned from past failures), then set concatenate mode",
  "estimated_duration": 60
}
```

### 2. Execution

- Step 0 succeeds ✓
- Step 1 succeeds ✓
- Step 2 succeeds ✓ (already uses learning from `open_files`)
- Step 3 **FAILS** ❌ - "Concatenate menu not found"

### 3. Recovery & Learning

```python
# In _handle_step_failure:
failed_action = ActionSchema(
    tool_name="Click-Tool",
    tool_arguments={"loc": ["last_state:menu:Concatenate"]},
    reasoning="Select Concatenate mode",
    kb_source="concatenate_mode"  # ← We know exactly which KB!
)

# Create learning
learning = SelfExplorationLearning(
    task="Concatenate MF4 files...",
    step_num=3,
    original_action=failed_action.model_dump(),
    original_error="Concatenate menu not found",
    recovery_approach="Used Concatenate tab instead of menu. Tab is visible in main UI.",
    timestamp="2025-01-19T15:00:00"
)

# Attach to KB item "concatenate_mode"
_attach_learning_to_kb(
    kb_id="concatenate_mode",  # ← From failed_action.kb_source
    learning=learning
)
```

### 4. Next Task

When planning next concatenation task:

**Retrieved KB**: `concatenate_mode` now has learning attached

**LLM sees**:
```
KB ID: concatenate_mode
Description: Set operation mode to concatenate

⚠️ PAST LEARNINGS (1 correction):
1. Agent Self-Recovery:
   - Failed Action: Click-Tool
   - Error: Concatenate menu not found
   - What Worked: Used Concatenate tab instead of menu. Tab is visible in main UI.
```

**LLM generates plan** using the learning:
```json
{
  "tool_name": "Click-Tool",
  "tool_arguments": {"loc": ["last_state:tab:Concatenate"]},
  "reasoning": "Click Concatenate tab (learned: menu doesn't exist, use tab)",
  "kb_source": "concatenate_mode"
}
```

---

## Benefits of kb_source Field

### 1. Automatic KB Attribution
- No need to guess which KB item caused failure
- LLM tells us during planning via `kb_source` field

### 2. Precise Learning Attachment
- Learning attached to exact KB item
- Next time KB item retrieved → learning comes with it

### 3. Trust Score Tracking
- KB items with failures get lower trust scores
- Can prioritize high-trust KB items during retrieval

### 4. KB Self-Correction
- KB catalog becomes self-improving
- Bad KB items get enriched with corrections automatically

---

## Implementation Checklist

### Phase 1: Schema Updates
- [ ] Add `kb_source` field to `ActionSchema`
- [ ] Add `kb_learnings` and `trust_score` to `KnowledgeSchema`
- [ ] Initialize `knowledge_catalog.json` with empty `kb_learnings: []` and `trust_score: 1.0`

### Phase 2: Planning Updates
- [ ] Update `get_planning_system_prompt()` to explain `kb_source` field
- [ ] Update `get_planning_user_prompt()` to use formatted KB with learnings
- [ ] Add `_format_kb_with_learnings()` in `workflow_planner.py`
- [ ] Update `save_plan()` to store retrieved KB metadata

### Phase 3: Execution Updates
- [ ] Add `_attach_learning_to_kb()` in `adaptive_executor.py`
- [ ] Update `_handle_step_failure()` to use `action.kb_source`
- [ ] Update human interrupt handling to use `action.kb_source`
- [ ] Test learning attachment when step fails

### Phase 4: Retrieval Updates
- [ ] Update `KnowledgeRetriever._load_catalog()` to parse `kb_learnings`
- [ ] Format KB items with learnings when sending to LLM
- [ ] Verify learnings are included in planning context

### Phase 5: Cleanup
- [ ] Remove `memory_manager.py` (Mem0 integration)
- [ ] Remove Mem0 initialization from `autonomous_workflow.py`
- [ ] Remove `mem0ai` from dependencies
- [ ] Clean up any Mem0-related imports

---

## Success Metrics

### Metric 1: KB Attribution Accuracy
- % of failed steps that have `kb_source` set
- Target: >80% of failures traceable to KB item

### Metric 2: Learning Reuse
- Average times a KB learning is used in subsequent plans
- Target: Each learning reused 3+ times

### Metric 3: Trust Score Correlation
- Correlation between trust score and plan success rate
- Target: Lower trust KB items → higher plan failure rate

### Metric 4: KB Self-Correction
- % of KB items with at least 1 learning after 10 tasks
- Target: 40% of KB items enriched with learnings

---

## Open Questions

1. **What if LLM forgets to set kb_source?**
   - Fallback: Use heuristic matching (current `_identify_responsible_kb_item()`)
   - Log warning for monitoring

2. **Should we version KB learnings?**
   - Consideration: Track which version of asammdf the learning applies to
   - Decision: Add later if needed

3. **How to handle conflicting learnings?**
   - Example: One learning says "use menu", another says "use tab"
   - Solution: Show all learnings, let LLM decide based on most recent/verified

4. **Should trust_score affect retrieval ranking?**
   - Yes: Rank by `relevance * trust_score`
   - Lower trust KB items still retrieved but deprioritized

---

**End of Design Document**

Ready for implementation when approved.
