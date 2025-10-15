# asammdf Agent

**Autonomous GUI automation agent** - give it a task in natural language, it controls the asammdf GUI autonomously.

## Quick Start

```python
from agent.workflows.autonomous_workflow import execute_autonomous_task

result = execute_autonomous_task(
    "Concatenate all MF4 files in C:\\data and export to Excel"
)
```

## What It Does

```
Natural Language Task
        ↓
RAG Retrieval (ChromaDB) → AI Planning (GPT-5-mini) → Adaptive Execution (GPT-4o-mini) → Auto-Recovery
        ↓
    Success
```

**5-Phase Autonomous System:**
1. **RAG Retrieval** - Semantic search finds relevant documentation patterns
2. **AI Planning** - Generates MCP tool sequences from knowledge context
3. **Adaptive Execution** - Resolves UI elements dynamically (no hardcoded coordinates)
4. **Self-Recovery** - Auto-detects failures, replans with KB context, continues
5. **Orchestration** - LangGraph state machine with bounded retry/replan logic

## Core Technologies

| Component | Stack | Purpose |
|-----------|-------|---------|
| **Knowledge Base** | ChromaDB + sentence-transformers | Semantic search over docs |
| **Planning** | GPT-5-mini + OpenAI API | Generates MCP tool plans |
| **Execution** | GPT-4o-mini + MCP Protocol | Resolves UI elements dynamically |
| **Recovery** | Plan tracking + replanning | Auto-recovery with KB context |
| **Orchestration** | LangGraph | State machine with retry/replan |

## Example Workflow

**Task:** "Concatenate all MF4 files in C:\data and save as output.mf4"

### Phase 1: RAG Retrieval (<1s)
```
Query → ChromaDB → top-5 patterns: concatenate_files, open_folder, save_file
```

### Phase 2: AI Planning (2-5s)
```
GPT-5-mini + knowledge patterns → 28-step MCP tool plan:
  1. State-Tool {"use_vision": false}
  2. Switch-Tool {"name": "asammdf"}
  3. Click-Tool {"loc": ["last_state:menu:File"], ...}
  ...
```

### Phase 3: Adaptive Execution (~500ms/element)
```
Step 1: State-Tool → captures UI → caches
Step 2: Switch-Tool → activates window
Step 3: Click-Tool → GPT resolves ["last_state:menu:File"] → [120, 30] → clicks
...
Step 15: Fails (element not found)
```

### Phase 4: Auto-Recovery (3-8s)
```
Failure detected → saves snapshot → summarizes progress (14 done, 1 failed, 13 pending)
→ KB query: "concatenate button" → 3 patterns
→ GPT generates recovery plan (10 steps) with reasoning
→ Merges: 14 completed + 10 new = 24 total
→ Resumes from step 15 → Success!
```

## Key Features

✅ **Documentation-driven** - GPT extracts knowledge from docs (no hardcoding)
✅ **Adaptive** - GPT interprets intent, finds alternative UI elements
✅ **Self-healing** - Auto-replans on failures (up to 3 attempts)
✅ **State-aware** - Caches UI state for dynamic coordinate resolution
✅ **Versioned plans** - `Plan_0`, `Plan_1` with merge logic
✅ **Centralized prompts** - All LLM prompts in dedicated modules for easy iteration
✅ **Cost tracking** - Real-time API cost monitoring per component
✅ **Production-ready** - Error handling, logging, timestamped snapshots

## Architecture

```
agent/
├── workflows/autonomous_workflow.py    # LangGraph orchestrator (6-node state machine)
├── prompts/                            # Centralized LLM prompts
│   ├── planning_prompt.py              # Plan generation prompts
│   ├── recovery_prompt.py              # Replanning prompts
│   ├── coordinate_resolution_prompt.py # UI element resolution prompts
│   └── doc_parsing_prompt.py           # Documentation extraction prompts
├── utils/
│   └── cost_tracker.py                 # API cost tracking & reporting
├── rag/
│   ├── doc_parser.py                   # GPT extracts knowledge from docs
│   └── knowledge_retriever.py          # ChromaDB semantic search
├── planning/
│   ├── workflow_planner.py             # GPT-5-mini generates plans
│   ├── plan_recovery.py                # Replanning with KB context
│   └── schemas.py                      # Pydantic models
├── execution/
│   ├── mcp_client.py                   # MCP protocol client (async)
│   └── adaptive_executor.py            # GPT-4o-mini resolves UI elements
└── knowledge_base/
    ├── json/knowledge_catalog.json     # Extracted documentation patterns
    └── vector_store_gpt5_mini/         # ChromaDB database
```

## Components Deep Dive

### 1. Knowledge Extraction (`doc_parser.py`)
GPT parses asammdf docs → structured JSON patterns:
```json
{
  "knowledge_id": "concatenate_mf4",
  "description": "Concatenate multiple MF4 files",
  "ui_location": "Multiple files tab",
  "action_sequence": ["select_tab", "add_files", "set_mode", "run"]
}
```

### 2. RAG Retrieval (`knowledge_retriever.py`)
- ChromaDB + sentence-transformers (`all-MiniLM-L6-v2`)
- Semantic search returns top-K patterns for any task
- <1s retrieval time

### 3. AI Planning (`workflow_planner.py`)
- GPT-5-mini generates MCP tool sequences using knowledge context
- Validates against available MCP tools
- Caches plans with versioning (`Plan_0`, `Plan_1`, ...)
- 2-5s planning time

