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

    return f"""Find exact [x, y] coordinates for a UI element from the current state.

ACTION CONTEXT:
{context_info}
Tool: {action.tool_name}
Intent: {action.reasoning}

CURRENT UI STATE:
```
{state_output}
```

FIND COORDINATES FOR (try in priority order):
{refs_list}

Element reference formats:
- Structured: "last_state:control_type:element_name" (e.g., "last_state:button:Save")
- Natural: "Save button", "File menu", "OK dialog"

RESOLUTION LOGIC:
1. Search for exact matches first
2. If no match, use intent to find elements serving the same purpose
3. For multiple matches, use context and position to choose the best one
4. ONLY return coordinates for elements ACTUALLY PRESENT in the UI state

JSON RESPONSE:
Success:
{{"found": true, "coordinates": [x, y], "matched_ref": "...", "adaptation": "explain if adapted, else empty"}}

Failure:
{{"found": false, "reason": "why no match", "suggestion": "alternative visible elements"}}

Return ONLY JSON, no other text."""
