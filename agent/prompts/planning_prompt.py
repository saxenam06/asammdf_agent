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
1. Follow provided knowledge patterns as reference - they contain proven workflows
2. Use ONLY listed tool names with exact argument schemas
3. ALWAYS call State-Tool before interacting with UI elements
4. Start with Switch-Tool to activate asammdf: {{"name": "asammdf"}}
5. Reference UI elements discovered by State-Tool: ["last_state:element_type:element_name"]
   - Menus: ["last_state:menu:Mode"]
   - Buttons: ["last_state:button:Save"]
   - Files: ["last_state:file name:data.MF4"] or ["last_state:file name:*.MF4"]
   - File name: ["last_state:edit:File name"]
6. Windows paths: Use single backslash (\) only - e.g., C:\Users\ADMIN\file.mf4

KB SOURCE ATTRIBUTION (CRITICAL):
For EACH action in your plan, you MUST set the "kb_source" field:
- If the action is derived from a knowledge base (KB) item, set kb_source to that KB item's knowledge_id
- If the action is from your own reasoning (not from any KB item), set kb_source to null
- This helps track which KB items led to failures so we can improve them

Example with kb_source:
{{
  "tool_name": "Click-Tool",
  "tool_arguments": {{"loc": ["last_state:menu:File"], "button": "left"}},
  "reasoning": "Open File menu to access Open command (from KB: open_files)",
  "kb_source": "open_files"
}}

LEARNING-BASED PLANNING:
You will receive past learnings from previous task executions. These learnings show:
- How plans derived from knowledge base FAILED in practice(original errors)
- How the agent successfully RECOVERED from those failures (recovery approaches)
- Human corrections when the agent asked for help (human interrupt/proactive)

Each learning includes:
- SOURCE: "agent_self_exploration" (agent recovered on its own), "human_interrupt" (human corrected the agent), or "human_proactive" (agent asked, human answered)
- ORIGINAL ERROR: What went wrong when following knowledge patterns
- RECOVERY APPROACH: What actually worked to accomplish the task

Use learnings to:
1. AVOID actions/patterns that previously failed (check original_error)
2. ADOPT recovery approaches that succeeded (check recovery_approach)


WORKFLOW:
Switch-Tool (activate app) → State-Tool (discover elements) → Click/Type-Tool (interact) → Repeat as needed

JSON OUTPUT:
{{
  "task": "Brief restatement of user's task",
  "plan": [
    {{
      "tool_name": "Switch-Tool",
      "tool_arguments": {{"name": "asammdf"}},
      "reasoning": "Activate asammdf window",
      "kb_source": null
    }},
    {{
      "tool_name": "State-Tool",
      "tool_arguments": {{"use_vision": false}},
      "reasoning": "Discover available UI elements",
      "kb_source": null
    }},
    {{
      "tool_name": "Click-Tool",
      "tool_arguments": {{"loc": ["last_state:menu:File"], "button": "left", "clicks": 1}},
      "reasoning": "Open File menu (from KB: open_files)",
      "kb_source": "open_files"
    }},
    {{
      "tool_name": "Type-Tool",
      "tool_arguments": {{"text": "C:\Users\ADMIN\output.mf4", "clear": true, "press_enter": false}},
      "reasoning": "Enter output path",
      "kb_source": null
    }}
  ],
  "reasoning": "Overall strategy and why this accomplishes the task",
  "estimated_duration": 60
}}

Return ONLY valid JSON. No explanatory text outside JSON."""


def get_planning_user_prompt(
    task: str,
    knowledge_json: str,
    context: str = "",
    latest_state: str = "",
    learnings_context: str = ""
) -> str:
    """User prompt for plan generation

    Args:
        task: User's task description
        knowledge_json: JSON-formatted knowledge patterns from documentation
        context: Optional additional context
        latest_state: Optional current UI state
        learnings_context: Optional past learnings from previous task executions

    Returns:
        User prompt string
    """
    context_str = f"\n\nAdditional context: {context}" if context else ""

    learnings_section = ""
    if learnings_context:
        learnings_section = f"""

PAST LEARNINGS FROM PREVIOUS EXECUTIONS:
{learnings_context}

HOW TO USE THESE LEARNINGS:
- SOURCE shows who/what provided the learning: "agent_self_exploration" (agent recovered), "human_interrupt" (human corrected), "human_proactive" (agent asked human)
- ORIGINAL ERROR shows what failed when following knowledge base patterns
- RECOVERY APPROACH shows what actually worked in practice
"""

    state_context = ""
    if latest_state:
        state_context = f"""

CURRENT UI STATE (for reference when planning element interactions):
```
{latest_state}
```

Use this state to understand what UI elements are currently available and the format of State-Tool output.
"""

    return f"""User task: "{task}"{context_str}

Available knowledge patterns from documentation:
{knowledge_json}
{learnings_section}
Generate a complete execution plan using knowledge patterns and past learnings.

Consider:
- What prerequisite steps are needed (e.g., opening files before processing)
- The correct order of operations
- What arguments each action needs
- Past learnings about what worked/failed in similar tasks
- Expected GUI state after each action
{state_context}
Return ONLY valid JSON matching the schema. No explanatory text outside JSON."""