### 4. Adaptive Execution (`adaptive_executor.py`)
- **Symbolic resolution**: `["last_state:button:Save"]` → GPT resolves to coordinates
- **Intent-based**: If exact match fails, finds alternatives
- **Context-aware**: Uses previous actions for interpretation
- ~500ms per element

### 5. Plan Recovery (`plan_recovery.py`)
7-step replanning workflow:
1. Tracks execution state in plan JSON
2. Saves timestamped snapshots on failure
3. Summarizes: completed steps vs pending goal
4. Retrieves KB knowledge for failed actions
5. Generates recovery plan with reasoning
6. Merges completed + new steps
7. Continues execution automatically

### 6. LangGraph Orchestration (`autonomous_workflow.py`)
6-node state machine:
- `retrieve_knowledge` → RAG search
- `generate_plan` → GPT planning
- `validate_plan` → Tool validation
- `execute_step` → Adaptive execution
- `verify_step` → Success/failure check + replan trigger
- `handle_error` → Retry logic

**Routing**: Success → next | Failure → retry (2x) → replan (3x) → abort

### 7. Centralized Prompts (`prompts/`)
All LLM prompts in dedicated modules:
- `planning_prompt.py` - Plan generation (system + user prompts)
- `recovery_prompt.py` - Replanning with failure analysis
- `coordinate_resolution_prompt.py` - UI element coordinate resolution
- `doc_parsing_prompt.py` - Knowledge extraction from documentation

**Benefits**: Single source of truth, easy A/B testing, version control

### 8. Cost Tracking (`utils/cost_tracker.py`)
Automatic API cost monitoring:
- Tracks all OpenAI API calls with token counts
- Component breakdown (planning, recovery, resolution, doc_parsing)
- Model breakdown (gpt-5-mini, gpt-4o-mini)
- Export to JSON for analysis
- Real-time cost visibility during execution

## Performance

- Knowledge retrieval: <1s
- Plan generation: 2-5s
- Element resolution: ~500ms
- Total workflow: 10-60s (task-dependent)

## What Makes This Special

1. **Documentation-Driven**: No hardcoded actions - everything from GPT-parsed docs
2. **Adaptive Resolution**: GPT interprets intent, finds UI alternatives
3. **Self-Healing**: Auto-replans with KB context on failures
4. **State-Aware**: Caches UI for dynamic coordinates
5. **Incremental Planning**: Merges completed work with recovery plans

## Setup

### 1. Install Dependencies
```bash
python -m venv .agent-venv
.agent-venv\Scripts\activate
pip install -r requirements.txt

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

### 3. Extract Knowledge (one-time)
```bash
python agent/rag/doc_parser.py
python agent/rag/knowledge_retriever.py --rebuild-index
```

### 4. Run
```bash
python agent/workflows/autonomous_workflow.py "Your task here"
```

## Usage Examples

### Simple Task
```python
from agent.workflows.autonomous_workflow import execute_autonomous_task

result = execute_autonomous_task("Open sample.mf4 and plot the first signal")
print(f"Success: {result['success']}")
```

### Complex Task
```python
result = execute_autonomous_task(
    "Concatenate all MF4 files in C:\\data\\logs and export to Excel"
)
print(f"Steps completed: {result['steps_completed']}")
```

### Custom Configuration
```python
from agent.workflows.autonomous_workflow import AutonomousWorkflow

workflow = AutonomousWorkflow(
    app_name="asammdf 8.6.10",
    max_retries=2,
    max_replan_attempts=3
)
result = await workflow.run("Your task")
```

### Cost Tracking
```python
from agent.utils.cost_tracker import get_global_tracker

# After workflow execution
tracker = get_global_tracker()
tracker.print_summary()  # Shows cost breakdown by component/model
tracker.save_to_file()   # Exports to cost_reports/cost_TIMESTAMP.json
```

## Limitations

- Windows-only (Windows UI Automation)
- Single application (designed for asammdf, extensible to others)
- Text-based UI state (no vision, can add GPT-4o vision)
- Sequential execution (no parallel actions)

## Future Enhancements

- Multi-app workflows
- Vision integration (screenshots)
- Verified skills library (learn from successes)
- Parallel execution
- Human-in-the-loop approval

## Key Achievements

✅ Fully autonomous (no human intervention)
✅ Knowledge-grounded (all actions from docs)
✅ Self-recovering (auto-replanning)
✅ Adaptive (dynamic UI resolution)
✅ Production-ready (error handling, logging)
✅ Extensible (add knowledge via doc parsing)
✅ Fast (<5s planning, <1s retrieval)
✅ Reliable (bounded retries, snapshots)

## Tech Stack Summary

- **RAG**: ChromaDB + sentence-transformers → semantic search
- **Planning**: GPT-5-mini (OpenAI API) → MCP tool sequences
- **Execution**: GPT-4o-mini → dynamic coordinate resolution
- **Recovery**: Plan tracking + KB-augmented replanning
- **Orchestration**: LangGraph → state machine with retry/replan logic
- **Prompts**: Centralized prompt management → easy iteration
- **Cost Tracking**: Per-call API cost monitoring → budget visibility
- **MCP Integration**: Windows-MCP server → 13+ GUI automation tools
- **Schemas**: Pydantic → type safety
- **Async**: nest_asyncio → event loop management

## Project Status

**Production-ready autonomous workflow** with:
- Complete agentic loop (learn → plan → execute → recover)
- No hardcoded logic (documentation-driven)
- Adaptive recovery (KB-augmented replanning)
- Production error handling (bounded retries, snapshots)

**Result**: Natural language → GUI automation with self-healing and zero hardcoding.
