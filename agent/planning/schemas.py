"""
Pydantic schemas for autonomous workflow components
"""

from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field


class KnowledgeSchema(BaseModel):
    """Schema for GUI knowledge patterns extracted from documentation with accumulated learnings"""
    knowledge_id: str = Field(..., description="Short snake_case unique identifier (e.g., 'concatenate_files', 'export_csv', 'open_folder')")
    description: str = Field(..., description="Clear human-readable explanation of what this knowledge pattern does")
    ui_location: str = Field(..., description="Where in GUI (tab/menu/toolbar) it is accessed (e.g., 'File menu', 'Plot window', 'Batch processing tab')")
    action_sequence: List[str] = Field(..., description="Ordered list of high-level GUI steps to perform this action (e.g., [\"click_menu('File')\", \"select('Open Folder')\", \"choose_folder\"])")
    shortcut: Optional[str] = Field(None, description="Keyboard shortcut if available (e.g., 'Ctrl+O', 'F2', null if none)")
    prerequisites: List[str] = Field(default_factory=list, description="List of required conditions that must be true before executing the action_sequence (e.g., ['app_open'], ['file_loaded'])")
    output_state: str = Field(..., description="Expected state of the result after performing action (e.g., 'file_opened', 'plot_created', 'concatenated_file_loaded')")
    doc_citation: str = Field(..., description="Relative section citation string in the URL or doc (e.g., 'GUI#File-operations')")
    parameters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Configurable parameters")

    # KB learnings and trust tracking
    kb_learnings: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of learnings (SelfExplorationLearning or HumanInterruptLearning) from past failures using this KB item"
    )
    trust_score: float = Field(
        1.0,
        description="Confidence in this KB item (1.0=fully trusted, <1.0=has known issues). Decreases with failures."
    )

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


class TaskInput(BaseModel):
    """Schema for parameterized task input"""
    operation: str = Field(..., description="Core task operation without specific file/folder paths")
    parameters: Dict[str, str] = Field(
        default_factory=dict,
        description="Path parameters as key-value pairs (e.g., {'input_folder': 'C:\\\\Users\\\\...', 'output_file': '...'})"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "operation": "Concatenate all .MF4 files and save with specified name",
                "parameters": {
                    "input_folder": "C:\\Users\\ADMIN\\Downloads\\ev-data-pack-v10\\electric_cars\\log_files\\Kia EV6\\LOG\\2F6913DB\\00001026",
                    "output_file": "C:\\Users\\ADMIN\\Downloads\\ev-data-pack-v10\\electric_cars\\log_files\\Kia EV6\\LOG\\2F6913DB\\Kia_EV_6_2F6913DB.mf4"
                }
            }
        }

    def to_full_task_string(self) -> str:
        """Convert to legacy full task string format (for backward compatibility)"""
        if not self.parameters:
            return self.operation

        # Build task string with parameters embedded
        params_str = ", ".join([f"{k}={v}" for k, v in self.parameters.items()])
        return f"{self.operation} (Parameters: {params_str})"


class ActionSchema(BaseModel):
    """Schema for a single MCP tool action in a plan"""
    tool_name: str = Field(..., description="MCP tool name to execute (e.g., 'Click-Tool', 'Type-Tool', 'State-Tool')")
    tool_arguments: Dict[str, Any] = Field(default_factory=dict, description="Arguments to pass to MCP tool")
    reasoning: Optional[str] = Field(None, description="Why this action is needed (optional, for clarity)")
    kb_source: Optional[str] = Field(
        None,
        description="Knowledge base item ID this action is derived from (e.g., 'open_files'). Leave null/empty if not from KB."
    )

    class Config:
        json_schema_extra = {
            "example": {
                "tool_name": "Click-Tool",
                "tool_arguments": {"loc": ["last_state:menu:File"], "button": "left", "clicks": 1},
                "reasoning": "Open File menu to access Open command",
                "kb_source": "open_files"
            }
        }


class PlanSchema(BaseModel):
    """Schema for a complete execution plan"""
    plan: List[ActionSchema] = Field(..., description="Sequence of actions to execute")
    reasoning: str = Field(..., description="Why this plan achieves the task")
    estimated_duration: Optional[int] = Field(None, description="Estimated execution time in seconds")
    parameters: Optional[Dict[str, str]] = Field(
        None,
        description="Path parameters used in this plan (for parameterized tasks). Null for legacy non-parameterized plans."
    )

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


class StepStatus(BaseModel):
    """Status of a single step in plan execution"""
    step_number: int = Field(..., description="Step number in the plan (1-indexed)")
    action: ActionSchema = Field(..., description="The action that was/will be executed")
    status: str = Field(..., description="Status: 'pending', 'completed', 'failed'")
    result: Optional[ExecutionResult] = Field(None, description="Execution result if completed or failed")
    timestamp: Optional[str] = Field(None, description="When this step was executed")


class PlanExecutionState(BaseModel):
    """Complete state of plan execution for recovery and replanning"""
    original_task: str = Field(..., description="Original user task description")
    plan_id: str = Field(..., description="Unique plan identifier with timestamp")
    steps: List[StepStatus] = Field(..., description="Status of each step in the plan")
    current_step: int = Field(0, description="Current step being executed (0-indexed)")
    overall_status: str = Field("in_progress", description="Overall plan status: 'in_progress', 'completed', 'failed'")
    created_at: str = Field(..., description="When this plan execution started")
    updated_at: str = Field(..., description="When this state was last updated")

    def get_completed_steps(self) -> List[StepStatus]:
        """Get all completed steps"""
        return [s for s in self.steps if s.status == "completed"]

    def get_failed_steps(self) -> List[StepStatus]:
        """Get all failed steps"""
        return [s for s in self.steps if s.status == "failed"]

    def get_pending_steps(self) -> List[StepStatus]:
        """Get all pending steps"""
        return [s for s in self.steps if s.status == "pending"]


class VerifiedSkillSchema(BaseModel):
    """Schema for human-verified, proven workflow skills"""
    task_description: str = Field(..., description="What task this verified skill accomplishes (legacy format with paths)")
    operation: Optional[str] = Field(
        None,
        description="Core operation without paths (for parameterized skills). Null for legacy skills."
    )
    action_plan: List[ActionSchema] = Field(..., description="Sequence of proven MCP tool actions that execute this skill")
    parameters: Optional[Dict[str, str]] = Field(
        None,
        description="Required parameters for this skill (for parameterized skills). Null for legacy skills."
    )
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


