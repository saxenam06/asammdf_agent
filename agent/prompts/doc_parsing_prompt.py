"""Documentation parsing prompt for DocumentationParser"""


def get_doc_parsing_prompt(doc_content: str) -> str:
    """Prompt for extracting knowledge from asammdf documentation

    Args:
        doc_content: The documentation text content

    Returns:
        Prompt string
    """
    return f"""Extract ALL GUI capabilities from asammdf documentation into structured JSON Knowledge Base.

FOCUS AREAS:
1. File operations (open, save, export, convert, extract)
2. Multi-file operations (concatenate, stack, comparison)
3. Plotting & visualization (plots, numeric/tabular views, cursors, statistics, computed signals)
4. Data manipulation (cut, filter, resample, search, pattern selection)
5. Navigation (tabs, menus, dialogs, channel trees, drag & drop)
6. Shortcuts (general, plot zoom/fit/align, representation, layout, saving)

EXTRACT FOR EACH CAPABILITY:
- knowledge_id: snake_case unique identifier (e.g., "concatenate_files", "export_csv")
- description: what this pattern does
- ui_location: where accessed (e.g., "File menu", "Batch processing tab")
- action_sequence: ordered GUI steps (e.g., ["click_menu('File')", "select('Open')", "choose_folder"])
- shortcut: keyboard shortcut if available (e.g., "Ctrl+O", null if none)
- prerequisites: required conditions (e.g., ["app_open"], ["file_loaded"])
- output_state: expected result (e.g., "file_opened", "plot_created")
- doc_citation: section reference (e.g., "GUI#File-operations")

EXAMPLE:
[{{
  "knowledge_id": "concatenate_files",
  "description": "Concatenate multiple MDF files into single continuous file with same structure",
  "ui_location": "Batch processing tab → Batch operations",
  "action_sequence": [
    "click_menu('Mode')",
    "select_option('Batch processing')",
    "click_menu('File')",
    "select_option('Open')",
    "multi_select_files_in_dialog('Ctrl + A')",
    "click_button('Open')",
    "select_operation('Concatenate')",
    "set_option('Sync using timestamps', true/false)",
    "enter_filename('output.mf4')",
    "click_button('Save')"
  ],
  "shortcut": null,
  "prerequisites": ["app_open", "multiple_files_available"],
  "output_state": "concatenated_file_created",
  "doc_citation": "GUI#Batch-processing"
}}]

<documentation>
{doc_content}
</documentation>

Return ONLY JSON array of all knowledge patterns. No explanatory text."""
