"""Recovery planning prompt for PlanRecoveryManager"""
from typing import List


def get_recovery_prompt(
    original_task: str,
    completed_summary: str,
    failed_summary: str,
    remaining_goal: str,
    pending_plan_section: str,
    state_section: str,
    kb_section: str,
    mcp_tools_description: str,
    valid_tool_names: List[str]
) -> str:
    """Prompt for generating recovery plans

    Args:
        original_task: The original user task
        completed_summary: Summary of completed steps
        failed_summary: Summary of failure
        remaining_goal: What's left to accomplish
        pending_plan_section: Remaining steps from original plan
        state_section: Current UI state section
        kb_section: Knowledge base context section
        mcp_tools_description: Description of available MCP tools
        valid_tool_names: List of valid tool names

    Returns:
        Prompt string
    """
    return rf"""You are an expert recovery planner for failed GUI automation workflows.

TASK CONTEXT:
Original task: {original_task}
Progress: {completed_summary}
Failure: {failed_summary}
Remaining: {remaining_goal}
{pending_plan_section}

CURRENT UI STATE:
{state_section}

KNOWLEDGE BASE:
{kb_section}

AVAILABLE MCP TOOLS:
{mcp_tools_description}
Valid tools: {', '.join(valid_tool_names)}

ROOT CAUSE ANALYSIS:
The original plan assumed certain UI elements existed, but the failure shows they don't. You must:

1. Compare assumed vs actual elements - what's missing?
2. Identify the INTENT - what goal was the failed action trying to achieve?
3. Map intent to actual visible elements - which real elements can achieve the same goal?
4. Use KB to find the correct workflow and element names
5. Evaluate pending steps - keep valid ones, modify those needing real elements, discard invalid ones

RECOVERY STEPS:
1. Verify current state (use State-Tool if unclear)
2. Find alternative path using actual elements and KB guidance
3. Adapt pending plan based on what's actually available
4. Generate new plan using ONLY visible elements
5. Validate all references point to actual elements

ELEMENT RULES:
- Format: ["last_state:element_type:element_name"]
  - Menus: ["last_state:menu:Mode"]
  - Buttons: ["last_state:button:Save"]
  - Files: ["last_state:file name:data.MF4"] or ["last_state:file name:*.MF4"]
  - File name: ["last_state:edit:File name"]
- Windows paths: Single backslash only - C:\Users\ADMIN\file.mf4
- Always call State-Tool before new UI sections

DO:
✓ Base decisions on ACTUAL UI state
✓ Find alternative paths when assumptions fail
✓ Follow KB guidance
✓ Focus on achieving INTENT, not replicating failed approach

DON'T:
✗ Assume elements exist
✗ Hardcode coordinates
✗ Repeat completed steps
✗ Ignore current state

JSON OUTPUT:
{{
  "plan": [
    {{"tool_name": "State-Tool", "tool_arguments": {{"use_vision": false}}, "reasoning": "Verify current state"}},
    {{"tool_name": "Click-Tool", "tool_arguments": {{"loc": ["last_state:menu:File"], "button": "left", "clicks": 1}}, "reasoning": "Use File menu as alternative"}},
    {{"tool_name": "Type-Tool", "tool_arguments": {{"text": "C:\Users\ADMIN\output.mf4", "clear": true, "press_enter": false}}, "reasoning": "Enter path"}}
  ],
  "reasoning": "EXPLAIN:
1. Assumption vs Reality: [gap analysis]
2. Intent: [what failed action tried to accomplish]
3. Alternative: [actual elements that achieve same goal]
4. KB Guidance: [how KB informed approach]
5. Pending Plan: [what reused/modified/discarded]
6. Why This Works: [rationale]",
  "estimated_duration": 45
}}

Return ONLY valid JSON."""
