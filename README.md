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
python agent\examples\example_manual_workflow.py
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
python agent\examples\example_autonomous_workflow.py
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
│   └── examples/
│       ├── example_autonomous_workflow.py  # Autonomous examples (.agent-venv)
│       └── example_manual_workflow.py      # Manual examples (.agent-venv)
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
python agent\examples\example_manual_workflow.py
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
python agent\examples\example_autonomous_workflow.py
```

Choose from:
1. Claude + MCP Direct (Simple GUI task)
2. RAG + Autonomous (Open MF4 file)
3. RAG + Autonomous (Concatenate & Export)
4. Custom Task (Your own prompt)

**Manual Examples** (requires `.agent-venv` - MCP client spawns server):
```bash
.agent-venv\Scripts\activate
python agent\examples\example_manual_workflow.py
```

Choose from:
1. Plot Signal from MF4 (hardcoded workflow using MCP tools)

## How It Works

### 1. Automatic Skill Extraction (One-time Setup)

`doc_parser.py` uses Claude to parse asammdf documentation:

**Input:** HTML from https://asammdf.readthedocs.io/en/stable/gui.html
**Process:** Claude extracts 15-20 GUI skills with structured output
**Output:** `skill_catalog.json` with skills like `concatenate_mf4`, `export_excel`

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

**Option 2:** Manually add to `skill_catalog.json`
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
- Save to `agent/rag/skill_catalog.json`

Expected output:
```
Fetching documentation from https://asammdf.readthedocs.io/en/stable/gui.html...
Extracting skills using Claude claude-sonnet-4-20250514...
Extracted 15-20 skills:
  - open_file: Open an MF4 file
  - concatenate_mf4: Concatenate multiple MF4 files
  - export_excel: Export data to Excel format
  ...
Saved 20 skills to agent/rag/skill_catalog.json
✓ Successfully built skill catalog with 20 skills
```

### 4. Index Skills in Vector Database

```bash
python agent/rag/skill_retriever.py --rebuild-index
```

This creates a ChromaDB vector database at `agent/rag/vector_store/` for fast semantic search.

### 5. Run Examples

#### Option A: Interactive Examples

```bash
python agent/examples/example_1_basic_usage.py
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
│   ├── skill_retriever.py           # RAG queries
│   ├── skill_catalog.json           # Extracted skills (generated)
│   └── vector_store/                # ChromaDB (generated)
├── planning/
│   ├── schemas.py                   # Pydantic models
│   └── workflow_planner.py          # Claude-based planner
├── execution/
│   ├── action_primitives.py         # Primitive GUI actions
│   └── state_based_executor.py      # Generic action interpreter
└── examples/
    └── example_1_basic_usage.py     # Usage examples
```

## How It Works

### 1. Skill Extraction (One-time)

`doc_parser.py` uses Claude to parse the asammdf GUI documentation:

**Input:** HTML documentation
**Process:** Claude extracts skills with structured output
**Output:** `skill_catalog.json` with 15-20 GUI skills

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

2. Or manually add to `skill_catalog.json`

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
