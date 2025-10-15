"""Documentation parsing prompt for DocumentationParser"""


def get_doc_parsing_prompt(doc_content: str) -> str:
    """Prompt for extracting knowledge from asammdf documentation

    Args:
        doc_content: The documentation text content

    Returns:
        Prompt string
    """
    return f"""

You are a GUI automation expert analyzing asammdf application documentation. The documentation describes all the interactive options and workflows of the asammdf GUI.

Your task: Extract ALL GUI capabilities, actions, workflows, and knowledge patterns from the documentation into a structured JSON Knowledge Base.
This Knowledge Base will later be used to provide all the information and step-by-step instructions for automating tasks in asammdf GUI.

Extraction Requirements

Focus on capturing every possible GUI capability, including but not limited to:
1. File operations (open, save, export, convert, extract attachments)
2. Single & Multiple file operations (concatenate, stack, comparison)
3. Plotting & Visualization of channels (create plots, numeric views, tabular views, cursor/range usage, statistics, computed signals)
4. Data manipulation (cut, filter, resample, search, pattern-based selection)
5. Navigation (tabs, menus, dialogs, channel trees, layouts, drag & drop)
6. Shortcuts (general shortcuts, plot shortcuts for zoom, fit, alignment, representation, layout, saving, toggles, shifting signals)
6. Step-by-step tasks (e.g., "Open Folder", "Create Plot from selected channels", "Save all channels", "Insert computed signal", etc.)

For each capability, identify:
- knowledge_id: short snake_case Unique identifier (e.g., "concatenate_files", "export_csv", "open_folder")
- description: clear human-readable explanation of what this knowledge pattern does
- ui_location: where in GUI (tab/menu/toolbar) it is accessed (e.g., "File menu", "Plot window", "Batch processing tab")
- action_sequence: ordered list of high-level GUI steps to perform this action (e.g., ["click_menu('File')", "select('Open Folder')", "choose_folder"])
- shortcut: keyboard shortcut if available (e.g., "Ctrl+O", "F2", null if none)
- prerequisites: list of required conditions that must be true before executing the action_sequence (e.g., ["app_open"], ["file_loaded"])
- output_state: expected state of the result after performing action (e.g., "file_opened", "plot_created", "concatenated_file_loaded")
- doc_citation: relative section citation string in the URL or doc (e.g., "GUI#File-operations")
- Return ONLY a JSON array of knowledge patterns. No explanatory text.

Example format:
[{{
{{
  "knowledge_id": "concatenate_files",
  "description": "Concatenate multiple MDF files into a single continuous measurement file. The files must share the same internal structure (identical channel groups and matching channels in each group). Samples are appended in the given order, optionally synchronized by timestamps.",
  "ui_location": "Batch processing tab → Batch operations",
  "action_sequence": [
    "click_menu('Mode')",
    "select_option('Batch processing')",
    "click_menu('File')",
    "select_option('Open')",
    "multi_select_files_in_dialog('Ctrl + A' or 'Select Files with Ctrl')",
    "click_button('Open')",
    "arrange_files_in_list(order='desired sequence')",
    "select_operation('Concatenate')",
    "set_option('Sync using measurement timestamps', true/false)",
    "enter_filename('Concatenated.mf4')",
    "click_button('Save')"
  ],
  "shortcut": None,
  "prerequisites": ["app_open", "multiple_files_available"],
  "output_state": "concatenated_file_created",
  "doc_citation": "GUI#Batch-processing",
}}
]

<documentation>
{doc_content}
</documentation>

Extract ALL knowledge patterns as JSON array:"""
