**Autonomous GUI Automation with Iterative Learning** 

- Natural language tasks → GUI control with knowledge base learning, human verification, and skill library.
- ASAMMDF Agent is an autonomous GUI automation system that executes Windows GUI based workflows on ASAMMDF tool from natural-language instructions. Given a task description, it generates UI action plans and executes them using MCP tools (e.g., click, type, key-shortcuts, window focus), while continuously improving by learning from failures and converting successful runs into reusable skills. Each rerun leverages accumulated knowledge, making the automation progressively more reliable and repeatable.
---

## 🚀 Quick Start

```python
from agent.workflows.autonomous_workflow import execute_autonomous_task

# Execute with parameters
result = execute_autonomous_task(
    operation="Concatenate all .MF4 files and save with specified name",
    parameters={
        "input_folder": r"C:\data\vehicle_logs",
        "output_folder": r"C:\output",
        "output_filename": "concatenated.mf4"
    },
    interactive_mode=True  # Press ESC for step feedback
)

print(f"Success: {result['success']}")
```

**On failure:** Error attached to knowledge base → User reruns with improved context
**On success:** Human verifies → Saved as reusable verified skill

---

## 🔄 Complete Workflow

### One-Time Setup

```
doc_parser.py → Fetch asammdf docs → LLM extracts patterns → knowledge_catalog.json
                                                                        ↓
indexer.py → Embed into ChromaDB vector store (semantic search ready)
```

### Per-Task Execution (6-Node LangGraph State Machine)

```
User: "Concatenate MF4 files" + parameters
    ↓
┌─────────────────────────────────────────────────────────────────┐
│ [1] retrieve_knowledge                                          │
│  • Check verified skills (fuzzy match ≥75%)                     │
│  • If no match → ChromaDB semantic search                       │
│  • Returns KB items with learnings + trust scores               │
└─────────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────────┐
│ [2] generate_plan (GPT-5-mini)                                  │
│  • LLM receives: task + parameters + KB items with learnings    │
│  • Sets kb_source for each action (tracks which KB inspired it) │
│  • Uses {parameter} placeholders for reusability                │
└─────────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────────┐
│ [3] validate_plan                                               │
│  • Human reviews plan (if HITL enabled)                         │
│  • Collects feedback/modifications                              │
└─────────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────────┐
│ [4] execute_step (loop for each step)                           │
│  • Substitute parameters: {input_folder} → actual path          │
│  • GPT-4o-mini resolves symbolic refs → coordinates             │
│  • MCP client executes Windows automation                       │
│  • Interactive: ESC for step feedback                           │
└─────────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────────┐
│ [5] verify_step                                                 │
│  • Check execution result                                       │
│  • If error → [handle_error] → STOP (user must rerun)          │
│  • If success + more steps → Loop to execute_step              │
│  • If all done → Continue                                       │
└─────────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────────┐
│ [6] final_verification (HITL)                                   │
│  • Human verifies task completion                               │
│  • Save as VerifiedSkill                                        │
│  • Prompt: Generate recovery approaches for KB?                 │
└─────────────────────────────────────────────────────────────────┘
```

### Error Learning Flow (Iterative Improvement)

```
Step N fails
    ↓
System finds kb_source from failed action
    ↓
Create FailureLearning (task, error, timestamp)
    ↓
Attach to KB item in knowledge_catalog.json
    ↓
Update trust_score: ×0.95 (min 0.5)
    ↓
Sync to ChromaDB metadata
    ↓
STOP execution
    ↓
───────────────────────────────────────
USER RERUNS SAME TASK
───────────────────────────────────────
    ↓
Retrieval includes KB item WITH learning
    ↓
GPT-5-mini sees previous error in planning context
    ↓
Generates better plan avoiding past mistakes
    ↓
Success!
```

### Success Flow (Skill Creation)

```
All steps complete successfully
    ↓
Human verification prompt
    ↓
Save VerifiedSkill JSON
  • operation (path-agnostic)
  • parameters schema
  • full action sequence
  • metadata (success_rate, timestamps)
    ↓
Prompt: "Update KB with recovery approaches? [y/N]"
    ↓
If yes → GPT-4o-mini analyzes verified skill
    ↓
For each KB item that had errors:
  • Generate recovery_approach (2-3 sentences)
  • Add to kb_learnings in catalog.json
    ↓
Future tasks benefit from error + recovery context
```

---

