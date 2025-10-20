# asammdf Agent

**Autonomous GUI Automation Agent** - Natural language → GUI control with KB-attached learning and iterative improvement.

---

## 🚀 Quick Start

```python
from agent.workflows.autonomous_workflow import execute_autonomous_task

result = execute_autonomous_task("Concatenate all MF4 files in C:\\data and save as output.mf4")
print(f"Success: {result['success']}")
```

**On failure:** Agent attaches learning to KB, user reruns for improved plan.

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

### KB-Attached Learning with Iterative Rerun

```
Natural Language Task
    ↓
RAG Retrieval (ChromaDB) → KB items with past learnings
    ↓
AI Planning (GPT-4o) → Plan with kb_source attribution
    ↓
Adaptive Execution (GPT-4o-mini) → Resolve UI elements
    ↓
On Failure: Attach learning → Stop → User reruns with improved context
    ↓
On Success: Trust scores intact, learnings reused for similar tasks
```

### Core Principles

1. **KB-Attached Learning**: Learnings stored WITH the KB items they correct
2. **Iterative Rerun**: Execution stops on failure, user explicitly reruns
3. **Dynamic Enrichment**: Related docs retrieved fresh during each planning
4. **Vector Consistency**: Catalog is single source of truth
5. **Learning Prioritization**: Learnings trump documentation (even 1 learning > 10 docs)

---

## 💻 Core Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Knowledge Base** | ChromaDB + sentence-transformers | Semantic doc search with metadata |
| **Planning** | GPT-4o (OpenAI) | Generate tool sequences with kb_source attribution |
| **Execution** | GPT-4o-mini (OpenAI) | Dynamic UI element resolution |
| **Learning Storage** | JSON catalog + ChromaDB metadata | KB-attached learnings with trust scores |
| **Orchestration** | LangGraph | State machine (no automatic replanning) |
| **MCP Tools** | Windows-MCP server | 13+ GUI automation tools |

**Note**: System designed to work WITHOUT external memory stores (Mem0 code exists but disabled).

---

## ✨ Key Features

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
✅ **Adaptive resolution** - Resolves UI elements dynamically
✅ **Learning prioritization** - 1 failure learning overrides 10 KB docs
✅ **Prompt history** - Every planning prompt saved for debugging
✅ **Cost tracking** - Real-time API monitoring by component/model

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
│   └── autonomous_workflow.py      # LangGraph orchestrator (no replanning)
├── knowledge_base/                 # RAG System
│   ├── doc_parser.py               # Parse documentation with GPT
│   ├── indexer.py                  # Index into ChromaDB
│   ├── retriever.py                # Semantic search + metadata updates
│   ├── parsed_knowledge/
│   │   └── knowledge_catalog.json  # SOURCE OF TRUTH (learnings stored here)
│   └── vector_store/               # ChromaDB (metadata synced from catalog)
├── planning/                       # Planning System
│   ├── workflow_planner.py         # GPT-4o planning with learning formatting
│   ├── schemas.py                  # KnowledgeSchema, ActionSchema, FailureLearning
│   └── plans/                      # Cached plans (Plan_0, Plan_1, ...)
├── execution/                      # Execution System
│   ├── mcp_client.py               # MCP protocol (async)
│   └── adaptive_executor.py        # GPT-4o-mini resolution + failure handling
├── feedback/                       # Learning System
│   └── schemas.py                  # FailureLearning, HumanInterruptLearning
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

## 🚧 What's NOT Included (Removed/Deprecated)

- ❌ **Mem0 integration** - Code exists but disabled (JSON storage only)
- ❌ **Automatic replanning** - Removed in favor of user-controlled reruns
- ❌ **PlanRecoveryManager** - Deprecated
- ❌ **max_replan_attempts** - Removed (user reruns instead)
- ❌ **Multi-attempt retries** - Disabled (max_retries=0)
- ❌ **HITL components** - Code exists but not active in current version
- ❌ **Skill library** - Code exists but not active in current version

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

**Current Version:** KB-Attached Learning with Iterative Rerun

✅ **Complete:**
- KB-attached learning system
- Iterative rerun architecture (no automatic replanning)
- Dynamic doc enrichment (related docs retrieved during planning)
- Vector metadata consistency (catalog as source of truth)
- Learning prioritization (learnings trump docs)
- Prompt history saving (debugging visibility)
- Trust score tracking
- Cost monitoring

🚧 **Future Enhancements:**
- Re-enable HITL components (human observer, skill library)
- Multi-app workflows
- GPT-4o vision integration
- Parallel execution

---

## 📝 License

[Specify your license here]

---

**Happy Automating! 🚀**

For questions or issues:
- Code documentation (inline comments and docstrings)
- Prompt history (`agent/prompts/planning_history/`)
- KB catalog (`agent/knowledge_base/parsed_knowledge/knowledge_catalog.json`)
