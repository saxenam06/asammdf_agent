"""Planning prompts for WorkflowPlanner"""

import os
from datetime import datetime
from typing import Optional


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
For EACH action in your plan, MUST set the "kb_source" field:
- If action derived from a KB item, set kb_source to that item's KB ID
- If action from your own reasoning, set kb_source to null
- This tracks which KB items led to failures for improvement

Example:
{{
  "tool_name": "Click-Tool",
  "tool_arguments": {{"loc": ["last_state:menu:File"], "button": "left"}},
  "reasoning": "Open File menu (from KB: open_files)",
  "kb_source": "open_files"
}}

LEARNING-BASED PLANNING:
Past learnings show:
- How KB patterns FAILED in practice (errors encountered)
- How failures were RESOLVED (recovery approaches)
- Human corrections when agent needed help

Use learnings to:
1. AVOID actions that previously failed
2. ADOPT recovery approaches that succeeded
3. **CRITICAL**: DO NOT repeat failed actions even if multiple KB items suggest them
   - Learnings trump documentation - they show real execution results
   - If learning shows action X failed, do NOT use action X again
   - Always check if learnings contradict a KB pattern before using it


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
    latest_state: str = ""
) -> str:
    """User prompt for plan generation

    Args:
        task: User's task description
        knowledge_json: Formatted KB patterns with learnings attached
        context: Optional additional context
        latest_state: Optional current UI state

    Returns:
        User prompt string
    """
    context_str = f"\n\nAdditional context: {context}" if context else ""

    state_context = ""
    if latest_state:
        state_context = f"""

CURRENT UI STATE:
```
{latest_state}
```
"""

    return f"""User task: "{task}"{context_str}

Knowledge patterns with learnings:
{knowledge_json}

Generate a complete execution plan.

Consider:
- Prerequisite steps needed
- Correct operation order
- Tool arguments required
- Past learnings showing what worked/failed
{state_context}
Return ONLY valid JSON. No explanatory text outside JSON."""


def save_prompt_to_markdown(
    task: str,
    system_prompt: str,
    user_prompt: str,
    plan_number: int = 0,
    output_dir: str = "agent/prompts/planning_history"
) -> Optional[str]:
    """Save planning prompts to markdown file for inspection

    Args:
        task: Task description
        system_prompt: System prompt content
        user_prompt: User prompt content
        plan_number: Plan iteration number
        output_dir: Directory to save prompt files

    Returns:
        Path to saved file, or None if save failed
    """
    try:
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)

        # Create filename from task (no timestamp to avoid clutter)
        task_slug = "".join(c if c.isalnum() or c in (' ', '_') else '' for c in task)
        task_slug = "_".join(task_slug.split())[:50]  # Limit length
        filename = f"{task_slug}_Plan_{plan_number}.md"
        filepath = os.path.join(output_dir, filename)

        # Format markdown content
        markdown_content = f"""# Planning Prompt - {task}

**Plan Number**: {plan_number}
**Timestamp**: {datetime.now().isoformat()}
**Task**: {task}

---

## System Prompt

```
{system_prompt}
```

---

## User Prompt

```
{user_prompt}
```

---

**File generated**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""

        # Write to file
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(markdown_content)

        return filepath

    except Exception as e:
        print(f"  [Warning] Failed to save prompt to markdown: {e}")
        return None
