# asammdf Agent

Intelligent GUI automation agent for the [asammdf](https://github.com/danielhrisca/asammdf) MDF/MF4 file viewer. This agent leverages the Windows-MCP tools to programmatically control the asammdf GUI application, enabling automated workflows for opening files and plotting signals without hardcoded screen coordinates.

## Overview

The asammdf agent provides a Python-based workflow orchestrator that can:
- Launch and control the asammdf GUI application
- Open MF4 measurement files
- Automatically locate and plot signals by name
- Execute complete workflows with dynamic UI element discovery

Instead of using brittle, hardcoded screen coordinates, this agent uses Windows UI Automation to intelligently discover and interact with GUI elements at runtime.

## Architecture

```
asammdf_agent/
├── agent/
│   ├── workflows/
│   │   └── asammdf_workflow.py    # Core workflow orchestrator
│   └── examples/
│       └── example_1_basic_usage.py  # Usage examples
├── tools/
│   └── Windows-MCP/                # Windows automation tools
└── docs/
    └── README.md                   # This file
```

## Installation

### Prerequisites

- **Python 3.13+** (required by Windows-MCP)
- **Windows OS** (required for Windows UI Automation)
- **asammdf** application installed and accessible from command line
- **uv** package manager ([install instructions](https://github.com/astral-sh/uv))

### Setup Steps

1. **Clone the repository** (if not already done):
   ```bash
   git clone <your-repo-url>
   cd asammdf_agent
   ```

2. **Install Windows-MCP tools**:

   Navigate to the Windows-MCP directory:
   ```bash
   cd tools/Windows-MCP
   ```

   **Option A: Using PowerShell virtual environment**
   ```powershell
   # Activate the virtual environment
   .\.windows-venv\Scripts\Activate.ps1

   # Sync dependencies
   uv sync --active
   ```

   **Option B: Direct installation with uv**
   ```bash
   # Install in editable mode with specified Python interpreter
   uv pip install -e . --python .windows-venv/Scripts/python.exe
   ```

3. **Verify installation**:
   ```bash
   # Return to project root
   cd ../..

   # Test Python import (from project root)
   python -c "from agent.workflows.asammdf_workflow import AsammdfWorkflow; print('✓ Installation successful')"
   ```

## Usage

### Basic Example

The simplest way to use the agent is through the convenience function:

```python
from agent.workflows.asammdf_workflow import plot_signal_from_mf4

# Plot a signal from an MF4 file
results = plot_signal_from_mf4(
    mf4_file="Discrete_deflate.mf4",
    signal_name="ASAM.M.SCALAR.SBYTE.IDENTICAL.DISCRETE"
)

if results['success']:
    print("✓ Workflow completed successfully!")
else:
    print(f"✗ Workflow failed: {results['error']}")
```

### Running the Example

```bash
python agent/examples/example_1_basic_usage.py
```

### Advanced Usage

For more control, use the `AsammdfWorkflow` class directly:

```python
from agent.workflows.asammdf_workflow import AsammdfWorkflow

# Initialize workflow with custom fuzzy matching threshold
workflow = AsammdfWorkflow(fuzzy_threshold=70)

# Execute complete workflow
results = workflow.plot_signal(
    mf4_file="my_measurement.mf4",
    signal_name="Engine.Speed.RPM"
)

# Inspect results
print(f"Success: {results['success']}")
print(f"Steps executed: {len(results['steps'])}")
for step in results['steps']:
    print(f"  - {step['name']}: {'✓' if step['success'] else '✗'}")
```

## How It Works

### Intelligent UI Discovery

The agent uses Windows UI Automation (via Windows-MCP tools) to:

1. **Query UI elements** - Retrieve all interactive elements with their properties and coordinates
2. **Parse and match** - Find elements by name and control type (Button, Edit, Tree Item, etc.)
3. **Execute actions** - Click, type, drag, and keyboard shortcuts at discovered locations

### Workflow Steps

The `plot_signal()` workflow executes these steps:

1. ~~**Launch asammdf**~~ (disabled - assumes application already running)
2. **Open MF4 file** - Use Ctrl+O shortcut, dynamically locate file input and Open button
3. **Drag signal to plot** - Find signal in Natural Sort tree, drag to plot area
4. **Create plot** - Click OK button to finalize plot creation

Each step uses dynamic element discovery, making the workflow resilient to:
- Different screen resolutions
- Window positions and sizes
- UI element repositioning in new asammdf versions

### Windows-MCP Tools

The workflow uses these tools from Windows-MCP:

- `launch_tool` - Launch applications by name
- `switch_tool` - Switch focus to application window
- `click_tool` - Click at coordinates
- `type_tool` - Type text with optional clear and enter
- `drag_tool` - Drag from source to destination
- `shortcut_tool` - Press keyboard shortcuts (Ctrl+O, etc.)
- `key_tool` - Press individual keys (Enter, Home, etc.)
- `wait_tool` - Wait for specified duration
- `state_tool` - Get current UI state and interactive elements

## Customization

### Modifying Workflows

Edit `agent/workflows/asammdf_workflow.py` to:

- Add new workflow steps
- Change element discovery strategies
- Adjust wait times for slower/faster systems
- Add error recovery logic

### Fuzzy Matching

The `fuzzy_threshold` parameter (0-100) controls how closely element names must match:

- **100** - Exact match only
- **70-90** - Recommended range for flexibility
- **< 70** - May match unintended elements

### File Paths

By default, the workflow assumes MF4 files are in the Downloads folder. Modify `_open_mf4_file()` to use absolute paths or different directories.

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