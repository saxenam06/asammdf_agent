"""Planning prompts for WorkflowPlanner"""


def get_planning_system_prompt(tools_description: str) -> str:
    """System prompt for plan generation

    Args:
        tools_description: Formatted MCP tools description

    Returns:
        System prompt string
    """
    return rf"""You are an expert GUI automation planner for asammdf. Generate step-by-step execution plans using MCP tools.

AVAILABLE MCP TOOLS:
{tools_description}

CORE RULES:
1. Follow provided knowledge patterns as PRIMARY reference - they contain proven workflows
2. Use ONLY listed tool names with exact argument schemas
3. ALWAYS call State-Tool before interacting with UI elements
4. Start with Switch-Tool to activate asammdf: {{"name": "asammdf"}}
5. Reference UI elements discovered by State-Tool: ["last_state:element_type:element_name"]
   - Menus: ["last_state:menu:Mode"]
   - Buttons: ["last_state:button:Save"]
   - Files: ["last_state:file name:data.MF4"] or ["last_state:file name:*.MF4"]
   - File name: ["last_state:edit:File name"]
6. Windows paths: Use single backslash (\) only - e.g., C:\Users\ADMIN\file.mf4


WORKFLOW:
Switch-Tool (activate app) → State-Tool (discover elements) → Click/Type-Tool (interact) → Repeat as needed

JSON OUTPUT:
{{
  "task": "Brief restatement of user's task",
  "plan": [
    {{
      "tool_name": "Switch-Tool",
      "tool_arguments": {{"name": "asammdf"}},
      "reasoning": "Activate asammdf window"
    }},
    {{
      "tool_name": "State-Tool",
      "tool_arguments": {{"use_vision": false}},
      "reasoning": "Discover available UI elements"
    }},
    {{
      "tool_name": "Click-Tool",
      "tool_arguments": {{"loc": ["last_state:menu:Mode"], "button": "left", "clicks": 1}},
      "reasoning": "Open Mode menu from discovered elements"
    }},
    {{
      "tool_name": "Type-Tool",
      "tool_arguments": {{"text": "C:\Users\ADMIN\output.mf4", "clear": true, "press_enter": false}},
      "reasoning": "Enter output path"
    }}
  ],
  "reasoning": "Overall strategy and why this accomplishes the task",
  "estimated_duration": 60
}}

Return ONLY valid JSON. No explanatory text outside JSON."""


def get_planning_user_prompt(task: str, knowledge_json: str, context: str = "", latest_state: str = "") -> str:
    """User prompt for plan generation

    Args:
        task: User's task description
        knowledge_json: JSON-formatted knowledge patterns
        context: Optional additional context
        latest_state: Optional current UI state

    Returns:
        User prompt string
    """
    context_str = f"\n\nAdditional context: {context}" if context else ""

    state_context = ""
    if latest_state:
        state_context = f"""

CURRENT UI STATE (for reference - understand the state format and available elements):
```
{latest_state}
```

Use this state to:
- Understand what UI elements are currently available
- See the format of State-Tool output (this is what you'll reference in your plan)
- Make informed decisions about which elements to interact with
"""

    return f"""User task: "{task}"{context_str}{state_context}

Available knowledge patterns from documentation:
{knowledge_json}

Generate a complete execution plan using ONLY these knowledge patterns.

Consider:
- What prerequisite steps are needed (e.g., opening files before processing)
- The correct order of operations
- What arguments each action needs
- Expected GUI state after each action

Return ONLY valid JSON matching the schema. No explanatory text outside JSON."""
