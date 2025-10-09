# asammdf Agent

**Autonomous GUI automation agent** for the [asammdf](https://github.com/danielhrisca/asammdf) MDF/MF4 file viewer.

Give it a task in natural language (e.g., _"concatenate all MF4 files and export to Excel"_), and the agent **takes full control of the asammdf GUI**, autonomously interacting with it to complete your task:

1. 📖 **Retrieves skills** from documentation-based knowledge base (RAG)
2. 🧠 **Plans workflow** using Claude AI + retrieved skills
3. 🤖 **Takes control of asammdf GUI** and autonomously executes actions via MCP tools
4. 👁️ **Observes GUI state** in real-time using Windows UI Automation
5. ✅ **Verifies and recovers** from errors automatically

**Key Innovation:** Claude calls Windows-MCP tools directly through the Model Context Protocol (MCP), enabling true autonomous GUI control without hardcoded actions.

## Key Features

✨ **Autonomous GUI Control:**
- **Agent takes full control** of asammdf application GUI
- **Claude calls MCP tools directly** - no wrapper functions needed
- **Real-time GUI observation** using Windows UI Automation
- **Dynamic element discovery** - no hardcoded coordinates
- **Self-healing execution** with automatic retry and error recovery

🎯 **Intelligence Layer:**
- **Natural language task input** (_"concatenate MF4s and export"_)
- **RAG-based skill retrieval** from documentation knowledge base
- **Claude AI planning** - generates step-by-step execution plans
- **Document-grounded** - only uses features from official docs
- **Stateful orchestration** via LangGraph

🔧 **MCP Integration:**
- **Model Context Protocol (MCP)** - Claude calls Windows-MCP tools directly
- **Separate environments** - Agent (`.agent-venv`) + MCP Server (`.windows-venv`)
- **13+ GUI automation tools** available to Claude (click, type, state, drag, etc.)
- **No manual tool wrapping** - MCP protocol handles tool discovery and execution

## Quick Start

### 1. Setup Virtual Environments

This project uses **two separate virtual environments** to isolate dependencies:

#### Environment Architecture

- **`.agent-venv`** (Root Level): Contains agent dependencies (MCP client, Claude SDK, RAG tools)
- **`.windows-venv`** (Inside `tools/Windows-MCP/`): Contains GUI automation dependencies (pywinauto, uiautomation)

**Why Two Environments?**
- **Isolation**: GUI automation tools stay separate from agent logic
- **MCP Server Process**: The MCP client (running in `.agent-venv`) spawns the MCP server as a subprocess using `.windows-venv`'s Python interpreter
- **Cross-Process Communication**: MCP client and server communicate via stdio (JSON-RPC), allowing them to run in different Python environments

```bash
# Step 1: Create agent environment (root level)
python -m venv .agent-venv
.agent-venv\Scripts\activate
pip install -r requirements.txt

# Step 2: Create Windows-MCP environment (inside tools/Windows-MCP/)
cd tools\Windows-MCP
python -m venv .windows-venv
.windows-venv\Scripts\activate
pip install -e .
deactivate

# Step 3: Return to root
cd ..\..
```

### 2. Configure MCP Server

The `mcp_config.json` file is already configured to use `.windows-venv` for the MCP server:

```json
{
  "mcpServers": {
    "windows-mcp": {
      "command": "D:\\Work\\asammdf_agent\\tools\\Windows-MCP\\.windows-venv\\Scripts\\python.exe",
      "args": ["D:\\Work\\asammdf_agent\\tools\\Windows-MCP\\main.py"]
    }
  }
}
```

**How it works:**
1. Activate `.agent-venv` (agent environment)
2. MCP client reads `mcp_config.json`
3. MCP client spawns MCP server subprocess using `.windows-venv`'s Python
4. MCP server runs `main.py` with GUI automation tools loaded
5. Client and server communicate via stdio

### 3. Setup API Key
```bash
cp .env.example .env
# Edit .env and add: ANTHROPIC_API_KEY=sk-ant-...
```

### 4. Run Manual Workflow (asammdf GUI Control)

With `.agent-venv` activated, run manual workflows that control asammdf GUI:

```bash
.agent-venv\Scripts\activate
python examples\example_manual_workflow.py
```

**What happens:**
1. Script imports `manual_workflow.py` which uses MCP client
2. MCP client spawns MCP server subprocess (using `.windows-venv` Python)
3. Workflow sends MCP tool calls (Click-Tool, State-Tool, etc.) to server
4. Server executes GUI automation using pywinauto/uiautomation
5. Results flow back to workflow

**Example Output:**
```
================================================================================
Manual Workflow Example: Plot Signal from MF4
================================================================================
Environment: .agent-venv (MCP Client) → .windows-venv (MCP Server)
Approach: Hardcoded action sequence

[Step] Open MF4 file...
  → Switched to asammdf 8.6.10
  → Ctrl+O pressed
  → File dialog opened
  → Found file input at: [450, 320]
  → Typed filename: Discrete_deflate.mf4
  → Found Open button at: [820, 650]
  → File 'Discrete_deflate.mf4' loaded
  ✓ Open MF4 file completed

[Step] Drag signal 'ASAM.M.SCALAR.SBYTE.IDENTICAL.DISCRETE'...
  → Found signal at: [220, 485]
  → Dragging from (220, 485) to (670, 485)
  → Dragged 'ASAM.M.SCALAR.SBYTE.IDENTICAL.DISCRETE' to plot area
  ✓ Drag signal completed

[Step] Create plot...
  → Found OK button at: [735, 590]
  → Clicked OK button
  ✓ Create plot completed

✓ Manual workflow completed successfully!
```

### 5. Run Autonomous Workflow (Future)

For Claude-driven autonomous workflows:
```bash
.agent-venv\Scripts\activate
python examples\example_autonomous_workflow.py
```

**See [SETUP_GUIDE.md](SETUP_GUIDE.md) for detailed setup instructions.**

## Architecture

### High-Level Flow

```
User Task: "Plot signal from MF4 file"
    ↓
┌──────────────────────────────────────────────────────────────────┐
│  Agent Process (.agent-venv)                                     │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ Manual Workflow (manual_workflow.py)                       │  │
│  │  → Hardcoded action sequence                              │  │
│  │  → Calls: execute_tool('Click-Tool', loc=[x,y])           │  │
│  │            execute_tool('State-Tool', use_vision=False)    │  │
│  │            execute_tool('Type-Tool', text="file.mf4")      │  │
│  └────────────────────────────────────────────────────────────┘  │
│                          ↓                                       │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ MCP Client (mcp_client.py)                                 │  │
│  │  → Reads mcp_config.json                                   │  │
│  │  → Spawns MCP server subprocess (see below)                │  │
│  │  → Maintains ClientSession                                 │  │
│  │  → Forwards tool calls via stdio (JSON-RPC)                │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
                        ↓ stdio (JSON-RPC over pipes)
┌──────────────────────────────────────────────────────────────────┐
│  MCP Server Subprocess (.windows-venv - separate process)       │
│  Command: tools/Windows-MCP/.windows-venv/Scripts/python.exe    │
│  Args: tools/Windows-MCP/main.py                                │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ Windows-MCP Server (main.py)                               │  │
│  │  → Receives tool calls via stdin                           │  │
│  │  → Executes: State-Tool, Click-Tool, Type-Tool, etc.       │  │
│  │  → Returns results via stdout                              │  │
│  │                                                             │  │
│  │  Tools Available:                                          │  │
│  │  • State-Tool → Observe GUI (pywinauto)                    │  │
│  │  • Click-Tool → Click coordinates (pywinauto)              │  │
│  │  • Type-Tool → Type text (pywinauto)                       │  │
│  │  • Drag-Tool → Drag and drop (pywinauto)                   │  │
│  │  • Switch-Tool → Switch window focus                       │  │
│  │  • + 8 more automation tools                               │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
                        ↓ Windows UI Automation API
┌──────────────────────────────────────────────────────────────────┐
│  asammdf GUI (Controlled via UI Automation)                      │
│  → MCP Server reads UI state, clicks buttons, types text         │
│  → Real-time element discovery (no hardcoded coordinates)        │
└──────────────────────────────────────────────────────────────────┘
```

**Key Points:**
- **Two Python Processes**: Agent process (`.agent-venv`) and MCP server subprocess (`.windows-venv`)
- **Communication**: MCP client and server communicate via **stdio pipes** (JSON-RPC protocol)
- **Environment Isolation**: Agent dependencies stay in `.agent-venv`, GUI automation deps in `.windows-venv`
- **MCP Server Spawning**: Client reads `mcp_config.json` and spawns server using `.windows-venv`'s Python interpreter

### Key Integration Points

1. **Workflow ↔ MCP Client**: Manual workflow calls `execute_tool()` which wraps MCP client calls
2. **MCP Client ↔ MCP Server**: JSON-RPC over stdio, separate Python processes (`.agent-venv` ↔ `.windows-venv`)
3. **MCP Server ↔ GUI**: Windows UI Automation (pywinauto, uiautomation)
4. **Environment Isolation**: Agent runs in `.agent-venv`, MCP server runs in `.windows-venv` subprocess

### How MCP Client Spawns Server

When you run a workflow from `.agent-venv`:

```python
# In manual_workflow.py (running in .agent-venv)
from execution.mcp_client import get_mcp_client

client = get_mcp_client()
asyncio.run(client.connect('windows-mcp'))  # Spawns server subprocess
```

**What happens in `mcp_client.py`:**

1. **Read Config**: Loads `mcp_config.json` to get server command
   ```json
   {
     "command": "D:\\...\\tools\\Windows-MCP\\.windows-venv\\Scripts\\python.exe",
     "args": ["D:\\...\\tools\\Windows-MCP\\main.py"]
   }
   ```

2. **Spawn Subprocess**: Starts MCP server as separate process
   ```python
   # Simplified version of what happens
   server_params = StdioServerParameters(
       command=".windows-venv/Scripts/python.exe",
       args=["main.py"]
   )
   read, write = await stdio_client(server_params)  # Spawns subprocess
   ```

3. **Establish Session**: Creates ClientSession with stdio pipes
   ```python
   session = ClientSession(read, write)  # JSON-RPC over pipes
   await session.initialize()
   ```

4. **Tool Calls**: Forward tool calls to server via stdin
   ```python
   result = await session.call_tool('Click-Tool', {'loc': [450, 320]})
   # Sent via stdin → MCP server executes → Returns via stdout
   ```

### Project Structure

```
asammdf_agent/
├── .agent-venv/                         # Agent Python environment (root level)
│   └── ...                              # Agent dependencies (MCP client, Claude SDK, RAG)
├── agent/
│   ├── execution/
│   │   ├── mcp_client.py                # MCP client (spawns server, calls tools)
│   │   ├── claude_mcp_executor.py       # Claude + MCP integration ⭐
│   │   ├── action_primitives.py         # Legacy wrapper functions
│   │   └── state_based_executor.py      # State-based executor
│   ├── rag/
│   │   ├── doc_parser.py                # Auto skill extraction from docs
│   │   ├── skill_retriever.py           # RAG queries (ChromaDB)
│   │   ├── skill_catalog.json           # Extracted skills
│   │   └── vector_store/                # ChromaDB vector database
│   ├── planning/
│   │   ├── schemas.py                   # Pydantic models (Skills, Plans)
│   │   └── workflow_planner.py          # Claude-based planner
│   ├── workflows/
│   │   ├── autonomous_workflow.py       # LangGraph orchestrator
│   │   └── manual_workflow.py           # Manual workflow (uses MCP client)
├── examples/
│   ├── example_autonomous_workflow.py  # Autonomous examples
│   └── example_manual_workflow.py      # Manual examples
├── tools/
│   └── Windows-MCP/                     # MCP server package
│       ├── .windows-venv/               # MCP Server Python environment (nested)
│       │   └── ...                      # GUI automation deps (pywinauto, uiautomation)
│       ├── main.py                      # MCP server entry point
│       └── ...                          # MCP server implementation
├── mcp_config.json                      # MCP server configuration
├── SETUP_GUIDE.md                       # Detailed setup guide
└── requirements.txt                     # Agent dependencies
```

## Installation

### Prerequisites

- **Python 3.13+** (required by Windows-MCP)
- **Windows OS** (required for Windows UI Automation)
- **asammdf** application installed and accessible from command line

### Detailed Setup Steps

#### Step 1: Create Agent Environment (Root Level)

This environment contains agent dependencies (MCP client, ChromaDB, etc.):

```bash
# From project root
python -m venv .agent-venv
.agent-venv\Scripts\activate
pip install -r requirements.txt
```

**Dependencies installed:**
- `mcp` - MCP client SDK
- `anthropic` - Claude API client (for autonomous workflows)
- `chromadb` - Vector database for RAG
- `sentence-transformers` - Embeddings
- Other agent dependencies

#### Step 2: Create MCP Server Environment (Inside tools/Windows-MCP/)

This environment contains GUI automation dependencies:

```bash
# From project root, navigate to Windows-MCP
cd tools\Windows-MCP

# Create venv inside Windows-MCP directory
python -m venv .windows-venv
.windows-venv\Scripts\activate

# Install Windows-MCP in editable mode
pip install -e .

# Deactivate and return to root
deactivate
cd ..\..
```

**Dependencies installed (in .windows-venv):**
- `pywinauto` - Windows GUI automation
- `uiautomation-py` - UI Automation API wrapper
- `mcp` - MCP server SDK
- Other GUI automation tools

#### Step 3: Update mcp_config.json with Absolute Paths

Edit `mcp_config.json` to point to your `.windows-venv` Python:

```json
{
  "mcpServers": {
    "windows-mcp": {
      "command": "D:\\Work\\asammdf_agent\\tools\\Windows-MCP\\.windows-venv\\Scripts\\python.exe",
      "args": ["D:\\Work\\asammdf_agent\\tools\\Windows-MCP\\main.py"]
    }
  }
}
```

**Replace paths with your actual project location.**

#### Step 4: Verify Installation

From **agent environment** (`.agent-venv`), test MCP connection:

```bash
# Activate agent environment
.agent-venv\Scripts\activate

# Run manual workflow example
python examples\example_manual_workflow.py
```

**Expected output:**
- MCP server spawns successfully
- Workflow controls asammdf GUI
- Signal is plotted

If you see "RuntimeError: Attempted to exit cancel scope in a different task", ensure you're using the **fixed version** of `manual_workflow.py` with the global event loop fix.

## Usage Examples

### Claude + MCP Direct Execution (Recommended)

**Agent takes full control** of the GUI - Claude calls MCP tools directly:

```python
from agent.execution.claude_mcp_executor import execute_with_claude_mcp

# Simple GUI task
results = execute_with_claude_mcp("Open Notepad and type 'Hello World'")

# asammdf-specific task
results = execute_with_claude_mcp(
    "Open asammdf, load sample.mf4, and plot the first signal"
)

print(f"Success: {results['success']}")
print(f"Claude's response: {results['response']}")
print(f"Conversation turns: {results['turns']}")
```

**What happens:**
1. MCP server starts in `.windows-venv`
2. Claude receives 13+ MCP tools (State-Tool, Click-Tool, etc.)
3. **Claude autonomously controls the GUI** by calling tools
4. Agent forwards tool calls to MCP server
5. Results flow back to Claude

### RAG-Powered Autonomous Workflow

Combines **knowledge base retrieval** with **Claude + MCP execution**:

```python
from agent.workflows.autonomous_workflow import execute_autonomous_task

# Retrieves relevant skills from docs, then executes
results = execute_autonomous_task("Open an MF4 file called sample.mf4")

# Complex multi-step task
results = execute_autonomous_task(
    "Concatenate all MF4 files in C:\\data folder and export to Excel"
)

print(f"Success: {results['success']}")
print(f"Steps completed: {results['steps_completed']}")
```

### Legacy: Manual Workflow

Hardcoded action sequences (pre-MCP approach):

```python
from agent.workflows.manual_workflow import plot_signal_from_mf4

results = plot_signal_from_mf4(
    mf4_file="Discrete_deflate.mf4",
    signal_name="ASAM.M.SCALAR.SBYTE.IDENTICAL.DISCRETE"
)
```

### Running Interactive Examples

**Autonomous Examples** (requires `.agent-venv`):
```bash
.agent-venv\Scripts\activate
python examples\example_autonomous_workflow.py
```

Choose from:
1. Claude + MCP Direct (Simple GUI task)
2. RAG + Autonomous (Open MF4 file)
3. RAG + Autonomous (Concatenate & Export)
4. Custom Task (Your own prompt)

**Manual Examples** (requires `.agent-venv` - MCP client spawns server):
```bash
.agent-venv\Scripts\activate
python examples\example_manual_workflow.py
```

Choose from:
1. Plot Signal from MF4 (hardcoded workflow using MCP tools)

## How It Works

### 1. Automatic Skill Extraction (One-time Setup)

`doc_parser.py` uses Claude to parse asammdf documentation:

**Input:** HTML from https://asammdf.readthedocs.io/en/stable/gui.html
**Process:** Claude extracts 15-20 GUI skills with structured output
**Output:** `agent/skills/json/skill_catalog.json` with skills like `concatenate_mf4`, `export_excel`

Example skill:
```json
{
  "skill_id": "concatenate_mf4",
  "description": "Concatenate multiple MF4 files into one",
  "ui_location": "Multiple files tab",
  "action_sequence": ["select_tab", "add_files", "set_mode", "run"],
  "doc_citation": "https://asammdf.readthedocs.io/..."
}
```

### 2. Task Planning (RAG + LLM)

When you give a task:

1. **RAG Retrieval:** ChromaDB finds top-5 relevant skills via semantic search
2. **Plan Generation:** Claude generates step-by-step plan using ONLY those skills
3. **Validation:** Ensures all skill IDs exist and have required arguments
4. **Output:** Validated plan with doc citations

### 3. Autonomous Execution (Claude + MCP)

**Key Innovation:** Claude calls MCP tools directly via the Anthropic API.

**Execution Flow:**

1. **Initialize MCP Client**
   ```python
   from agent.execution.claude_mcp_executor import ClaudeMCPExecutor

   executor = ClaudeMCPExecutor()
   # Fetches available tools from Windows-MCP server
   # Tools: State-Tool, Click-Tool, Type-Tool, Switch-Tool, etc.
   ```

2. **Claude Takes Control**
   ```python
   response = client.messages.create(
       model="claude-sonnet-4-20250514",
       tools=mcp_tools,  # ← MCP tools passed to Claude
       messages=[{"role": "user", "content": task}]
   )
   ```

3. **Claude Calls MCP Tools Autonomously**
   - Claude decides which tools to use and when
   - Example: `State-Tool` → observes GUI → `Click-Tool` → clicks button
   - Agent forwards tool calls to Windows-MCP server
   - Results flow back to Claude for next decision

4. **Real-time GUI Control**
   - Windows-MCP server executes GUI actions in `.windows-venv`
   - No hardcoded coordinates - dynamic element discovery
   - Self-healing: Claude observes failures and retries

**Example Tool Call by Claude:**
```json
{
  "name": "Click-Tool",
  "input": {
    "loc": [450, 320],
    "button": "left",
    "clicks": 1
  }
}
```

Agent forwards to MCP server → GUI action executed → Result returned to Claude

### 4. Verification & Recovery

- After each step: Check success/failure
- On failure: Retry up to 2 times
- On max retries: Abort with detailed error report

### Windows-MCP Tools (Called Directly by Claude)

The agent provides Claude with 13+ MCP tools for autonomous GUI control:

**Observation Tools:**
- `State-Tool` - Get current UI state: windows, buttons, fields, coordinates
- `Clipboard-Tool` - Read/write system clipboard

**Action Tools:**
- `Click-Tool` - Click at coordinates (left/right/middle, single/double/triple)
- `Type-Tool` - Type text into fields (with auto-clear and enter options)
- `Drag-Tool` - Drag and drop operations
- `Key-Tool` - Press individual keys (Enter, Tab, Arrow keys, etc.)
- `Shortcut-Tool` - Keyboard shortcuts (Ctrl+O, Alt+Tab, etc.)
- `Scroll-Tool` - Scroll vertical/horizontal

**Window Management:**
- `Switch-Tool` - Switch focus to application by name
- `Launch-Tool` - Launch applications from Start Menu
- `Resize-Tool` - Resize/move windows

**Utilities:**
- `Wait-Tool` - Wait for specified duration
- `Scrape-Tool` - Fetch and convert web content to markdown

**Claude calls these tools autonomously** - the agent just:
1. Fetches tool definitions from MCP server (`list_tools()`)
2. Passes them to Claude via Anthropic API
3. Forwards Claude's tool calls to MCP server (`call_tool()`)
4. Returns results back to Claude

## Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **🤖 AI Orchestration** | **Claude 4 Sonnet** | Task planning & autonomous GUI control |
| **🔧 Tool Protocol** | **MCP (Model Context Protocol)** | Claude ↔ MCP Server communication |
| **🖥️ GUI Automation** | **Windows-MCP Server** | Windows UI Automation (pywinauto, uiautomation) |
| **📊 Knowledge Base** | **ChromaDB** | Vector database for skill retrieval |
| **🧠 Embeddings** | **sentence-transformers** | Semantic skill search |
| **🔄 Workflow Engine** | **LangGraph** | Stateful orchestration with retry logic |
| **📝 Schema Validation** | **Pydantic** | Type-safe data models |
| **🌐 API Client** | **Anthropic SDK** | Claude API with tool calling |
| **📖 Doc Parsing** | **BeautifulSoup** | Extract skills from HTML docs |

### Key Technology Integrations

1. **Model Context Protocol (MCP)**
   - Standardized protocol for LLM ↔ Tool communication
   - Claude calls GUI tools without manual wrapper functions
   - Server runs in isolated Python environment (`.windows-venv`)

2. **RAG (Retrieval-Augmented Generation)**
   - ChromaDB stores skill embeddings from documentation
   - Semantic search retrieves relevant skills for each task
   - Grounds Claude's planning in actual documented features

3. **Windows UI Automation**
   - Real-time GUI state observation (`State-Tool`)
   - Dynamic element discovery (coordinates, control types)
   - Cross-process GUI control (agent controls asammdf)

## Extending the Agent

### Add New Skills

**Option 1:** Re-extract from updated docs
```bash
python agent/rag/doc_parser.py
python agent/rag/skill_retriever.py --rebuild-index
```

**Option 2:** Manually add to `agent/skills/json/skill_catalog.json`
```json
{
  "skill_id": "your_skill",
  "description": "What it does",
  "ui_location": "Tab/menu location",
  "action_sequence": ["step1", "step2"],
  "prerequisites": [],
  "output_state": "expected result",
  "doc_citation": "URL"
}
```

### Implement Custom Executors

Add methods to `agent/execution/state_based_executor.py`:

```python
def _execute_your_skill(self, args: Dict[str, Any]) -> str:
    """Custom skill implementation"""
    switch_tool(self.app_name)
    wait_tool(1)

    # Use state_tool to find GUI elements
    state_output = state_tool(use_vision=False)
    # ... your logic here

    return "Success message"
```

## Troubleshooting

### Common Issues

1. **Import errors** - Ensure Windows-MCP is installed in the correct virtual environment
2. **Element not found** - Increase wait times in `wait_tool()` calls
3. **Wrong element clicked** - Adjust `fuzzy_threshold` or add `control_type` filters
4. **asammdf not launching** - Verify asammdf is in PATH and can be launched from command line

### Debug Mode

Add print statements or logging to see which elements are discovered:

```python
state_output = state_tool(use_vision=False)
print(state_output)  # See all available UI elements
```

## Contributing

Contributions are welcome! Areas for improvement:

- Additional workflows (export data, batch processing, etc.)
- Better error handling and recovery
- Configuration file support
- Multi-file operations
- Integration with other MDF tools

## License

This project follows the license terms of its dependencies. See LICENSE file for details.

## Acknowledgments

- **Windows-MCP** - https://github.com/CursorTouch/Windows-MCP
- **asammdf** - https://github.com/danielhrisca/asammdf
- **pywinauto** - Windows GUI automation library
- **uiautomation** - Windows UI Automation wrapper

## Support

For issues and questions:
- File an issue on the GitHub repository
- Check Windows-MCP documentation for tool-specific questions
- Consult asammdf documentation for application-specific details



# Setup Guide: Autonomous asammdf Agent

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure API Key

Create a `.env` file from the template:

```bash
cp .env.example .env
```

Edit `.env` and add your Anthropic API key:

```
ANTHROPIC_API_KEY=sk-ant-...
```

Get your API key from: https://console.anthropic.com/

### 3. Extract Skills from Documentation

This is a **one-time setup** that automatically parses the asammdf documentation and builds the skill catalog:

```bash
python agent/rag/doc_parser.py
```

This will:
- Fetch the asammdf GUI documentation
- Use Claude to extract all GUI skills
- Save to `agent/skills/json/skill_catalog.json`

Expected output:
```
Fetching documentation from https://asammdf.readthedocs.io/en/stable/gui.html...
Extracting skills using Claude claude-sonnet-4-20250514...
Extracted 15-20 skills:
  - open_file: Open an MF4 file
  - concatenate_mf4: Concatenate multiple MF4 files
  - export_excel: Export data to Excel format
  ...
Saved 20 skills to agent/skills/json/skill_catalog.json
✓ Successfully built skill catalog with 20 skills
```

### 4. Index Skills in Vector Database

```bash
python agent/rag/skill_retriever.py --rebuild-index
```

This creates a ChromaDB vector database at `agent/skills/vector_store/` for fast semantic search.

### 5. Run Examples

#### Option A: Interactive Examples

```bash
python examples/example_autonomous_workflow.py
```

Choose:
- `1` - Manual workflow (hardcoded steps from your initial work)
- `2` - Autonomous workflow (simple task)
- `3` - Autonomous workflow (concatenate & export)

#### Option B: Direct Autonomous Task

```bash
python agent/core/autonomous_workflow.py "Open an MF4 file called sample.mf4"
```

## Architecture

```
User Task ("concatenate MF4s")
    ↓
autonomous_workflow.py (LangGraph orchestrator)
    ↓
┌─────────────────────────────────────────────┐
│ 1. Retrieve Skills (RAG from documentation) │
│ 2. Generate Plan (Claude + constraints)    │
│ 3. Validate Plan (schema + skill checks)   │
│ 4. Execute Steps (state_tool + Windows-MCP)│
│ 5. Verify Results (state checks)           │
└─────────────────────────────────────────────┘
    ↓
Success / Retry / Fail
```

## Directory Structure

```
agent/
├── workflows/
│   ├── manual_workflow.py           # Original hardcoded workflow
│   └── autonomous_workflow.py       # LangGraph orchestrator
├── rag/
│   ├── doc_parser.py                # Automatic skill extraction
│   └── skill_retriever.py           # RAG queries
├── skills/
│   ├── json/
│   │   ├── skill_catalog.json       # Extracted skills (generated)
│   │   └── skill_catalog_gpt5.json  # GPT-5 extracted skills
│   └── vector_store/                # ChromaDB (generated)
├── planning/
│   ├── schemas.py                   # Pydantic models
│   └── workflow_planner.py          # Claude-based planner
├── execution/
│   ├── action_primitives.py         # Primitive GUI actions
│   └── state_based_executor.py      # Generic action interpreter
examples/
├── example_autonomous_workflow.py   # Autonomous examples
└── example_manual_workflow.py       # Manual examples
```

## How It Works

### 1. Skill Extraction (One-time)

`doc_parser.py` uses Claude to parse the asammdf GUI documentation:

**Input:** HTML documentation
**Process:** Claude extracts skills with structured output
**Output:** `agent/skills/json/skill_catalog.json` with 15-20 GUI skills

Example skill:
```json
{
  "skill_id": "concatenate_mf4",
  "description": "Concatenate multiple MF4 files into one",
  "ui_location": "Multiple files tab",
  "action_sequence": [
    "select_tab('Multiple files')",
    "add_files",
    "set_mode('Concatenate')",
    "run"
  ],
  "prerequisites": ["app_open"],
  "output_state": "concatenated_file_loaded",
  "doc_citation": "https://asammdf.readthedocs.io/..."
}
```

### 2. Task Planning

**Input:** Natural language task
**Process:**
1. RAG retrieves top-5 relevant skills from vector DB
2. Claude generates step-by-step plan using ONLY those skills
3. Validator ensures all skill IDs exist and have required args

**Output:** Validated execution plan with doc citations

### 3. Execution

**Input:** Plan (list of actions)
**Process:**
- For each action, `state_based_executor.py`:
  1. Activates asammdf window
  2. Uses `state_tool()` to get UI elements
  3. Parses element coordinates
  4. Clicks/types/drags via Windows-MCP tools

**Output:** Execution results per step

### 4. Verification & Recovery

- After each step: Check success/failure
- On failure: Retry up to 2 times (configurable)
- On max retries: Abort with error report

## Troubleshooting

### "Skill catalog not found"

Run the extraction:
```bash
python agent/rag/doc_parser.py
```

### "ANTHROPIC_API_KEY not found"

Create `.env` file with your API key:
```bash
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env
```

### "No skills retrieved"

Rebuild the vector index:
```bash
python agent/rag/skill_retriever.py --rebuild-index
```

### "Button not found" errors

The GUI structure may have changed. Options:
1. Check application version matches (asammdf 8.6.x)
2. Increase wait times in `state_based_executor.py`
3. Re-extract skills with updated documentation

## Next Steps

### Add New Skills

1. Re-run extraction (if docs updated):
   ```bash
   python agent/rag/doc_parser.py
   ```

2. Or manually add to `agent/skills/json/skill_catalog.json`

3. Rebuild index:
   ```bash
   python agent/rag/skill_retriever.py --rebuild-index
   ```

### Implement Custom Executors

Add methods to `state_based_executor.py`:

```python
def _execute_your_skill(self, args: Dict[str, Any]) -> str:
    """Your custom skill implementation"""
    # ... use state_tool + Windows-MCP
    return "Success message"
```

### Test New Tasks

```bash
python agent/core/autonomous_workflow.py "Your custom task description"
```

## Performance Tips

- **First run:** ~30s (model loading + vector DB init)
- **Subsequent runs:** ~10-15s per task
- **Skill retrieval:** <1s (ChromaDB in-memory)
- **Plan generation:** 2-5s (Claude API)

## Security Notes

- API keys stored in `.env` (gitignored)
- No credentials passed to LLM (only task descriptions)
- Windows-MCP runs locally (no network except Anthropic API)

## References

- asammdf docs: https://asammdf.readthedocs.io/en/stable/gui.html
- LangGraph: https://github.com/langchain-ai/langgraph
- Windows-MCP: https://github.com/CursorTouch/Windows-MCP
- Claude API: https://docs.anthropic.com/


# Architecture: Generic Action Execution

## Design Philosophy

The autonomous workflow system is **truly documentation-driven**, meaning:

✅ **No hardcoded task implementations** - All actions are determined by skill catalog
✅ **Generic action interpreter** - Executor parses `action_sequence` dynamically
✅ **Extensible without code changes** - Add new skills via documentation extraction
✅ **Primitive-based** - Complex actions built from reusable primitives

---

## How It Works

### 1. Task → Plan

```
User: "Concatenate MF4 files and export to Excel"
    ↓
Planner queries RAG → retrieves skills
    ↓
Claude generates plan:
{
  "plan": [
    {"skill_id": "select_tab", "args": {"name": "Multiple files"}},
    {"skill_id": "add_files", "args": {"folder": "C:\\data"}},
    {"skill_id": "concatenate", "args": {}},
    {"skill_id": "export", "args": {"format": "Excel"}}
  ]
}
```

### 2. Plan → Execution

```
For each action in plan:
  1. Look up skill in catalog
  2. Get action_sequence from skill
  3. Substitute args into action_sequence
  4. Parse and execute each primitive
```

**Example:**

```json
// Skill from catalog
{
  "skill_id": "select_tab",
  "action_sequence": [
    "click_by_text('{name}', control_type='TabItem')",
    "wait(1)"
  ]
}

// Action from plan
{
  "skill_id": "select_tab",
  "args": {"name": "Multiple files"}
}

// Execution:
// Step 1: "click_by_text('{name}', control_type='TabItem')"
//         → substitute args → "click_by_text('Multiple files', control_type='TabItem')"
//         → parse → primitives.click_by_text('Multiple files', control_type='TabItem')
//         → execute → find element via state_tool → click
// Step 2: "wait(1)" → primitives.wait(1)
```

---

## Component Breakdown

### 1. Action Primitives (`action_primitives.py`)

**Purpose:** Library of atomic GUI operations

**Primitives:**
- `click_by_text(element_name, control_type, prefer_bottom)`
- `type_in_field(text, field_name, clear, press_enter)`
- `select_tab(tab_name)`
- `select_mode(mode_name)`
- `press_shortcut(keys)`
- `press_key(key)`
- `wait(seconds)`
- `click_button(button_name)`
- `drag_element(from_text, to_x_offset, to_y_offset)`
- `type_in_dialog(text, field_name)`

**Key Feature:** All primitives use `state_tool` for dynamic element discovery.

---

### 2. State-Based Executor (`state_based_executor.py`)

**Purpose:** Generic interpreter that executes `action_sequence` from skills

**Flow:**
```python
def execute_action(action, skill):
    for step in skill.action_sequence:
        # Substitute args
        step_with_args = substitute_args(step, action.args)
        # e.g., "click_button('{name}')" + {"name": "Export"}
        #    → "click_button('Export')"

        # Parse primitive
        primitive_func, args, kwargs = parse_primitive(step_with_args)
        # e.g., "click_button('Export')"
        #    → func=primitives.click_button, args=['Export'], kwargs={}

        # Execute
        primitive_func(*args, **kwargs)
```

**No Hardcoded Methods:**
- ❌ Old approach: `def _execute_open_file()`, `def _execute_export()`
- ✅ New approach: `def _execute_primitive(action_string)` - parses ANY action

---

### 3. Workflow Orchestrator (`autonomous_workflow.py`)

**Location:** `agent/workflows/autonomous_workflow.py`
**Purpose:** LangGraph state machine coordinating the full workflow

**Nodes:**
1. `retrieve_skills` - RAG query
2. `generate_plan` - Claude planning
3. `validate_plan` - Schema validation
4. `execute_step` - Generic executor
5. `verify_step` - State checks
6. `handle_error` - Retry logic

---

## Skill Catalog Format

Skills must define `action_sequence` with parseable primitive calls:

```json
{
  "skill_id": "concatenate_mf4",
  "description": "Concatenate multiple MF4 files",
  "ui_location": "Multiple files tab",
  "action_sequence": [
    "select_tab('Multiple files')",
    "click_button('Add files')",
    "wait(2)",
    "type_in_dialog('{folder}/*.mf4', field_name='File name')",
    "click_button('Open', prefer_bottom=True)",
    "select_mode('Concatenate')",
    "click_button('Run')",
    "wait(5)"
  ],
  "prerequisites": ["app_open"],
  "output_state": "concatenated_file_ready",
  "doc_citation": "https://asammdf.readthedocs.io/...",
  "parameters": {
    "folder": "str"
  }
}
```

**Key Points:**
- `{folder}` placeholder gets substituted with `action.args["folder"]`
- Each step is a primitive function call string
- Primitives support both positional and keyword arguments

---

## Adding New Capabilities

### Option 1: Add Primitive (for new GUI interaction pattern)

```python
# agent/execution/action_primitives.py

def your_new_primitive(self, arg1: str, arg2: int = 5) -> str:
    """Your primitive documentation"""
    switch_tool(self.app_name)
    # ... implementation using state_tool + Windows-MCP
    return "Success message"
```

Then use in skill `action_sequence`:
```json
"action_sequence": [
  "your_new_primitive('value', arg2=10)"
]
```

### Option 2: Add Skill (for new task)

Re-run documentation extraction:
```bash
python agent/rag/doc_parser.py
```

Claude will parse new GUI features and add skills automatically.

Or manually edit `agent/skills/json/skill_catalog.json`:
```json
{
  "skill_id": "your_new_skill",
  "action_sequence": [
    "click_button('Some Button')",
    "wait(2)",
    "type_in_field('data', field_name='Input')"
  ],
  ...
}
```

---

## Why This Matters

### ❌ Old Approach (Hardcoded)
```python
def _execute_open_file(self, args):
    # Hardcoded implementation
    press_shortcut(["ctrl", "o"])
    type_in_field(args["filename"])
    click_button("Open")
```

**Problems:**
- Can't handle new tasks without code changes
- Planner generates plan, but executor ignores it
- Not scalable

### ✅ New Approach (Generic)
```python
def execute_action(self, action, skill):
    # Reads action_sequence from skill
    for step in skill.action_sequence:
        self._execute_primitive(step)
```

**Benefits:**
- ✅ Handles any task defined in skill catalog
- ✅ Add new skills without touching executor code
- ✅ Truly documentation-driven
- ✅ Planner and executor are decoupled

---

## File Organization

```
agent/
├── workflows/
│   ├── manual_workflow.py         # Original (hardcoded sequences)
│   └── autonomous_workflow.py     # NEW: LangGraph orchestrator
│
├── execution/
│   ├── action_primitives.py       # NEW: Primitive action library
│   └── state_based_executor.py    # NEW: Generic interpreter
│
├── rag/
│   ├── doc_parser.py              # Extracts skills from docs
│   └── skill_retriever.py         # RAG queries
│
├── skills/
│   ├── json/
│   │   ├── skill_catalog.json     # Extracted skills
│   │   └── skill_catalog_gpt5.json # GPT-5 extracted skills
│   └── vector_store/              # ChromaDB vector database
│
└── planning/
    ├── schemas.py                 # Data models
    └── workflow_planner.py        # Claude-based planner
examples/
├── example_autonomous_workflow.py # Autonomous examples
└── example_manual_workflow.py     # Manual examples
```

**Why `autonomous_workflow.py` is in `workflows/`:**
- Consistency with `manual_workflow.py`
- Both are workflow entry points
- Clear separation: workflows orchestrate, execution executes

---

## Testing the Generic Executor

```bash
# Test primitive action parsing
python agent/execution/state_based_executor.py
```

Example test skill:
```python
test_skill = SkillSchema(
    skill_id="open_file",
    action_sequence=[
        "press_shortcut(['ctrl', 'o'])",
        "wait(2)",
        "type_in_dialog('{filename}', field_name='File name')",
        "click_button('Open', prefer_bottom=True)",
        "wait(2)"
    ],
    parameters={"filename": "str"}
)

test_action = ActionSchema(
    skill_id="open_file",
    args={"filename": "sample.mf4"}
)

executor.execute_action(test_action, test_skill)
```

Output:
```
[Executing] open_file with args {'filename': 'sample.mf4'}
  → press_shortcut(['ctrl', 'o'])
  → wait(2)
  → type_in_dialog('sample.mf4', field_name='File name')
  → click_button('Open', prefer_bottom=True)
  → wait(2)
✓ Completed 5 steps
```

---

## Summary

| Aspect | Before | After |
|--------|--------|-------|
| **Executor** | Hardcoded methods per task | Generic action interpreter |
| **Extensibility** | Requires code changes | Add skills to catalog |
| **Planning** | Plan generated but unused | Plan fully drives execution |
| **Scalability** | Limited to implemented tasks | Unlimited (any documented feature) |
| **Location** | `core/autonomous_workflow.py` | `workflows/autonomous_workflow.py` |

**Key Insight:** The executor doesn't "know" about tasks - it only knows primitives. The skill catalog bridges the gap between high-level tasks and low-level primitives.


# Autonomous Workflow Refactoring

## Overview

Refactored the autonomous workflow to use MCP client directly (same pattern as `manual_workflow.py`), eliminating unnecessary abstraction layers.

## Changes Made

### 1. Updated Schemas (`agent/planning/schemas.py`)

**ActionSchema** now includes:
- `tool_name`: MCP tool to execute (e.g., 'Click-Tool', 'State-Tool')
- `tool_arguments`: Arguments for the MCP tool
- `skill_id`: Kept for documentation/context purposes

**Before:**
```python
{
  "skill_id": "click_button",
  "args": {"name": "OK"},
  "doc_citation": "..."
}
```

**After:**
```python
{
  "skill_id": "click_button_ok",
  "tool_name": "Click-Tool",
  "tool_arguments": {"loc": [450, 300], "button": "left"},
  "doc_citation": "..."
}
```

### 2. Unified MCPClient (`agent/execution/mcp_client.py`)

Unified client that combines connection and execution functionality:
- Directly calls MCP tools via `call_tool(tool_name, arguments)`
- No string parsing or wrapper methods
- Centralized MCP client management
- Supports both async and sync interfaces

**Three interfaces:**
1. `call_tool_sync(tool_name, arguments)` - Sync tool execution (for manual workflows)
2. `call_tool(tool_name, arguments)` - Async tool execution (for async workflows)
3. `execute_action(action: ActionSchema)` - Wrapped execution (for autonomous workflows)

**Key methods:**
```python
def call_tool_sync(self, tool_name: str, arguments: Dict[str, Any] = None) -> Any:
    """Sync wrapper for manual workflows"""
    self.ensure_connected()
    return self._run_async(self.call_tool(tool_name, arguments))

def execute_action(self, action: ActionSchema) -> ExecutionResult:
    """Execute action for autonomous workflows"""
    self.ensure_connected()
    result = self._run_async(self.call_tool(action.tool_name, action.tool_arguments))
    return ExecutionResult(success=True, action=action.tool_name, evidence=output)
```

### 3. Updated WorkflowPlanner (`agent/planning/workflow_planner.py`)

**Planning prompt now:**
- Describes available MCP tools (State-Tool, Click-Tool, etc.)
- Instructs Claude to generate plans with actual MCP tool calls
- Emphasizes using State-Tool to discover UI coordinates dynamically

**Validation:**
- Validates tool_name against known MCP tools
- Validates required arguments for each tool type
- skill_id is now just for documentation (warning if not in catalog)

### 4. Updated AutonomousWorkflow (`agent/workflows/autonomous_workflow.py`)

- Replaced `MCPExecutor` with unified `MCPClient`
- Removed skill lookup logic (no longer needed)
- Simplified execution node to directly call `client.execute_action(action)`
- Uses `call_tool_sync()` for direct tool calls

### 5. Refactored ManualWorkflow (`agent/workflows/manual_workflow.py`)

- Uses unified `MCPClient` via `execute_tool()` convenience function
- Single import: `from execution.mcp_client import execute_tool`
- Reduced code and eliminated duplication
- Single source of truth for MCP client management

## Architecture Comparison

### Old Architecture (Before)
```
User Task
  → RAG (retrieve skills)
  → WorkflowPlanner (generate plan with skill_id + args)
  → StateBasedExecutor
      → Parses action_sequence strings
      → ActionPrimitives (wrapper methods)
          → MCP Client
```

### New Architecture (After)
```
User Task
  → RAG (retrieve skills for reference)
  → WorkflowPlanner (generate plan with MCP tool calls)
  → MCPClient (unified client with execution methods)
      → Direct MCP tool calls (async/sync)
```

## Deprecated Files

The following files are no longer used and can be deleted later:
- `agent/execution/action_primitives.py` - Redundant wrapper methods
- `agent/execution/state_based_executor.py` - String parsing layer
- `agent/execution/claude_mcp_executor.py` - Alternative approach

## Benefits

1. **Simpler**: Fewer abstraction layers, easier to understand
2. **Consistent**: Same pattern as verified `manual_workflow.py`
3. **Flexible**: Direct MCP tool access, no hardcoded methods
4. **Debuggable**: Clear flow from plan to MCP tool execution
5. **Maintainable**: Changes to MCP tools don't require updating wrapper code

## Testing

Run tests:
```bash
# Test unified client directly
python -m agent.execution.mcp_client

# Test autonomous workflow execution
python test_refactored_workflow.py

# Test manual workflow with unified client
python test_manual_workflow_refactored.py

# Test full autonomous workflow
python -m agent.workflows.autonomous_workflow "Open sample.mf4"
```

**All tests passed successfully!** ✓

## Migration Notes

- Skill catalog format remains unchanged (high-level action_sequence)
- WorkflowPlanner translates skills into MCP tool calls
- Existing RAG and skill retrieval unchanged
- LangGraph workflow structure unchanged


# Skills vs Knowledge Base Refactoring Summary

## Overview

This refactoring separates the concept of "skills" into two distinct categories:

1. **Knowledge Base**: Documentation-extracted patterns (formerly called "skills")
2. **Verified Skills**: Human-verified, proven workflows

## Key Changes

### 1. Schema Changes (`agent/planning/schemas.py`)

#### New Schemas
- `KnowledgeSchema`: Represents patterns extracted from documentation (renamed from `SkillSchema`)
  - Field `skill_id` → `knowledge_id`
  - Represents unverified documentation patterns

- `VerifiedSkillSchema`: NEW - Represents human-verified workflows
  - Contains `action_plan` (list of `ActionSchema`)
  - Contains `knowledge_references` (which knowledge patterns were used)
  - Contains `verification_metadata` (who, when, test cases)
  - Contains `success_rate` tracking

- `WorkflowState`: Updated to include both:
  - `retrieved_knowledge`: Knowledge patterns from docs
  - `verified_skills`: Human-verified skills (optional)

### 2. File Renames

- `agent/rag/skill_retriever.py` → `agent/rag/knowledge_retriever.py`
- `SkillRetriever` class → `KnowledgeRetriever` class

### 3. Directory Structure

```
agent/
├── knowledge_base/              # Formerly: agent/skills/
│   ├── json/
│   │   ├── knowledge_catalog_gpt5.json       # Formerly: skill_catalog_gpt5.json
│   │   └── knowledge_catalog_gpt5_mini.json  # Formerly: skill_catalog_gpt5_mini.json
│   └── vector_store_gpt5_mini/               # Formerly: vector_store_gpt5_mini/
│
├── verified_skills/             # NEW
│   ├── json/
│   │   └── verified_skills.json              # NEW - Empty initially
│   └── README.md                             # NEW - Documentation
│
├── rag/
│   ├── knowledge_retriever.py                # Renamed from skill_retriever.py
│   └── doc_parser.py                         # Updated terminology
│
├── planning/
│   ├── schemas.py                            # Added KnowledgeSchema and VerifiedSkillSchema
│   └── workflow_planner.py                   # Updated to use knowledge_patterns
│
└── workflows/
    └── autonomous_workflow.py                # Updated to use knowledge_patterns
```

### 4. Method Renames

#### `KnowledgeRetriever` (formerly `SkillRetriever`)
- `load_skills()` → `load_knowledge()`
- `index_skills()` → `index_knowledge()`
- `retrieve()` → Returns `List[KnowledgeSchema]` (was `List[SkillSchema]`)
- `get_skill_by_id()` → `get_knowledge_by_id()`
- `list_all_skills()` → `list_all_knowledge()`

#### `DocumentationParser` (`doc_parser.py`)
- `extract_skills()` → `extract_knowledge()`
- `save_skills()` → `save_knowledge()`
- `build_skill_catalog()` → `build_knowledge_catalog()`

#### `WorkflowPlanner` (`workflow_planner.py`)
- Parameter `available_skills` → `available_knowledge`
- Updated prompts to reference "knowledge patterns" instead of "skills"

### 5. Updated Files

All files have been updated to use the new terminology:

- `agent/planning/schemas.py` - Added new schemas
- `agent/rag/knowledge_retriever.py` - Renamed and updated
- `agent/rag/doc_parser.py` - Updated terminology
- `agent/planning/workflow_planner.py` - Updated to use KnowledgeSchema
- `agent/workflows/autonomous_workflow.py` - Updated to use KnowledgeSchema

### 6. Migration Path

#### For existing JSON catalogs:
The JSON structure remains compatible, but fields need renaming:
- `skill_id` → `knowledge_id` in each entry

You can either:
1. Re-run the doc parser to generate new catalogs
2. Use a migration script to rename fields in existing catalogs

#### For existing vector databases:
- Rebuild the index using `KnowledgeRetriever` with `--rebuild-index` flag
- The collection name changed from `asammdf_skills` to `asammdf_knowledge`

## Conceptual Separation

### Knowledge Base (Documentation Patterns)
- **What**: Patterns extracted automatically from documentation
- **Trust Level**: Reference material only
- **Usage**: Planning inspiration, understanding capabilities
- **Example**: "Documentation says there's a concatenate feature in the Multiple Files tab"

### Verified Skills (Proven Workflows)
- **What**: Complete workflows that have been executed and verified to work
- **Trust Level**: High - human-approved
- **Usage**: Direct execution, templates, reliable automation
- **Example**: "I successfully concatenated Tesla Model 3 logs using these exact 15 steps"

## Benefits

1. **Clear Distinction**: No confusion between "documentation knowledge" and "proven workflows"
2. **Trust Levels**: Users know verified skills are reliable
3. **Incremental Learning**: System builds library of verified skills over time
4. **Traceability**: Verified skills reference the knowledge patterns they're based on
5. **Quality Metrics**: Success rate tracking for verified skills

## Future Enhancements

1. **Skill Retriever**: Create `VerifiedSkillRetriever` similar to `KnowledgeRetriever`
2. **Automatic Verification**: After successful workflow execution, offer to save as verified skill
3. **Skill Matching**: Prefer verified skills when available for a task
4. **Skill Evolution**: Track version history as skills are refined
5. **Skill Sharing**: Export/import verified skills between systems


# Code Changes Reference Guide

Quick reference for all files and line numbers changed in this implementation.

## New Files Added

### 1. `agent/execution/action_reverter.py`
**Purpose**: Smart action reversal strategies

**Key Classes/Functions**:
- `ActionReverter.__init__()` - Lines 30-41
- `can_revert()` - Lines 43-54
- `generate_revert_action()` - Lines 56-83
- `_revert_click()` - Lines 85-109
- `_find_cancel_button()` - Lines 111-170
- `_revert_type()` - Lines 172-180
- `_revert_key()` - Lines 182-197
- `_revert_hotkey()` - Lines 199-213
- `_llm_generate_revert()` - Lines 215-280
- `suggest_exploration_options()` - Lines 282-335

### 2. `test_revert_retain.py`
**Purpose**: Comprehensive unit tests

**Test Functions**:
- `test_local_action_history()` - Lines 20-85
- `test_action_reverter()` - Lines 88-159
- `test_progress_evaluation()` - Lines 162-217
- `test_loop_detection()` - Lines 220-240

### 3. `plans/local_planning_revert_retain_design.md`
**Purpose**: Complete design documentation (220 lines)

### 4. `plans/revert_retain_flow_diagram.md`
**Purpose**: Visual flow diagrams and examples (450 lines)

### 5. `IMPLEMENTATION_SUMMARY.md`
**Purpose**: Implementation summary and testing results (320 lines)

## Modified Files

### `agent/execution/adaptive_executor.py`

#### Added Imports (Lines 1-20)
```python
Line 9:   from dataclasses import dataclass, field
```

#### New Classes (Lines 23-138)

**LocalActionNode** (Lines 23-44)
```python
@dataclass
class LocalActionNode:
    """Single local action with exploration and progress tracking"""
    action: ActionSchema
    state_before: str
    state_after: str
    result: ExecutionResult
    distance_to_goal_before: float = 0.0
    distance_to_goal_after: float = 0.0
    exploration_options: List[Dict[str, str]] = field(default_factory=list)
    explored_count: int = 0
    reverted: bool = False

    @property
    def progress_made(self) -> float

    @property
    def has_unexplored_options(self) -> bool
```

**LocalActionHistory** (Lines 47-138)
```python
class LocalActionHistory:
    """Stack of local actions with revert capability"""

    def __init__(self)  # Line 50
    def push(...)  # Lines 54-78
    def peek_last(self)  # Lines 80-82
    def pop(self)  # Lines 84-91
    def get_depth(self)  # Lines 93-95
    def is_stuck_in_loop(self, window_size=3)  # Lines 97-115
    def has_consistent_regression(self, window_size=3, threshold=-0.5)  # Lines 117-133
    def clear(self)  # Lines 135-138
```

#### New Methods in AdaptiveExecutor Class

**`_evaluate_distance_to_goal()`** (Lines 434-487)
```python
def _evaluate_distance_to_goal(self, current_state: str, goal: str) -> float:
    """
    Evaluate how close current state is to achieving the goal
    Returns: Distance score from 0.0 (far) to 10.0 (achieved)
    """
```

**Key Features**:
- Uses LLM to score proximity to goal (0-10 scale)
- Prompts for distance_score, reasoning, missing_elements
- Returns float score
- Error handling with fallback to 0.0

**`_decide_revert_or_retain()`** (Lines 489-544)
```python
def _decide_revert_or_retain(
    self,
    history: LocalActionHistory,
    last_node: LocalActionNode,
    goal: str
) -> str:
    """
    Decide whether to revert last action or retain it
    Returns: "retain", "revert", "explore", or "cancel"
    """
```

**Decision Logic**:
1. Check if stuck in loop → "cancel"
2. Check if consistent regression → "cancel"
3. If progress > 0.5 → "retain"
4. If progress > 0 → "retain"
5. If progress ≤ 0:
   - Has unexplored options → "explore"
   - No options → "revert"

#### Completely Rewritten Method

**`_execute_with_local_planning()`** (Lines 750-909)

**Old Implementation** (60 lines):
- Simple loop executing 2-step plans
- No progress tracking
- No revert capability
- Basic goal checking

**New Implementation** (160 lines):
- Lines 769-777: Initialize tracking (history, reverter)
- Lines 783-796: Interpret and adapt with KB context
- Lines 808-823: Execute actions and track main action
- Lines 828-830: Evaluate distance before/after
- Lines 833-840: Record in history with distances
- Lines 843-849: Get exploration options
- Lines 852-858: Check goal condition
- Lines 861-902: Decision logic (cancel/revert/explore/retain)

**Key Additions**:
```python
Line 769: from agent.execution.action_reverter import ActionReverter

Line 774: history = LocalActionHistory()
Line 775: reverter = ActionReverter(self.mcp_client, self.client)

Lines 829-830: Evaluate progress
    dist_before = self._evaluate_distance_to_goal(...)
    dist_after = self._evaluate_distance_to_goal(...)

Lines 833-840: Record action with distances
    action_node = history.push(
        action=main_action,
        state_before=state_before or "",
        state_after=state_after or "",
        result=result,
        distance_before=dist_before,
        distance_after=dist_after
    )

Lines 843-849: Get exploration options
    if dist_after < 9.0:
        exploration_options = reverter.suggest_exploration_options(...)
        action_node.exploration_options = exploration_options

Lines 861-902: Revert/retain decision handling
    decision = self._decide_revert_or_retain(history, action_node, goal)

    if decision == "cancel":
        return failure
    elif decision == "revert":
        revert_action = reverter.generate_revert_action(...)
        execute_action(revert_action)
        history.pop()
    elif decision == "explore":
        option = action_node.exploration_options[action_node.explored_count]
        action_node.explored_count += 1
```

## Line-by-Line Change Summary

### agent/execution/adaptive_executor.py

| Line Range | Change Type | Description |
|------------|-------------|-------------|
| 9 | Added import | `from dataclasses import dataclass, field` |
| 23-44 | New class | `LocalActionNode` dataclass |
| 47-138 | New class | `LocalActionHistory` class |
| 434-487 | New method | `_evaluate_distance_to_goal()` |
| 489-544 | New method | `_decide_revert_or_retain()` |
| 750-909 | Rewritten | `_execute_with_local_planning()` with revert/retain logic |

**Total Lines Changed**: ~320 lines (160 new, 160 modified)

## Integration Points

### How to Use the New Functionality

**1. The system automatically uses revert/retain in local planning**
No changes needed to existing code. When `_execute_with_local_planning()` is called, it now includes intelligent backtracking.

**2. Accessing from autonomous workflow**
```python
# In autonomous_workflow.py, already integrated
# Line 245 calls executor.execute_action() which may trigger local planning
result = self.executor.execute_action(action, context=context_actions, step_num=step_num)
```

**3. Configuring behavior**
```python
# In adaptive_executor.py line 755
def _execute_with_local_planning(
    self,
    high_level_action: ActionSchema,
    context: List[ActionSchema],
    step_num: Optional[int],
    max_local_iterations: int = 10  # ← Adjust this
):
```

**4. Adjusting decision thresholds**
```python
# In _decide_revert_or_retain() method

# Line 522: Significant progress threshold
if progress > 0.5:  # ← Adjust this (default: 0.5)

# Line 527: Any progress threshold
if progress > 0:  # ← Keep as is

# Line 117 in LocalActionHistory: Regression window
def has_consistent_regression(self, window_size: int = 3, threshold: float = -0.5):
    # ← Adjust window_size or threshold
```

## Testing the Changes

### Run Unit Tests
```bash
.agent-venv\Scripts\python.exe test_revert_retain.py
```

### Run with Real Workflow
```bash
.agent-venv\Scripts\python.exe agent\workflows\autonomous_workflow.py "your task"
```

### Expected Test Output
```
✓ Test 1: LocalActionHistory
  - Push/pop actions
  - Progress tracking
  - Loop detection
  - Regression detection

✓ Test 2: ActionReverter
  - Checkbox reversion
  - Dialog cancellation
  - Text field clearing

✓ Test 3: Progress Evaluation
  - RETAIN decision for good progress
  - EXPLORE decision for stalled progress
  - REVERT decision for regression

✓ Test 4: Loop Detection
  - Detects repeated states
```

## Debugging and Monitoring

### Key Log Messages

**Progress Evaluation**:
```
→ Distance to goal: 5.2/10 - File menu is open but dialog not yet shown
```

**Decision Point**:
```
[Decision Point]
  Progress: +2.00 (before: 3.0, after: 5.0)
  Depth: 3
  → RETAIN: Good progress made
```

**Revert Action**:
```
→ Reverting action: Click-Tool
  Revert strategy: Revert: Click cancel button to close dialog
  ✓ Reverted successfully
```

**Exploration**:
```
→ Exploring option: try_different_field - Try entering value in Name field instead
```

**Cancellation**:
```
→ CANCEL: Stuck in loop
Local planning cancelled: stuck in loop or consistent regression
```

### State Cache Inspection

Local planning states are cached as:
- High-level step 8 → STATE_8.0
- First local action → STATE_8.1
- Second local action → STATE_8.2
- etc.

Access via:
```python
executor.state_cache.get_state(8.1)  # Get first local planning state
executor.state_cache.get_latest_state()  # Get most recent state
```

## Performance Considerations

### LLM Calls Per Iteration

Each local planning iteration makes:
1. `_interpret_and_adapt()` - 1 call (generates plan)
2. `_evaluate_distance_to_goal()` - 2 calls (before + after)
3. `suggest_exploration_options()` - 1 call (when needed)
4. `_find_cancel_button()` or `_llm_generate_revert()` - 1 call (when reverting)

**Total**: 3-5 LLM calls per iteration

**Typical local planning episode**:
- 3-5 iterations
- 9-25 LLM calls total
- ~10-30 seconds duration

### Optimization Opportunities

1. Cache distance evaluations for similar states
2. Batch LLM calls where possible
3. Use faster model for distance evaluation (already using gpt-4o-mini)
4. Skip exploration suggestion when progress is good

## Backward Compatibility

✓ All existing functionality preserved
✓ No breaking changes to existing APIs
✓ Autonomous workflow works unchanged
✓ Can disable by setting `max_local_iterations=1` (falls back to old behavior)

## Future Enhancements

Potential improvements (not yet implemented):

1. **State Visualization**
   - Add method to visualize decision tree
   - Track all explored paths

2. **Learning from History**
   - Cache successful exploration strategies
   - Prioritize previously successful options

3. **Confidence Scores**
   - LLM provides confidence for each exploration option
   - Try high-confidence options first

4. **Metrics Tracking**
   - Average iterations to goal
   - Revert rate by action type
   - Success rate by exploration strategy

## Quick Reference Card

```
┌────────────────────────────────────────────────────────────┐
│ REVERT/RETAIN DECISION QUICK REFERENCE                     │
├────────────────────────────────────────────────────────────┤
│                                                            │
│ Progress > 0.5      → RETAIN (good progress)              │
│ Progress > 0        → RETAIN (some progress)              │
│ Progress ≤ 0 + opts → EXPLORE (try alternatives)          │
│ Progress ≤ 0        → REVERT (backtrack)                  │
│ Loop detected       → CANCEL (stuck)                      │
│ Consistent regress  → CANCEL (not working)                │
│                                                            │
├────────────────────────────────────────────────────────────┤
│ KEY FILES:                                                 │
│  • adaptive_executor.py (lines 750-909)                   │
│  • action_reverter.py (reversal strategies)               │
│  • test_revert_retain.py (unit tests)                     │
│                                                            │
├────────────────────────────────────────────────────────────┤
│ KEY METHODS:                                               │
│  • _evaluate_distance_to_goal() - Score 0-10              │
│  • _decide_revert_or_retain() - Make decision             │
│  • _execute_with_local_planning() - Main loop             │
│                                                            │
└────────────────────────────────────────────────────────────┘
```



# Local Planning Revert/Retain Implementation Summary

## Overview
Successfully implemented an intelligent revert/retain decision mechanism for local planning in the adaptive executor. The system can now:
- Evaluate progress toward goals quantitatively
- Decide whether to revert or retain actions based on progress
- Explore alternative options before backtracking
- Cancel plans when stuck in loops or consistent regression
- Intelligently revert different action types (checkboxes, dialogs, text fields, etc.)

## Files Created/Modified

### New Files
1. **`agent/execution/action_reverter.py`** (335 lines)
   - `ActionReverter` class with smart reversal strategies
   - Heuristic-based reversion for common patterns
   - LLM fallback for complex cases
   - Exploration option suggestion

2. **`test_revert_retain.py`** (257 lines)
   - Comprehensive unit tests
   - Tests for history tracking, reversion, progress evaluation, and loop detection
   - ✓ All tests passing

3. **`plans/local_planning_revert_retain_design.md`** (220 lines)
   - Complete design documentation
   - Architecture diagrams
   - Integration points and testing strategy

### Modified Files
1. **`agent/execution/adaptive_executor.py`**
   - Added `LocalActionNode` dataclass (lines 23-44)
   - Added `LocalActionHistory` class (lines 47-138)
   - Added `_evaluate_distance_to_goal()` method (lines 434-487)
   - Added `_decide_revert_or_retain()` method (lines 489-544)
   - Completely rewrote `_execute_with_local_planning()` with revert/retain logic (lines 750-909)

## Key Features Implemented

### 1. Progress Evaluation (0-10 scale)
```python
def _evaluate_distance_to_goal(current_state: str, goal: str) -> float:
    """Returns score from 0.0 (far) to 10.0 (achieved)"""
```
- Uses LLM to evaluate proximity to goal
- Scores before and after each action
- Progress = distance_after - distance_before

### 2. Decision Logic
```
IF progress > 0.5:          → RETAIN (good progress)
ELIF progress > 0:          → RETAIN (some progress)
ELIF has_unexplored_options: → EXPLORE (try alternatives)
ELIF no_progress:           → REVERT (backtrack)
ELIF stuck_in_loop:         → CANCEL (escalate)
ELIF consistent_regression: → CANCEL (escalate)
```

### 3. Action Reversal Strategies

| Action Type | Reversal Method |
|-------------|----------------|
| Checkbox click | Click same location (toggle) |
| Button opening dialog | Find Cancel/Close button or ESC |
| Type text | Ctrl+A + Delete |
| Key: Enter | ESC key |
| Hotkey: Ctrl+Z | Ctrl+Y (redo) |
| Generic | LLM-generated strategy |

### 4. Exploration Before Reversion
- After each action, LLM suggests 2-3 alternative options
- System tries all options before reverting
- Tracks `explored_count` vs `exploration_options`
- Example: Dialog opened → try filling form, different values, then cancel

### 5. Plan Cancellation
Automatically cancels when:
- **Loop detected**: Same state appears 3+ times in recent history
- **Consistent regression**: Distance decreasing for 3+ consecutive actions
- **Max iterations**: Configurable limit (default: 10)

### 6. Action History Tracking
```python
@dataclass
class LocalActionNode:
    action: ActionSchema
    state_before: str
    state_after: str
    result: ExecutionResult
    distance_to_goal_before: float
    distance_to_goal_after: float
    exploration_options: List[Dict]
    explored_count: int
    reverted: bool
```

## Testing Results

All unit tests passing:

### Test 1: LocalActionHistory ✓
- Push/pop actions
- Track progress
- Depth management
- Loop detection (3 repeated states triggers detection)
- Regression detection

### Test 2: ActionReverter ✓
- Checkbox: Click same location ✓
- Type: Ctrl+A strategy ✓
- State-Tool: Correctly marked as non-revertible ✓

### Test 3: Progress Evaluation ✓
- Good progress (+2.0) → RETAIN
- No progress with options → EXPLORE
- Regression without options → REVERT

### Test 4: Loop Detection ✓
- Detects repeated states after 3 iterations

## Integration with Existing System

The new logic is integrated into `_execute_with_local_planning()` in adaptive_executor.py:

```python
# Execute action
result = execute_action(local_action, ...)

# Evaluate progress
dist_before = evaluate_distance_to_goal(state_before, goal)
dist_after = evaluate_distance_to_goal(state_after, goal)

# Record in history
node = history.push(action, state_before, state_after, result, dist_before, dist_after)

# Get exploration options
node.exploration_options = reverter.suggest_exploration_options(...)

# Check if goal met
if check_goal_condition(goal, state_after):
    return success

# Decide: revert or retain?
decision = decide_revert_or_retain(history, node, goal)

if decision == "revert":
    revert_action = reverter.generate_revert_action(node.action, state_after, state_before)
    execute_action(revert_action)
    history.pop()
elif decision == "explore":
    # Try next exploration option
    # LLM will plan based on exploration hint
elif decision == "cancel":
    return failure("stuck in loop")
# else: "retain" - continue to next iteration
```

## Usage Example

When the high-level plan has an unreachable action, the system now:

1. **Iteration 1**: Click button A → Dialog opens
   - Distance: 3.0 → 5.0 (progress +2.0)
   - Decision: RETAIN ✓

2. **Iteration 2**: Fill wrong field → No progress
   - Distance: 5.0 → 5.0 (progress 0.0)
   - Exploration options: [try_field_B, try_field_C, cancel]
   - Decision: EXPLORE ✓

3. **Iteration 3**: Try field B → Still wrong
   - Distance: 5.0 → 4.5 (progress -0.5)
   - Still has exploration options
   - Decision: EXPLORE ✓

4. **Iteration 4**: Try field C → Correct!
   - Distance: 4.5 → 9.0 (progress +4.5)
   - Decision: RETAIN ✓
   - Goal condition met → SUCCESS ✓

## Configuration Options

In `_execute_with_local_planning()`:
- `max_local_iterations`: Default 10
- Loop detection window: 3 states
- Regression window: 3 actions
- Progress thresholds:
  - Significant: +0.5
  - Regression: -0.5

## Benefits

1. **Intelligent Backtracking**: No longer stuck when hitting dead ends
2. **Exploration First**: Exhausts options before reverting
3. **Progress Measurement**: Quantitative evaluation (0-10 scale)
4. **Smart Reversion**: Action-type-specific strategies
5. **Loop Prevention**: Detects and cancels infinite loops
6. **State Tracking**: Complete history with revert capability

## Next Steps (Future Enhancements)

1. Add state visualization/debugging UI
2. Implement learning from successful exploration paths
3. Add confidence scores to exploration options
4. Optimize LLM calls (cache similar states)
5. Add metrics tracking (avg iterations to goal, revert rate, etc.)

## Testing Commands

```bash
# Run unit tests
.agent-venv\Scripts\python.exe test_revert_retain.py

# Run with actual GUI automation
.agent-venv\Scripts\python.exe agent\workflows\autonomous_workflow.py "your task here"
```

## Performance Notes

- Each local iteration makes 2-3 LLM calls:
  1. `_interpret_and_adapt()` - generate 2-step plan
  2. `_evaluate_distance_to_goal()` - twice (before/after)
  3. `suggest_exploration_options()` - when needed

- Typical local planning completes in 3-5 iterations
- Progress evaluation adds ~1-2 seconds per iteration

## Conclusion

The revert/retain mechanism is fully implemented and tested. The system can now intelligently navigate GUI automation tasks with:
- Progress-based decision making
- Smart backtracking when needed
- Exploration of alternatives before giving up
- Automatic loop and regression detection
- Action-specific reversal strategies

All requirements from the original specification have been met and validated through unit tests.
