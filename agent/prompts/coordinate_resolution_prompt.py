"""Coordinate resolution prompt for AdaptiveExecutor"""
import json
from typing import List, Dict, Any, Optional
from agent.planning.schemas import ActionSchema


def get_coordinate_resolution_prompt(
    element_refs: List[str],
    action: ActionSchema,
    state_output: str,
    tool_schema: Optional[Dict] = None
) -> str:
    """Prompt for resolving UI element coordinates

    Args:
        element_refs: List of element references to resolve
        action: The action being executed
        state_output: Current UI state from State-Tool
        tool_schema: Optional tool schema for context

    Returns:
        Prompt string
    """
    refs_list = "\n".join([f"  - {ref}" for ref in element_refs])

    context_info = f"""
ACTION CONTEXT:
- Tool: {action.tool_name}
- Reasoning: {action.reasoning}
- All Arguments: {json.dumps(action.tool_arguments, indent=2)}
"""

    if tool_schema:
        schema_params = tool_schema.get('properties', {})
        params_desc = []
        for param, info in schema_params.items():
            param_type = info.get('type', 'any')
            param_desc = info.get('description', 'No description')
            params_desc.append(f"  - {param} ({param_type}): {param_desc}")

        if params_desc:
            context_info += f"""
TOOL SCHEMA ({action.tool_name}):
{chr(10).join(params_desc)}
"""

    return f"""You are a UI element coordinate resolver for an automation system. Your task is to find the exact [x, y] coordinates of a UI element from the current state.

═══════════════════════════════════════════════════════════════════════════════
SECTION 1: WHAT YOU'RE TRYING TO DO
═══════════════════════════════════════════════════════════════════════════════
{context_info}

Key Understanding:
• Tool Name: {action.tool_name}
• Intent/Goal: {action.reasoning}
• This reasoning tells you WHY this element needs to be found and what it will be used for

═══════════════════════════════════════════════════════════════════════════════
SECTION 2: CURRENT UI STATE (What's Actually Visible)
═══════════════════════════════════════════════════════════════════════════════
```
{state_output}
```

═══════════════════════════════════════════════════════════════════════════════
SECTION 3: YOUR TASK
═══════════════════════════════════════════════════════════════════════════════
Find coordinates for ONE of these element references (try in order of priority):
{refs_list}

UNDERSTANDING ELEMENT REFERENCES:
• Structured format: "last_state:control_type:element_name" (e.g., "last_state:button:Save")
• Natural language: "Save button", "File menu", "OK dialog"
• Any description that identifies a UI element

═══════════════════════════════════════════════════════════════════════════════
SECTION 4: DECISION LOGIC (Follow This Process)
═══════════════════════════════════════════════════════════════════════════════

Step 1: EXACT MATCH SEARCH
→ Search the UI state for exact matches to the element references
→ If found, extract coordinates and proceed to response

Step 2: INTENT-BASED ADAPTATION (If no exact match)
→ Use the tool reasoning to understand the INTENT
→ Look for elements that serve the SAME PURPOSE
→ Example: If looking for "Mode menu" to access settings, and only "Preferences" exists,
   Preferences might serve the same intent

Step 3: MULTIPLE INSTANCE HANDLING
→ If multiple elements match (same control_type and name):
   - Use the tool reasoning to pick the most contextually appropriate one
   - Consider position (top/bottom, left/right) based on typical UI conventions
   - Prefer the element that best aligns with the intended action

Step 4: VALIDATION
→ ONLY return coordinates for elements ACTUALLY PRESENT in the UI state
→ NEVER return coordinates for invisible or non-existent elements
→ If nothing matches, provide helpful suggestions in the failure response

═══════════════════════════════════════════════════════════════════════════════
SECTION 5: RESPONSE FORMAT
═══════════════════════════════════════════════════════════════════════════════

Return ONLY a JSON object (no other text):

✓ SUCCESS CASE (Element found):
{{
  "found": true,
  "coordinates": [x, y],
  "matched_ref": "which reference matched",
  "adaptation": "explanation if you used intent-based adaptation instead of exact match (leave empty if exact match)"
}}

✗ FAILURE CASE (No element found):
{{
  "found": false,
  "reason": "clear explanation of why none of the references matched",
  "suggestion": "alternative elements visible in current state that might achieve the same goal based on reasoning"
}}

═══════════════════════════════════════════════════════════════════════════════
Now proceed with coordinate resolution.
═══════════════════════════════════════════════════════════════════════════════
"""
