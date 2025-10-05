"""
Pydantic schemas for autonomous workflow components
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class KnowledgeSchema(BaseModel):
    """Schema for GUI knowledge patterns extracted from documentation"""
    knowledge_id: str = Field(..., description="Short snake_case unique identifier (e.g., 'concatenate_files', 'export_csv', 'open_folder')")
    description: str = Field(..., description="Clear human-readable explanation of what this knowledge pattern does")
    ui_location: str = Field(..., description="Where in GUI (tab/menu/toolbar) it is accessed (e.g., 'File menu', 'Plot window', 'Batch processing tab')")
    action_sequence: List[str] = Field(..., description="Ordered list of high-level GUI steps to perform this action (e.g., [\"click_menu('File')\", \"select('Open Folder')\", \"choose_folder\"])")
    shortcut: Optional[str] = Field(None, description="Keyboard shortcut if available (e.g., 'Ctrl+O', 'F2', null if none)")
    prerequisites: List[str] = Field(default_factory=list, description="List of required conditions that must be true before executing the action_sequence (e.g., ['app_open'], ['file_loaded'])")
    output_state: str = Field(..., description="Expected state of the result after performing action (e.g., 'file_opened', 'plot_created', 'concatenated_file_loaded')")
    doc_citation: str = Field(..., description="Relative section citation string in the URL or doc (e.g., 'GUI#File-operations')")
    parameters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Configurable parameters")

    class Config:
        json_schema_extra = {
            "example": {
                "knowledge_id": "concatenate_mf4",
                "description": "Concatenate multiple MF4 files into one",
                "ui_location": "Multiple files tab",
                "action_sequence": [
                    "select_tab('Multiple files')",
                    "add_files",
                    "set_mode('Concatenate')",
                    "run"
                ],
                "shortcut": None,
                "prerequisites": ["app_open", "files_available"],
                "output_state": "concatenated_file_loaded",
                "doc_citation": "https://asammdf.readthedocs.io/en/stable/gui.html#multiple-files",
                "parameters": {
                    "folder": "str",
                    "filter": "str"
                }
            }
        }


class ActionSchema(BaseModel):
    """Schema for a single MCP tool action in a plan"""
    tool_name: str = Field(..., description="MCP tool name to execute (e.g., 'Click-Tool', 'Type-Tool', 'State-Tool')")
    tool_arguments: Dict[str, Any] = Field(default_factory=dict, description="Arguments to pass to MCP tool")
    reasoning: Optional[str] = Field(None, description="Why this action is needed (optional, for clarity)")

    class Config:
        json_schema_extra = {
            "example": {
                "tool_name": "Click-Tool",
                "tool_arguments": {"loc": [450, 300], "button": "left", "clicks": 1},
                "reasoning": "Click OK button to confirm dialog"
            }
        }


class PlanSchema(BaseModel):
    """Schema for a complete execution plan"""
    plan: List[ActionSchema] = Field(..., description="Sequence of actions to execute")
    reasoning: str = Field(..., description="Why this plan achieves the task")
    estimated_duration: Optional[int] = Field(None, description="Estimated execution time in seconds")

    class Config:
        json_schema_extra = {
            "example": {
                "plan": [
                    {
                        "tool_name": "State-Tool",
                        "tool_arguments": {"use_vision": False},
                        "reasoning": "Get current desktop state to find UI elements"
                    },
                    {
                        "tool_name": "Switch-Tool",
                        "tool_arguments": {"name": "asammdf"},
                        "reasoning": "Activate the asammdf application window"
                    },
                    {
                        "tool_name": "Click-Tool",
                        "tool_arguments": {"loc": [450, 300], "button": "left", "clicks": 1},
                        "reasoning": "Click the File menu button"
                    }
                ],
                "reasoning": "Overall explanation of why this plan achieves the task",
                "estimated_duration": 30
            }
        }


class ExecutionResult(BaseModel):
    """Result of executing a single action"""
    success: bool = Field(..., description="Whether the action executed successfully")
    action: Optional[str] = Field(None, description="Name of the action/tool that was executed")
    error: Optional[str] = Field(None, description="Error message if execution failed")
    evidence: Optional[str] = Field(None, description="Output/evidence from the tool execution")
    timestamp: Optional[str] = Field(None, description="Timestamp of execution")


class VerifiedSkillSchema(BaseModel):
    """Schema for human-verified, proven workflow skills"""
    task_description: str = Field(..., description="What task this verified skill accomplishes")
    action_plan: List[ActionSchema] = Field(..., description="Sequence of proven MCP tool actions that execute this skill")
    verification_metadata: Dict[str, Any] = Field(default_factory=dict, description="Human verification info (verified_by, date, test_cases)")
    success_rate: float = Field(1.0, description="Historical success rate (0.0 to 1.0)")

    class Config:
        json_schema_extra = {
            "example": {
                "task_description": "Concatenate Tesla Model 3 log files from a specific folder",
                "action_plan": [
                    {
                        "tool_name": "Switch-Tool",
                        "tool_arguments": {"name": "asammdf"},
                        "reasoning": "Switch to asammdf application"
                    },
                    {
                        "tool_name": "Shortcut-Tool",
                        "tool_arguments": {"shortcut": ["ctrl", "o"]},
                        "reasoning": "Open file dialog"
                    }
                ],
                "verification_metadata": {
                    "verified_by": "human_operator",
                    "verified_date": "2025-01-15",
                    "test_cases": ["Tesla Model 3 logs folder"]
                },
                "success_rate": 1.0
            }
        }



class WorkflowState(BaseModel):
    """State of the autonomous workflow"""
    task: str = Field(..., description="The user's task description")
    retrieved_knowledge: List[KnowledgeSchema] = Field(default_factory=list, description="Knowledge patterns retrieved from documentation using RAG")
    verified_skills: List[VerifiedSkillSchema] = Field(default_factory=list, description="Human-verified skills available for this task (if any)")
    plan: Optional[PlanSchema] = Field(None, description="Generated execution plan (sequence of MCP tool actions)")
    current_step: int = Field(0, description="Current step index in plan execution (0-based)")
    execution_log: List[ExecutionResult] = Field(default_factory=list, description="Log of executed actions and their results")
    error: Optional[str] = Field(None, description="Error message if workflow failed")
    completed: bool = Field(False, description="Whether the workflow has completed successfully")
    retry_count: int = Field(0, description="Current retry count for the current step")

    class Config:
        arbitrary_types_allowed = True