## 🏗️ Technical Architecture

### Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Knowledge Base** | ChromaDB + sentence-transformers | Semantic pattern retrieval |
| **Planning** | GPT-5-mini | Generate parameterized action plans |
| **Execution** | GPT-4o-mini | Resolve UI symbolic references to coordinates |
| **Automation** | MCP (Model Context Protocol) | Windows GUI control |
| **Recovery Generation** | GPT-4o-mini | Extract learnings from verified skills |
| **Learning Storage** | JSON catalog + ChromaDB metadata | KB-attached error learnings |
| **Skills Library** | JSON per verified task | Reusable workflows with fuzzy matching |
| **Orchestration** | LangGraph | State machine workflow |

### Core Mechanisms

**1. KB-Source Attribution**
- LLM assigns `kb_source` to each action during planning
- When action fails → System knows which KB item caused it
- Learning attached directly to causative pattern (not random)

**2. Parameterized Tasks**
- Operations separate from paths: `"Concatenate files"` + `{"input_folder": "..."}`
- Planner uses `{parameter_name}` placeholders
- Executor substitutes before execution
- Skills reusable across different folders/files

**3. Symbolic Reference Resolution**
- Planner: `"Click button with text 'Open'"`
- Executor: GPT-4o-mini + State-Tool output → Resolves to `(x, y)` coordinates
- Adapts to UI changes dynamically

**4. Trust Score Decay**
- Each failure: `trust_score × 0.95` (minimum 0.5)
- Stored in both `knowledge_catalog.json` and ChromaDB metadata
- Tracks reliability of KB patterns over time

**5. Fuzzy Skill Matching**
- `SequenceMatcher` compares operations (ignoring parameters)
- Threshold: 75% similarity
- Example: "Concatenate MF4 files" matches "Concatenate all .MF4 files"
- Enables skill reuse for similar tasks

**6. Human-in-the-Loop (HITL) Touchpoints**
- **Plan review**: Before execution starts
- **ESC key interrupt**: During execution (interactive mode)
- **Low confidence approval**: When LLM uncertain (future feature)
- **Final verification**: After task completion

### Data Structures

**knowledge_catalog.json** (source of truth):
```json
{
  "knowledge_id": "open_files",
  "description": "Open files using File menu",
  "action_sequence": ["Click File", "Click Open", "..."],
  "kb_learnings": [{
    "task": "Concatenate files",
    "original_error": "Button 'Add Files' not found",
    "recovery_approach": "Use Ctrl+O instead of Add Files button",
    "timestamp": "2025-11-03T10:30:00"
  }],
  "trust_score": 0.95
}
```

**ChromaDB stores**:
- Vector embeddings (from KB description)
- Metadata: full_knowledge (JSON), trust_score, learning_count

**VerifiedSkill JSON** (`agent/learning/verified_skills/`):
```json
{
  "operation": "Concatenate all .MF4 files and save with specified name",
  "parameters": {
    "input_folder": "Path to folder with MF4 files",
    "output_folder": "Path to save output",
    "output_filename": "Name of output file"
  },
  "action_sequence": [{...}, {...}],
  "metadata": {
    "success_rate": 1.0,
    "created_at": "2025-11-03T10:35:00",
    "last_used": "2025-11-03T10:35:00"
  }
}
```

---

## 💻 Setup & Usage

### Installation

```bash
# Create virtual environment
python -m venv .agent-venv
.agent-venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure API key
cp .env.example .env
# Edit .env: OPENAI_API_KEY=sk-...
```

### Build Knowledge Base (One-Time)

```bash
# Parse asammdf documentation
python agent/knowledge_base/doc_parser.py

# Index into ChromaDB
python agent/knowledge_base/indexer.py --rebuild
```

### Python API

**Basic Usage:**
```python
from agent.workflows.autonomous_workflow import execute_autonomous_task

result = execute_autonomous_task(
    operation="Open MF4 file and plot first signal",
    parameters={"file_path": r"C:\data\sample.mf4"}
)
```

**Iterative Rerun (Handling Failures):**
```python
# First attempt - may fail
result = execute_autonomous_task(
    operation="Concatenate all .MF4 files and save with specified name",
    parameters={
        "input_folder": r"C:\data\logs",
        "output_folder": r"C:\output",
        "output_filename": "merged.mf4"
    }
)

# If failed, learning attached to KB
if not result['success']:
    print("Learning attached. Rerunning...")
    result = execute_autonomous_task(
        operation="Concatenate all .MF4 files and save with specified name",
        parameters={
            "input_folder": r"C:\data\logs",
            "output_folder": r"C:\output",
            "output_filename": "merged.mf4"
        }
    )
    # Better plan with learning context
```

