# asammdf Agent

**Autonomous GUI Automation Agent with Human-in-the-Loop** - Natural language → GUI control with KB-attached learning, verified skills, and iterative improvement.

---

## 🚀 Quick Start

```python
from agent.workflows.autonomous_workflow import execute_autonomous_task

# With interactive mode (default) - Press ESC anytime during execution for feedback
result = execute_autonomous_task(
    "Concatenate all MF4 files in C:\\data and save as output.mf4",
    interactive_mode=True  # HITL enabled by default
)
print(f"Success: {result['success']}")
```

**💡 Interactive Mode**: Press **ESC anytime** during execution to provide feedback on the current/completed step.

**On failure:** Agent attaches learning to KB, user reruns for improved plan.
**On success:** Human can verify and save as reusable skill.

---

## 📋 Table of Contents

- [System Architecture](#system-architecture)
- [Core Tech Stack](#core-tech-stack)
- [Key Features](#key-features)
- [How It Works](#how-it-works)
- [Folder Structure](#folder-structure)
- [Setup](#setup)
- [Usage Examples](#usage-examples)
- [Performance](#performance)

---

## 🏗️ System Architecture

### KB-Attached Learning with HITL and Iterative Rerun

```
Natural Language Task
    ↓
Skill Matching (HITL) → Check verified skills library (fuzzy matching)
    ↓ (if no match)
RAG Retrieval (ChromaDB) → KB items with past learnings & trust scores
    ↓
AI Planning (GPT-5-mini) → Plan with kb_source attribution
    ↓
Adaptive Execution (GPT-4o-mini) → Resolve UI elements
    ├─ Low Confidence → Request Human Approval (HITL)
    ├─ [ANYTIME] Press ESC → Provide Feedback on Current/Completed Step (HITL) ⌨️
    ↓
On Failure: Attach learning → Stop → User reruns with improved context
On Success: Human Verification → Save as Verified Skill (HITL)
```

**Key HITL Feature**: The **ESC key works anytime during execution** - press it while the agent is working, and feedback will be requested as soon as the current step completes. Non-blocking and seamless.

### Core Principles

1. **KB-Attached Learning**: Learnings stored WITH the KB items they correct
2. **Human-in-the-Loop**: Skills library, action approval, interactive feedback, task verification
3. **Iterative Rerun**: Execution stops on failure, user explicitly reruns
4. **Dynamic Enrichment**: Related docs retrieved fresh during each planning
5. **Vector Consistency**: Catalog is single source of truth
6. **Learning Prioritization**: Verified skills > Learnings > Documentation

---

## 💻 Core Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Knowledge Base** | ChromaDB + sentence-transformers | Semantic doc search with metadata |
| **Planning** | GPT-5-mini (OpenAI) | Generate tool sequences with kb_source attribution |
| **Execution** | GPT-4o-mini (OpenAI) | Dynamic UI element resolution |
| **Learning Storage** | JSON catalog + ChromaDB metadata | KB-attached learnings with trust scores |
| **Skills Library** | JSON per task | Human-verified workflows with fuzzy matching |
| **HITL Observer** | Background thread | Non-blocking human approvals/feedback |
| **Orchestration** | LangGraph | 6-node state machine (no automatic replanning) |
| **MCP Tools** | Windows-MCP server | 13+ GUI automation tools |
| **Keyboard Listener** | pynput | ESC key for interactive feedback |

**Note**: Fully self-contained system using JSON storage (no external databases required).

---

## ✨ Key Features

### Human-in-the-Loop (HITL) System
✅ **Verified Skills Library** - Save successful workflows, reuse with fuzzy matching (≥70% similarity)
✅ **Interactive Mode** - Press ESC anytime during execution for step feedback
✅ **Low-Confidence Approval** - System requests human approval for uncertain actions (<50% confidence)
✅ **Task Verification** - Human verifies completion and optionally saves as skill
✅ **Focus Management** - Auto-switches back to target app after terminal interaction

### KB-Attached Learning System
✅ **Learnings live with KB items** - Errors attached to the KB patterns that caused them
✅ **Trust score tracking** - KB items decay by 0.95 per failure (min 0.5)
✅ **kb_source attribution** - LLM sets which KB item inspired each action
✅ **Dynamic doc retrieval** - Related docs retrieved fresh during planning (not stored)
✅ **Vector metadata sync** - Catalog is single source of truth, metadata reloaded automatically

### Iterative Rerun Architecture
✅ **No automatic replanning** - Execution stops on failure, user controls reruns
✅ **Progressive improvement** - Each rerun sees more learnings, generates better plans
✅ **Deterministic flow** - Simple, predictable, debuggable
✅ **User control** - Explicit reruns, clear feedback

### Planning & Execution
✅ **Documentation-driven** - GPT extracts knowledge from docs (no hardcoding)
✅ **Adaptive resolution** - Resolves UI elements dynamically with GPT-4o-mini
✅ **Learning prioritization** - Verified skills > Learnings > Documentation
✅ **Prompt history** - Every planning prompt saved for debugging
✅ **Cost tracking** - Real-time API monitoring by component/model
✅ **State caching** - Reuses UI state across actions in same step

---

## 🔄 How It Works

### Example: "Concatenate MF4 files"

#### First Run (Failure)

**1. RAG Retrieval** (<1s)
```
Query: "Concatenate MF4 files"
Retrieved 5 KB items: concatenate_files, open_files, save_file, ...
  • open_files (trust: 1.0, learnings: 0)
```

**2. Planning** (2-5s)
```
LLM generates plan with kb_source attribution:
Step 5: Click "Add Files" button
  - kb_source: "open_files"  ← LLM sets this
  - reasoning: "Open files using Add Files button"
```

**3. Execution** (~500ms/step)
```
Step 1-4: ✓ Success
Step 5: ✗ FAILURE - "Button 'Add Files' not found"
```

**4. Failure Handling**
```
Create FailureLearning:
  - task: "Concatenate MF4 files"
  - step_num: 5
  - original_action: {"tool_name": "Click-Tool", ...}
  - original_error: "Button 'Add Files' not found"
  - recovery_approach: ""  (empty until success)

Attach to KB item "open_files":
  - kb_learnings: [<learning>]
  - trust_score: 0.95  (decreased from 1.0)

Update vector metadata:
  - has_learnings: true
  - learning_count: 1

STOP EXECUTION
Message: "Learning attached to KB. Please rerun the task."
```

**Catalog After First Run:**
```json
{
  "knowledge_id": "open_files",
  "kb_learnings": [
    {
      "task": "Concatenate MF4 files",
      "original_error": "Button 'Add Files' not found",
      "recovery_approach": ""
    }
  ],
  "trust_score": 0.95
}
```

#### First Rerun (Success)

**1. RAG Retrieval** (<1s)
```
Retrieved KB "open_files" WITH learning:
  • trust: 0.95
  • learnings: 1 (Button 'Add Files' failed)
```

**2. Planning with Learning Context** (2-5s)
```
_format_kb_with_learnings() formats:

---
KB ID: open_files
Description: Open files in asammdf
Action Sequence: click_menu('File'), select_option('Open')
---

⚠️ PAST LEARNINGS (1 correction):

1. Past Failure:
   - Failed Action: Click-Tool
   - Error: Button 'Add Files' not found
   - Successful Approach: (Not yet resolved - see related docs below)

   📚 Related Docs (2):  ← Retrieved dynamically
      • KB ID: file_menu_open
        Open files using File → Open menu
        Shortcut: Ctrl+O
        Actions: click_menu('File'), select_option('Open')

      • KB ID: keyboard_shortcuts
        Use keyboard shortcuts for faster navigation
        Actions: press_keys('Ctrl+O')

⚠️ CAUTION: Trust score 0.95 (has 1 known issue)
---

CRITICAL RULE in system prompt:
"DO NOT repeat failed actions even if multiple KB items suggest them.
Learnings trump documentation."
```

**3. Planning Result**
```
LLM sees:
  ✗ Learning: "Add Files" button failed
  ✓ Related docs: Use Ctrl+O or File → Open menu
  ✓ Critical rule: Don't repeat failures

Generated plan:
Step 5: Press Ctrl+O to open file dialog  ← Changed!
  - kb_source: "keyboard_shortcuts"
  - reasoning: "Use shortcut instead of button (learning shows button failed)"
```

**4. Execution** (~500ms/step)
```
Step 1-5: ✓ All success (including fixed step 5)
Step 6-10: ✓ All success

EXECUTION COMPLETE ✓
```

#### Next Similar Task

```
User runs: "Concatenate MF4 files in D:\folder"

RAG retrieves "open_files" with learning → LLM sees failure context
→ Generates correct plan immediately (uses Ctrl+O)
→ Success on first try
```

---

## 📁 Folder Structure

```
agent/
├── workflows/
│   └── autonomous_workflow.py      # LangGraph orchestrator (6-node + HITL)
├── knowledge_base/                 # RAG System
│   ├── doc_parser.py               # Parse documentation with GPT
│   ├── indexer.py                  # Index into ChromaDB
│   ├── retriever.py                # Semantic search + metadata updates
│   ├── parsed_knowledge/
│   │   └── knowledge_catalog.json  # SOURCE OF TRUTH (learnings stored here)
│   └── vector_store/               # ChromaDB (metadata synced from catalog)
├── planning/                       # Planning System
│   ├── workflow_planner.py         # GPT-5-mini planning with learning formatting
│   ├── schemas.py                  # KnowledgeSchema, ActionSchema, FailureLearning
│   └── plans/                      # Cached plans (Plan_0, Plan_1, ...)
├── execution/                      # Execution System
│   ├── mcp_client.py               # MCP protocol (async)
│   └── adaptive_executor.py        # GPT-4o-mini resolution + failure handling
├── feedback/                       # HITL System
│   ├── human_observer.py           # Background thread for approvals/feedback
│   ├── communication_protocol.py   # Message passing protocol
│   └── schemas.py                  # FailureLearning, HumanFeedback, Verification
├── learning/                       # Skills Library
│   ├── skill_library.py            # Verified workflows storage & matching
│   └── verified_skills/            # Task-specific skill JSON files
├── prompts/                        # Centralized LLM prompts
│   ├── planning_prompt.py          # System/user prompts + history saving
│   ├── coordinate_resolution_prompt.py
│   └── planning_history/           # Saved prompts (Plan_0.md, Plan_1.md, ...)
└── utils/
    └── cost_tracker.py             # API cost monitoring
```

---

## 🛠️ Setup

### 1. Install Dependencies

```bash
# Create virtual environment
python -m venv .agent-venv
.agent-venv\Scripts\activate
pip install -r requirements.txt

# Install Windows-MCP tools
cd tools\Windows-MCP
python -m venv .windows-venv
.windows-venv\Scripts\activate
pip install -e .
cd ..\..
```

### 2. Configure API Key

```bash
cp .env.example .env
# Edit .env: OPENAI_API_KEY=sk-...
```

### 3. Build Knowledge Base (one-time)

```bash
# Parse documentation
python agent/knowledge_base/doc_parser.py

# Build vector index
python agent/knowledge_base/indexer.py --rebuild
```

### 4. Run

```bash
python agent/workflows/autonomous_workflow.py "Your task here"
```

---

## 📖 Usage Examples

### Basic Usage

```python
from agent.workflows.autonomous_workflow import execute_autonomous_task

result = execute_autonomous_task("Open sample.mf4 and plot first signal")
print(f"Success: {result['success']}")
```

### Handling Failures (Iterative Rerun)

```python
from agent.workflows.autonomous_workflow import execute_autonomous_task

# First attempt - may fail
result = execute_autonomous_task("Concatenate all MF4 files")

if not result['success']:
    print("Failure detected. Learning attached to KB.")
    print("Rerunning with improved context...")

    # Rerun - agent sees learning + related docs
    result = execute_autonomous_task("Concatenate all MF4 files")
    print(f"Second attempt: {result['success']}")
```

### Custom Configuration

```python
from agent.workflows.autonomous_workflow import AutonomousWorkflow

workflow = AutonomousWorkflow(
    app_name="asammdf 8.6.10",
    catalog_path="agent/knowledge_base/parsed_knowledge/knowledge_catalog.json",
    vector_db_path="agent/knowledge_base/vector_store",
    max_retries=0  # No automatic retries (user-controlled reruns)
)
result = workflow.run_sync("Your task")
```

### Cost Tracking

```python
from agent.utils.cost_tracker import get_global_tracker

tracker = get_global_tracker()
tracker.print_summary()  # Component/model breakdown
tracker.save_to_file()   # Export to cost_reports/
```

### Inspect KB Learnings

```python
from agent.knowledge_base import KnowledgeRetriever

retriever = KnowledgeRetriever()

# Get specific KB item
kb_item = retriever.get_by_id("open_files")
print(f"Trust score: {kb_item.trust_score}")
print(f"Learnings: {len(kb_item.kb_learnings)}")

for learning in kb_item.kb_learnings:
    print(f"Error: {learning['original_error']}")
    print(f"Recovery: {learning['recovery_approach']}")
```

### Inspect Prompt History

```bash
# View planning prompts
ls agent/prompts/planning_history/

# Example files:
Concatenate_files_Plan_0.md  # First attempt (no learnings)
Concatenate_files_Plan_1.md  # First rerun (with learnings + related docs)
Concatenate_files_Plan_2.md  # Second rerun (with more learnings)
```

### Rebuild KB Index After Manual Edits

```python
from agent.knowledge_base.indexer import rebuild_index

# Rebuild entire index from catalog
rebuild_index(catalog_path="agent/knowledge_base/parsed_knowledge/knowledge_catalog.json")
```

---

## ⚡ Performance

### Typical Task (First Run - No Learnings)
- Knowledge retrieval: <1s
- Plan generation: 2-5s
- Execution: 10-60s (task-dependent)
- Success rate: 70-80%

### After Learning (Rerun with Context)
- Knowledge retrieval: <1s (includes learnings)
- Plan generation: 2-5s (improved with learning context)
- Execution: 10-60s
- Success rate: 85-95%

### Subsequent Similar Tasks
- Uses existing learnings from first encounter
- Success rate: 95%+

---

## 📊 Data Storage

### Knowledge Base Catalog (Single Source of Truth)
```
agent/knowledge_base/parsed_knowledge/
└── knowledge_catalog.json     # All KB items + learnings + trust scores
```

### Vector Store (Synced Metadata)
```
agent/knowledge_base/vector_store/
└── ChromaDB files              # Full KnowledgeSchema + convenience fields
                                # (has_learnings, learning_count, trust_score)
```

### Cached Plans
```
agent/planning/plans/
├── Concatenate_files_Plan_0.json
├── Concatenate_files_Plan_1.json  # Incremental plan after first rerun
└── Open_plot_data_Plan_0.json
```

### Prompt History (Debugging)
```
agent/prompts/planning_history/
├── Concatenate_files_Plan_0.md    # Full system + user prompts
└── Concatenate_files_Plan_1.md    # Shows learnings + related docs
```

---

## 🤝 Human-in-the-Loop (HITL) Features

The system provides **four levels of human involvement**:

### 1. Verified Skills Library (Highest Priority)

**What**: Reuse proven workflows for similar tasks
**When**: Before planning phase
**How**:
```python
# After successful task completion
workflow = AutonomousWorkflow(enable_hitl=True)
result = workflow.run_sync("Concatenate MF4 files in folder X")

# Human verifies → System prompts to save as skill
# Next similar task: "Concatenate MF4 files in folder Y"
# → Skill matched (75%+ similarity) → Reuses proven plan
```

**Benefits**:
- Skip planning entirely for known tasks
- Fuzzy matching finds similar tasks (≥70% similarity threshold)
- Tracks success rate, times used
- Each task type has its own skills file (e.g., `concatenate_mf4_files_skills.json`)

### 2. Low-Confidence Action Approval

**What**: Human approval for uncertain actions
**When**: Before executing action with confidence < 50%
**How**:
```
[Confidence: 0.45] About to: Click button at [450, 300]
Approve? [y/n/correct]:
  y → Execute as planned
  n → Skip action
  correct → Provide corrected action
```

**Confidence factors**:
- Tool type (State-Tool: low risk, Click-Tool: high risk)
- Has symbolic references (e.g., `['last_state:button:Save']`)
- Number of recent failures
- KB item trust score

### 3. Interactive Mode (ESC Key Feedback) ⌨️

**What**: Press ESC **anytime during execution** to provide feedback on current/completed step
**When**: Works at any moment - while agent is planning, executing, or between steps
**How**:
```bash
python agent/workflows/autonomous_workflow.py "Your task" --interactive true

# During execution - Press ESC ANYTIME:
[Step 3/10] Executing...
[ESC pressed] ← You press ESC while step is running
[ESC pressed] Feedback will be requested after current step completes...
[Step 3/10] ✓ Success
[Step 4/10] ✓ Success

[Interactive] Step 4 completed
Provide feedback for this step? [y/N/stop]: y
  1. Was the action correct? [y/n]: n
  2. What should have been done? (describe): Use Ctrl+S instead of clicking Save
  3. Why? (reasoning): Save button location changes in different views
✓ Feedback recorded
```

**Benefits**:
- **Anytime interrupt** - Press ESC whenever you notice something wrong
- **Non-blocking** - Doesn't interrupt current action, waits for safe completion point
- **Keyboard listener** - Monitors ESC key continuously in background
- **Focus auto-switched** - Returns to target app after feedback
- **KB learning** - Creates learning entry attached to KB item

### 4. Final Task Verification

**What**: Human verifies task completed successfully
**When**: After all steps complete
**How**:
```
[HITL] Final Verification
Task completed all 10 steps. Did it succeed? [y/n/partial]: y
Want to save as verified skill? [y/n]: y
  Tags (comma-separated, optional): mf4,concatenate,file_operations
✓ Created verified skill: skill_001_20250126_143000
```

**Benefits**:
- Ensures task actually succeeded (not just "no errors")
- Creates reusable verified skill
- Tracks human feedbacks & agent recoveries in metadata

---

## 🎯 What Makes This Special

### 1. KB-Attached Learning
- **Errors live with patterns**: Learning attached to the KB item that caused the failure
- **Automatic attribution**: LLM sets `kb_source` field, system tracks which patterns fail
- **Trust scores**: KB items decay with failures (0.95 per failure, min 0.5)
- **Contextual retrieval**: Low-trust KB items appear with warning labels

### 2. Dynamic Doc Enrichment
- **Fresh retrieval**: Related docs retrieved during each planning phase (not stored statically)
- **Adapts to changes**: If KB improves, related docs reflect latest state
- **Minimal storage**: Learnings store only error + recovery (not 3 related docs)

### 3. Iterative Rerun (Not Automatic Replanning)
- **User control**: Explicit reruns, no hidden retry loops
- **Deterministic**: Predictable flow, easy to debug
- **Progressive**: Each rerun builds on previous learnings
- **Simple code**: ~155 lines removed vs. automatic replanning

### 4. Learning Prioritization
- **Explicit rule**: "Learnings trump documentation"
- **Prevents circular failures**: Won't repeat failed action even if 10 KB docs suggest it
- **Real-world evidence**: 1 failure learning > N docs (learnings show actual execution results)

### 5. Vector Metadata Consistency
- **Catalog as source of truth**: Vector metadata reloaded from catalog on every update
- **No drift**: Impossible for metadata to become stale
- **Simple API**: `update_vector_metadata(kb_id)` - everything else automatic

### 6. Prompt History
- **Full debugging visibility**: Every planning prompt saved with KB items + learnings
- **Compare iterations**: Plan_0 (no learnings) vs Plan_1 (with learnings)
- **Reproducibility**: See exact LLM input for any planning phase

---

## 🏗️ Architecture Diagrams

### KB-Attached Learning Flow

```
┌─────────────────────────────────────────────────────────────┐
│  knowledge_catalog.json (SOURCE OF TRUTH)                   │
│  {                                                           │
│    "knowledge_id": "open_files",                            │
│    "kb_learnings": [                                        │
│      {                                                       │
│        "original_error": "Button not found",                │
│        "recovery_approach": "Use Ctrl+O"                    │
│      }                                                       │
│    ],                                                        │
│    "trust_score": 0.95                                      │
│  }                                                           │
└─────────────────────────────────────────────────────────────┘
                    ↓ (synced on update)
┌─────────────────────────────────────────────────────────────┐
│  ChromaDB Vector Metadata                                   │
│  {                                                           │
│    "full_knowledge": "{...entire KnowledgeSchema JSON...}", │
│    "knowledge_id": "open_files",                            │
│    "has_learnings": true,                                   │
│    "learning_count": 1,                                     │
│    "trust_score": 0.95                                      │
│  }                                                           │
└─────────────────────────────────────────────────────────────┘
```

### Iterative Rerun Flow

```
First Run:
  Retrieve KB → Plan → Execute → FAILURE
                                    ↓
                          Create FailureLearning
                                    ↓
                          Attach to KB item (via kb_source)
                                    ↓
                          Update trust_score (0.95)
                                    ↓
                          Update vector metadata
                                    ↓
                          STOP EXECUTION
                          "Please rerun the task"

First Rerun:
  Retrieve KB (with learning) → Format with learning context
                                    ↓
                          Dynamically retrieve related docs
                                    ↓
                          Plan with learning + docs + CRITICAL rule
                                    ↓
                          Execute → SUCCESS
```

---

## 🔧 Key Configuration Options

### Workflow Configuration

```python
workflow = AutonomousWorkflow(
    app_name="asammdf 8.6.10",              # Target app
    catalog_path="...",                      # KB catalog location
    vector_db_path="...",                    # ChromaDB location
    max_retries=0,                           # No automatic retries (user reruns)
    enable_hitl=False,                       # HITL disabled by default in current version
    session_id="user_123"                    # Session tracking (optional)
)
```

### Planning Configuration

- **Model**: GPT-4o (`gpt-4o-2024-11-20`)
- **Temperature**: Default (0.7)
- **Max tokens**: 120,000
- **Timeout**: 600s

### Execution Configuration

- **Model**: GPT-4o-mini
- **Temperature**: Default (0.7)
- **Timeout**: 60s

---

## 📝 Schemas Reference

### KnowledgeSchema

```python
class KnowledgeSchema(BaseModel):
    knowledge_id: str                    # Unique identifier
    description: str                     # What this KB item does
    ui_location: str                     # Where to find it in UI
    action_sequence: List[str]           # Step-by-step actions
    shortcut: Optional[str] = None       # Keyboard shortcut
    kb_learnings: List[Dict] = []        # Attached learnings
    trust_score: float = 1.0             # Reliability score
```

### ActionSchema

```python
class ActionSchema(BaseModel):
    tool_name: str                       # MCP tool to use
    tool_arguments: Dict[str, Any]       # Tool arguments
    reasoning: str                       # Why this action
    kb_source: Optional[str] = None      # Which KB item inspired this (LLM sets)
```

### FailureLearning

```python
class FailureLearning(BaseModel):
    task: str                            # Task being executed
    step_num: int                        # Which step failed
    original_action: Dict[str, Any]      # Action that failed
    original_error: str                  # Error message
    recovery_approach: str = ""          # How it was fixed (empty until success)
    timestamp: str                       # When failure occurred
    # NO related_docs field (retrieved dynamically)
```

---

## ⚠️ Limitations

- **Platform:** Windows-only (Windows UI Automation)
- **Scope:** Single application (designed for asammdf)
- **Vision:** Text-based UI state (no GPT-4o vision currently)
- **Execution:** Sequential (no parallel actions)
- **Learning:** User must explicitly rerun to apply learnings

---

## 🚧 Design Decisions & Trade-offs

### ✅ What's Included

1. **HITL System** - Fully integrated (skills library, approvals, interactive mode, verification)
2. **KB-Attached Learning** - Learnings stored with KB items (not separate memory)
3. **Iterative Rerun** - User-controlled reruns (no automatic replanning)
4. **JSON Storage** - Self-contained, no external databases
5. **Two-Model Approach** - GPT-5-mini for planning, GPT-4o-mini for resolution
6. **Task-Specific Skills** - Each task type has its own skills file

### ❌ What's Excluded

- ❌ **Mem0 integration** - Code scaffolding exists but disabled (using JSON only)
- ❌ **Automatic replanning** - Removed in favor of explicit user reruns
- ❌ **Multi-attempt retries** - Disabled (max_retries=0, user reruns instead)
- ❌ **Vision-based state** - Text-only UI state (no GPT-4o vision yet)
- ❌ **Parallel execution** - Sequential only (one action at a time)
- ❌ **Multi-app workflows** - Single application focus

---

## 🤝 Contributing

Key design principles:

1. **Catalog is truth** - All learnings in `knowledge_catalog.json`
2. **User-controlled reruns** - No automatic replanning
3. **Dynamic retrieval** - Related docs fetched fresh, never stored
4. **Type safety** - Pydantic everywhere
5. **Centralized prompts** - All in `agent/prompts/` for easy A/B testing
6. **Prompt history** - Save every planning prompt for debugging

---

## 📈 Status

**Current Version:** KB-Attached Learning with Full HITL Integration

✅ **Complete:**
- ✅ HITL System (skills library, action approval, interactive mode, task verification)
- ✅ KB-attached learning system
- ✅ Iterative rerun architecture (no automatic replanning)
- ✅ Dynamic doc enrichment (related docs retrieved during planning)
- ✅ Vector metadata consistency (catalog as source of truth)
- ✅ Learning prioritization (skills > learnings > docs)
- ✅ Prompt history saving (debugging visibility)
- ✅ Trust score tracking
- ✅ Cost monitoring
- ✅ Task-specific skill files
- ✅ Focus management after feedback
- ✅ Keyboard listener (ESC key)

🚧 **Future Enhancements:**
- Multi-app workflows
- GPT-4o vision integration for state capture
- Parallel action execution
- Automatic skill discovery from execution patterns

---

## 📝 License

[Specify your license here]

---

**Happy Automating! 🚀**

For questions or issues:
- Code documentation (inline comments and docstrings)
- Prompt history (`agent/prompts/planning_history/`)
- KB catalog (`agent/knowledge_base/parsed_knowledge/knowledge_catalog.json`)


# Knowledge Base Recovery Approach Generator

## Overview

After a verified skill is successfully created, the system can now automatically analyze the skill and generate recovery approaches for knowledge base (KB) items that previously encountered errors. This feature uses GPT-4o-mini to extract learnings from successful workflows and attach them to KB items.

## How It Works

### 1. Workflow Integration

When a task completes successfully and a verified skill is created, the system will prompt:

```
================================================================================
[KB Update] Would you like to update the knowledge catalog with
            recovery approaches from this verified skill?
            This will analyze errors in KB items and add learnings
            based on how the verified skill solved them.
================================================================================
Update knowledge catalog? [y/N]:
```

### 2. Recovery Approach Generation

If you respond with 'y', the system will:

1. **Load the verified skill** - The most recently created skill from the skill library
2. **Identify KB items with errors** - Find all KB items that have `original_error` in their `kb_learnings`
3. **Call LLM (GPT-4o-mini)** - Analyze the verified skill to generate recovery approaches
4. **Update the catalog** - Add `recovery_approach` field to relevant KB learnings

### 3. What Gets Generated

For each KB item with an `original_error`, the LLM generates a concise recovery approach (2-3 statements) that explains:

- What went wrong
- How the verified skill solved it
- What to do differently next time

## File Structure

```
agent/
├── prompts/
│   └── kb_recovery_approach_prompt.py    # Prompt template for LLM
├── knowledge_base/
│   ├── recovery_approach_generator.py     # Core generator logic
│   └── parsed_knowledge/
│       └── knowledge_catalog.json         # Updated with recovery approaches
└── workflows/
    └── autonomous_workflow.py             # Integrated in final verification
```

## Usage

### During Normal Workflow

The feature activates automatically after verified skill creation:

```python
# In autonomous_workflow.py, after skill is created:
workflow = AutonomousWorkflow(enable_hitl=True)
result = workflow.run_sync("Your task here")

# If task succeeds and skill is created, you'll be prompted for KB update
```

### Standalone Usage

You can also use the recovery approach generator independently:

```python
from agent.knowledge_base.recovery_approach_generator import (
    generate_and_update_kb_recovery_approaches
)

# Generate and update KB with recovery approaches
success = generate_and_update_kb_recovery_approaches(
    verified_skill_path="agent/learning/verified_skills/your_task_skills.json",
    catalog_path="agent/knowledge_base/parsed_knowledge/knowledge_catalog.json"
)
```

### Testing

Run the test script to verify functionality:

```bash
.agent-venv\Scripts\python.exe test_kb_recovery_generator.py
```

## Example

### Before (KB Learning with Error)

```json
{
  "knowledge_id": "open_files",
  "description": "Open MDF files",
  "kb_learnings": [
    {
      "task": "Concatenate all .MF4 files",
      "step_num": 11,
      "original_error": "Used wildcard path C:\\folder\\*.MF4 instead of exact folder. Suggestion: Use exact folder path, select one file, press Ctrl+A to select all.",
      "timestamp": "2025-10-25T23:45:00"
    }
  ]
}
```

### After (With Recovery Approach)

```json
{
  "knowledge_id": "open_files",
  "description": "Open MDF files",
  "kb_learnings": [
    {
      "task": "Concatenate all .MF4 files",
      "step_num": 11,
      "original_error": "Used wildcard path C:\\folder\\*.MF4 instead of exact folder. Suggestion: Use exact folder path, select one file, press Ctrl+A to select all.",
      "recovery_approach": "Always use the exact folder path from the task. Navigate to the specific folder first, then select one .MF4 file, press Ctrl+A to select all files of that type, and click Open. This ensures all files in the correct directory are loaded.",
      "timestamp": "2025-10-25T23:45:00"
    }
  ]
}
```

## Configuration

### Model Selection

The generator uses GPT-4o-mini by default (cost-effective for this task):

```python
# In recovery_approach_generator.py
self.model = "gpt-4o-mini"
```

To change the model:

```python
generator = RecoveryApproachGenerator()
generator.model = "gpt-4o"  # Use a different model
```

### Temperature

Default temperature is 0.3 for focused, consistent output:

```python
# In generate_recovery_approaches method
temperature=0.3
```

## API Requirements

Requires OpenAI API key in environment:

```bash
export OPENAI_API_KEY=your_api_key_here
# or on Windows:
set OPENAI_API_KEY=your_api_key_here
```

## Prompt Engineering

The prompt is defined in `agent/prompts/kb_recovery_approach_prompt.py`:

Key instructions:
- Review entire verified skill's action sequence
- For each KB item with original_error, identify recovery approach
- Generate 2-3 concise statements max
- Be specific and actionable
- Return null if verified skill doesn't address the error

## Error Handling

The generator handles various error scenarios:

1. **No KB items with errors** - Returns empty dict, skips update
2. **LLM API failure** - Catches exception, returns empty dict
3. **JSON parsing errors** - Handles both array and object responses
4. **File I/O errors** - Catches and reports file access issues

## Integration Points

### 1. Final Verification Node (autonomous_workflow.py:389-515)

```python
def _final_verification_node(self, state: WorkflowState) -> WorkflowState:
    # ... after skill creation ...
    if verification.create_skill:
        skill = self._skill_library.add_skill(...)
        # Prompt for KB update
        self._prompt_kb_update(skill_path)
```

### 2. KB Update Prompt (autonomous_workflow.py:454-515)

```python
def _prompt_kb_update(self, skill_path: str):
    response = input("Update knowledge catalog? [y/N]: ")
    if response == 'y':
        generator = RecoveryApproachGenerator()
        recovery_approaches = generator.generate_recovery_approaches(...)
        generator.update_knowledge_catalog(...)
```

## Benefits

1. **Automated Learning** - Automatically extracts learnings from successful workflows
2. **Consistent Format** - LLM ensures recovery approaches are concise and actionable
3. **Contextual** - Analyzes entire verified skill for comprehensive understanding
4. **Non-intrusive** - Optional prompt, only after successful task completion
5. **Cost-effective** - Uses GPT-4o-mini for this specific task

## Future Enhancements

Potential improvements:

1. **Batch Processing** - Process multiple verified skills at once
2. **Confidence Scores** - Add confidence ratings to recovery approaches
3. **Human Review** - Optional review step before applying to catalog
4. **Version Tracking** - Track which skill version generated each recovery approach
5. **Similarity Matching** - Match similar errors across different KB items

## Troubleshooting

### Issue: No recovery approaches generated

**Possible causes:**
- No KB items have `original_error` field
- Verified skill doesn't address the errors in KB
- LLM API key not configured

**Solution:**
- Check catalog for KB items with `kb_learnings` containing `original_error`
- Verify OPENAI_API_KEY environment variable is set
- Check console output for error messages

### Issue: Import errors

**Solution:**
```bash
# Verify all imports work
.agent-venv\Scripts\python.exe -c "from agent.knowledge_base.recovery_approach_generator import RecoveryApproachGenerator; print('Success')"
```

### Issue: JSON parsing errors

**Possible cause:**
- LLM returned unexpected format

**Solution:**
- Check console output for response format
- Generator handles both array and object responses
- May need to adjust prompt for more consistent output

## Version History

- **v1.0** (2025-11-01) - Initial implementation
  - Recovery approach generation using GPT-4o-mini
  - Integration with autonomous workflow
  - Prompt-based KB update after skill creation
