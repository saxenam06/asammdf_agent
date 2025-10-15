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
    return rf"""You are an expert recovery planner for a failed GUI automation workflow.

═══════════════════════════════════════════════════════════════════════════════
SECTION 1: TASK CONTEXT
═══════════════════════════════════════════════════════════════════════════════

ORIGINAL TASK:
{original_task}

EXECUTION PROGRESS:
{completed_summary}

FAILURE POINT:
{failed_summary}

REMAINING OBJECTIVE:
{remaining_goal}
{pending_plan_section}

═══════════════════════════════════════════════════════════════════════════════
SECTION 2: CURRENT REALITY (What's Actually Available)
═══════════════════════════════════════════════════════════════════════════════
{state_section}

═══════════════════════════════════════════════════════════════════════════════
SECTION 3: KNOWLEDGE BASE GUIDANCE
═══════════════════════════════════════════════════════════════════════════════
{kb_section}

═══════════════════════════════════════════════════════════════════════════════
SECTION 4: AVAILABLE MCP TOOLS
═══════════════════════════════════════════════════════════════════════════════
{mcp_tools_description}

Valid tool names: {', '.join(valid_tool_names)}

═══════════════════════════════════════════════════════════════════════════════
SECTION 5: ROOT CAUSE ANALYSIS
═══════════════════════════════════════════════════════════════════════════════

UNDERSTAND THE FAILURE:
The original plan likely ASSUMED certain UI elements would be present, but the failure
indicates these assumptions were WRONG. You must:

1. ANALYZE ASSUMPTIONS vs REALITY
   → What elements did the original plan assume existed?
   → What elements are ACTUALLY visible in the current UI state?
   → What's the gap between assumption and reality?

2. IDENTIFY THE INTENT
   → What was the original plan trying to ACCOMPLISH (not just execute)?
   → What is the END GOAL the user wants to achieve?
   → Why did the user want to perform the failed action?

3. MAP INTENT TO ACTUAL ELEMENTS
   → Which ACTUAL visible elements can achieve the same intent?
   → Are there alternative controls/menus/buttons serving the same purpose?
   → Is there a different navigation path using real elements?

4. LEVERAGE KNOWLEDGE BASE
   → What does the KB say about the CORRECT way to achieve this goal?
   → Are there proven workflows or element names documented?
   → What patterns should you follow?

5. EVALUATE PENDING PLAN
   → Which pending steps are still valid given ACTUAL element availability?
   → Which steps need modification to use real elements?
   → Which steps should be discarded because they reference non-existent elements?

═══════════════════════════════════════════════════════════════════════════════
SECTION 6: RECOVERY STRATEGY
═══════════════════════════════════════════════════════════════════════════════

APPROACH:
Follow this systematic process to generate your recovery plan:

Step 1: VERIFY CURRENT STATE
→ If UI state is not available or unclear, start with State-Tool
→ Ensure you understand what's ACTUALLY on screen right now

Step 2: FIND ALTERNATIVE PATH
→ Given the intent and actual available elements, determine alternative approach
→ Use KB guidance to identify correct element names and workflows
→ Map each intended action to actual UI elements

Step 3: ADAPT PENDING PLAN
→ Review each pending step from original plan
→ Keep steps that reference actual existing elements
→ Modify steps that need different elements
→ Discard steps that are no longer relevant

Step 4: GENERATE RECOVERY PLAN
→ Create new step sequence using ONLY actual visible elements
→ Reference elements as: ["last_state:element_type:element_name"]
→ Call State-Tool before interacting with new UI sections
→ Include clear reasoning for each step explaining the adaptation

Step 5: VALIDATE PLAN
→ Ensure all element references point to ACTUAL visible elements
→ Verify the plan achieves the original INTENT
→ Confirm all steps use valid MCP tools

═══════════════════════════════════════════════════════════════════════════════
SECTION 7: ELEMENT REFERENCE RULES (CRITICAL)
═══════════════════════════════════════════════════════════════════════════════

ELEMENT REFERENCE FORMAT
   • Menus: ["last_state:menu:Mode"]
   • Buttons: ["last_state:button:Save"]
   • File name: ["last_state:edit:File name"]
   • Select Files: ["last_state:file name:data.MF4"]
   • Wildcards: ["last_state:file name:*.MF4"] for any matching file

PATH FORMATTING (CRITICAL FOR WINDOWS):
   • ALWAYS use single backslash (\) in Windows paths
   • Example: C:\Users\ADMIN\Downloads\file.mf4
   • NEVER use double backslashes (\\) - this will cause GUI typing errors
   • When specifying paths in Type-Tool arguments, use exactly ONE backslash between path components

WORKFLOW:
1. Call State-Tool to discover elements
2. Reference discovered elements as "last_state:..."
3. If you need updated state later, call State-Tool again
4. Continue using "last_state:..." for newest elements

═══════════════════════════════════════════════════════════════════════════════
SECTION 8: CRITICAL REQUIREMENTS
═══════════════════════════════════════════════════════════════════════════════

✓ DO:
• Base ALL decisions on ACTUAL current UI state
• Use ONLY elements you can SEE in the state output
• Find ALTERNATIVE paths when original assumptions fail
• Follow KB guidance for correct workflows
• Reuse valid pending steps where appropriate
• Include clear reasoning explaining your adaptations
• Focus on achieving the INTENT, not replicating failed approach

✗ DON'T:
• Assume any elements exist without verification
• Hardcode coordinates - use State-Tool discovery
• Repeat completed steps
• Blindly copy the original failed approach
• Use numbered state references (STATE_1, STATE_2, etc.)
• Ignore the current UI state
• Discard entire pending plan without evaluation

═══════════════════════════════════════════════════════════════════════════════
SECTION 9: REQUIRED OUTPUT FORMAT
═══════════════════════════════════════════════════════════════════════════════

Return ONLY valid JSON (no explanatory text outside JSON):

{{
  "plan": [
    {{
      "tool_name": "State-Tool",
      "tool_arguments": {{"use_vision": false}},
      "reasoning": "Verify current UI state and discover actual available elements"
    }},
    {{
      "tool_name": "Click-Tool",
      "tool_arguments": {{"loc": ["last_state:menu:File"], "button": "left", "clicks": 1}},
      "reasoning": "Open File menu (alternative to non-existent Mode menu) to achieve same intent"
    }},
    {{
        "tool_name": "Type-Tool",
        "tool_arguments": {{
          "text": "C:\Users\ADMIN\Downloads\output.mf4",
          "clear": true,
          "press_enter": false
        }},
        "reasoning": "Enter the full output path and filename"
      }},
    ... additional steps ...
  ],
  "reasoning": "DETAILED EXPLANATION REQUIRED:
1. ASSUMPTION vs REALITY: [What original plan assumed vs what actually exists]
2. INTENT: [What the failed action was trying to accomplish]
3. ALTERNATIVE SOLUTION: [What actual elements will achieve the same intent]
4. KB GUIDANCE: [How knowledge base informed the new approach]
5. PENDING PLAN ADAPTATION: [Which steps reused/modified/discarded and why]
6. SUCCESS RATIONALE: [Why this reality-based approach will work]",
  "estimated_duration": 45
}}

═══════════════════════════════════════════════════════════════════════════════
Now generate your recovery plan following this systematic approach.
═══════════════════════════════════════════════════════════════════════════════
"""