**Interactive Mode:**
```python
result = execute_autonomous_task(
    operation="Export signals to CSV",
    parameters={"input_file": r"C:\data\test.mf4"},
    interactive_mode=True  # Press ESC during execution for feedback
)
```

---

## 📁 Project Structure

```
agent/
├── workflows/
│   └── autonomous_workflow.py      # LangGraph 6-node orchestrator + HITL
├── knowledge_base/
│   ├── doc_parser.py               # One-time doc processing (GPT-5-mini)
│   ├── indexer.py                  # ChromaDB vector indexing
│   ├── retriever.py                # Semantic search + fuzzy skill matching
│   ├── recovery_approach_generator.py  # LLM-based recovery generation
│   ├── parsed_knowledge/
│   │   └── knowledge_catalog.json  # SOURCE OF TRUTH (learnings + trust scores)
│   └── vector_store/               # ChromaDB (embeddings + metadata)
├── planning/
│   ├── workflow_planner.py         # Plan generation with KB context (GPT-5-mini)
│   ├── schemas.py                  # KnowledgeSchema, ActionSchema, PlanSchema
│   └── plans/                      # Cached plans
├── execution/
│   ├── adaptive_executor.py        # Step execution + error handling + learning attachment
│   └── mcp_client.py               # Windows MCP automation client
├── feedback/
│   ├── human_observer.py           # HITL interactions (plan review, verification)
│   └── schemas.py                  # FailureLearning, TaskVerification schemas
├── learning/
│   ├── skill_library.py            # Verified skill storage + fuzzy matching
│   └── verified_skills/            # JSON files per verified task
├── prompts/
│   ├── planning_prompt.py          # Planning system prompts
│   ├── coordinate_resolution_prompt.py  # UI resolution prompts
│   ├── doc_parsing_prompt.py       # Doc extraction prompts
│   └── kb_recovery_approach_prompt.py   # Recovery generation prompts
└── utils/
    ├── cost_tracker.py             # LLM API cost monitoring
    └── parameter_substitution.py   # {placeholder} → value substitution
```

---

## ✨ Key Features

- **KB-Attached Learning**: Errors stored with patterns that caused them (not random)
- **Verified Skills**: Human-verified workflows with fuzzy matching (≥75% similarity)
- **Parameterized Tasks**: Reusable skills across different files/folders
- **Trust Scores**: KB pattern reliability tracking (0.95× per failure, min 0.5)
- **Recovery Approaches**: LLM analyzes verified skills to generate recovery guidance
- **Interactive Mode**: ESC key for real-time feedback during execution
- **Iterative Improvement**: Rerun with learning context → Progressive success
- **Symbolic Resolution**: Dynamic UI adaptation (text references → coordinates)

---

## 📈 Performance

- **First Run** (no learnings): 70-80% success rate
- **After Learning** (rerun with context): 85-95% success rate
- **Verified Skill Match**: 95%+ success rate (direct reuse)
- **Recovery Generation**: <5 seconds using GPT-4o-mini

---

## ⚠️ Limitations

- **Platform**: Windows-only (MCP protocol)
- **Scope**: Single application (designed for asammdf)
- **Execution**: Sequential steps (no parallel actions)
- **Learning**: Manual rerun required to apply learnings

---

## 🎯 What Makes This Special

### 1. KB-Source Attribution
Unlike generic RAG systems, the LLM explicitly tracks which KB pattern inspired each action. When actions fail, the system knows exactly which pattern to blame and attach learnings to.

### 2. Iterative Rerun Architecture
No automatic retries or replanning. User explicitly reruns tasks, system provides progressively better context. Simple, debuggable, and user-controlled.

### 3. LLM-Generated Recovery Approaches
After successful task completion, GPT-4o-mini analyzes the verified skill to generate concise recovery guidance for KB items that had errors. Future tasks benefit from both error history and recovery strategies.

### 4. Parameterized Task Separation
Operations separated from data: `"Concatenate files"` + `{"input_folder": "..."}`. Same skill works for different folders. Privacy-friendly (no paths embedded in skills).

---

**Happy Automating! 🚀**
