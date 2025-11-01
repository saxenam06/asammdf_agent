"""
Prompt for generating recovery approaches for knowledge base items based on verified skills.

This prompt guides an LLM to analyze a verified skill and extract recovery approaches
for KB items that have original_error field.
"""

KB_RECOVERY_APPROACH_PROMPT = """You are an expert at extracting recovery approaches from verified skills to improve a knowledge base.

You will be given:
1. A verified skill - a proven workflow that successfully completed a task
2. A knowledge catalog - contains KB items, some with original_error indicating they failed before

Your task:
For EACH KB item that has an "original_error" field, analyze the verified skill to determine if there's a recovery approach that could help avoid or fix that error in the future.

Instructions:
- Review the entire verified skill's action sequence
- For each KB item with original_error, identify if the verified skill shows a better approach
- Generate a concise recovery_approach (2-3 statements max) that explains:
  * What went wrong (briefly)
  * How the verified skill solved it
  * What to do differently next time
- If the verified skill doesn't address a particular error, output null for that item's recovery_approach
- Be specific and actionable

Output format:
Return a JSON array with this structure for each KB item that has original_error:
[
  {
    "knowledge_id": "string",
    "recovery_approach": "string or null"
  },
  ...
]

Example output:
[
  {
    "knowledge_id": "open_files",
    "recovery_approach": "Always use the exact folder path from the task. Navigate to the specific folder first, then select one .MF4 file, press Ctrl+A to select all files of that type, and click Open. This ensures all files in the correct directory are loaded."
  },
  {
    "knowledge_id": "save_concatenated",
    "recovery_approach": null
  }
]

Verified Skill:
{verified_skill}

Knowledge Catalog Items with original_error:
{kb_items_with_errors}

Generate the recovery approaches now:
"""
