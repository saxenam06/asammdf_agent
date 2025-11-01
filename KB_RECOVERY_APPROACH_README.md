# Knowledge Base Recovery Approach Generator

## Overview

After a verified skill is successfully created, the system can now automatically analyze the skill and generate recovery approaches for knowledge base (KB) items that previously encountered errors. This feature uses GPT-4o-mini to extract learnings from successful workflows and attach them to KB items.

## How It Works

### 1. Workflow Integration

When a task completes successfully and a verified skill is created, the system will prompt:

```
================================================================================
[KB Update] Would you like to update the knowledge catalog with
            recovery approaches from this verified skill?
            This will analyze errors in KB items and add learnings
            based on how the verified skill solved them.
================================================================================
Update knowledge catalog? [y/N]:
```

### 2. Recovery Approach Generation

If you respond with 'y', the system will:

1. **Load the verified skill** - The most recently created skill from the skill library
2. **Identify KB items with errors** - Find all KB items that have `original_error` in their `kb_learnings`
3. **Call LLM (GPT-4o-mini)** - Analyze the verified skill to generate recovery approaches
4. **Update the catalog** - Add `recovery_approach` field to relevant KB learnings

### 3. What Gets Generated

For each KB item with an `original_error`, the LLM generates a concise recovery approach (2-3 statements) that explains:

- What went wrong
- How the verified skill solved it
- What to do differently next time

## File Structure

```
agent/
├── prompts/
│   └── kb_recovery_approach_prompt.py    # Prompt template for LLM
├── knowledge_base/
│   ├── recovery_approach_generator.py     # Core generator logic
│   └── parsed_knowledge/
│       └── knowledge_catalog.json         # Updated with recovery approaches
└── workflows/
    └── autonomous_workflow.py             # Integrated in final verification
```

## Usage

### During Normal Workflow

The feature activates automatically after verified skill creation:

```python
# In autonomous_workflow.py, after skill is created:
workflow = AutonomousWorkflow(enable_hitl=True)
result = workflow.run_sync("Your task here")

# If task succeeds and skill is created, you'll be prompted for KB update
```

### Standalone Usage

You can also use the recovery approach generator independently:

```python
from agent.knowledge_base.recovery_approach_generator import (
    generate_and_update_kb_recovery_approaches
)

# Generate and update KB with recovery approaches
success = generate_and_update_kb_recovery_approaches(
    verified_skill_path="agent/learning/verified_skills/your_task_skills.json",
    catalog_path="agent/knowledge_base/parsed_knowledge/knowledge_catalog.json"
)
```

### Testing

Run the test script to verify functionality:

```bash
.agent-venv\Scripts\python.exe test_kb_recovery_generator.py
```

## Example

### Before (KB Learning with Error)

```json
{
  "knowledge_id": "open_files",
  "description": "Open MDF files",
  "kb_learnings": [
    {
      "task": "Concatenate all .MF4 files",
      "step_num": 11,
      "original_error": "Used wildcard path C:\\folder\\*.MF4 instead of exact folder. Suggestion: Use exact folder path, select one file, press Ctrl+A to select all.",
      "timestamp": "2025-10-25T23:45:00"
    }
  ]
}
```

### After (With Recovery Approach)

```json
{
  "knowledge_id": "open_files",
  "description": "Open MDF files",
  "kb_learnings": [
    {
      "task": "Concatenate all .MF4 files",
      "step_num": 11,
      "original_error": "Used wildcard path C:\\folder\\*.MF4 instead of exact folder. Suggestion: Use exact folder path, select one file, press Ctrl+A to select all.",
      "recovery_approach": "Always use the exact folder path from the task. Navigate to the specific folder first, then select one .MF4 file, press Ctrl+A to select all files of that type, and click Open. This ensures all files in the correct directory are loaded.",
      "timestamp": "2025-10-25T23:45:00"
    }
  ]
}
```

## Configuration

### Model Selection

The generator uses GPT-4o-mini by default (cost-effective for this task):

```python
# In recovery_approach_generator.py
self.model = "gpt-4o-mini"
```

To change the model:

```python
generator = RecoveryApproachGenerator()
generator.model = "gpt-4o"  # Use a different model
```

### Temperature

Default temperature is 0.3 for focused, consistent output:

```python
# In generate_recovery_approaches method
temperature=0.3
```

## API Requirements

Requires OpenAI API key in environment:

```bash
export OPENAI_API_KEY=your_api_key_here
# or on Windows:
set OPENAI_API_KEY=your_api_key_here
```

## Prompt Engineering

The prompt is defined in `agent/prompts/kb_recovery_approach_prompt.py`:

Key instructions:
- Review entire verified skill's action sequence
- For each KB item with original_error, identify recovery approach
- Generate 2-3 concise statements max
- Be specific and actionable
- Return null if verified skill doesn't address the error

## Error Handling

The generator handles various error scenarios:

1. **No KB items with errors** - Returns empty dict, skips update
2. **LLM API failure** - Catches exception, returns empty dict
3. **JSON parsing errors** - Handles both array and object responses
4. **File I/O errors** - Catches and reports file access issues

## Integration Points

### 1. Final Verification Node (autonomous_workflow.py:389-515)

```python
def _final_verification_node(self, state: WorkflowState) -> WorkflowState:
    # ... after skill creation ...
    if verification.create_skill:
        skill = self._skill_library.add_skill(...)
        # Prompt for KB update
        self._prompt_kb_update(skill_path)
```

### 2. KB Update Prompt (autonomous_workflow.py:454-515)

```python
def _prompt_kb_update(self, skill_path: str):
    response = input("Update knowledge catalog? [y/N]: ")
    if response == 'y':
        generator = RecoveryApproachGenerator()
        recovery_approaches = generator.generate_recovery_approaches(...)
        generator.update_knowledge_catalog(...)
```

## Benefits

1. **Automated Learning** - Automatically extracts learnings from successful workflows
2. **Consistent Format** - LLM ensures recovery approaches are concise and actionable
3. **Contextual** - Analyzes entire verified skill for comprehensive understanding
4. **Non-intrusive** - Optional prompt, only after successful task completion
5. **Cost-effective** - Uses GPT-4o-mini for this specific task

## Future Enhancements

Potential improvements:

1. **Batch Processing** - Process multiple verified skills at once
2. **Confidence Scores** - Add confidence ratings to recovery approaches
3. **Human Review** - Optional review step before applying to catalog
4. **Version Tracking** - Track which skill version generated each recovery approach
5. **Similarity Matching** - Match similar errors across different KB items

## Troubleshooting

### Issue: No recovery approaches generated

**Possible causes:**
- No KB items have `original_error` field
- Verified skill doesn't address the errors in KB
- LLM API key not configured

**Solution:**
- Check catalog for KB items with `kb_learnings` containing `original_error`
- Verify OPENAI_API_KEY environment variable is set
- Check console output for error messages

### Issue: Import errors

**Solution:**
```bash
# Verify all imports work
.agent-venv\Scripts\python.exe -c "from agent.knowledge_base.recovery_approach_generator import RecoveryApproachGenerator; print('Success')"
```

### Issue: JSON parsing errors

**Possible cause:**
- LLM returned unexpected format

**Solution:**
- Check console output for response format
- Generator handles both array and object responses
- May need to adjust prompt for more consistent output

## Version History

- **v1.0** (2025-11-01) - Initial implementation
  - Recovery approach generation using GPT-4o-mini
  - Integration with autonomous workflow
  - Prompt-based KB update after skill creation
