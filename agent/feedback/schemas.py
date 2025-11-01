"""
Feedback schemas for human-in-the-loop learning system

Core schemas for HITL verification and learning storage
"""

from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime


class VerificationStatus(str, Enum):
    """Verification status from human"""
    COMPLETED = "completed"
    NOT_COMPLETED = "not_completed"
    PARTIALLY_COMPLETED = "partially_completed"


class VerifiedSkillMetadata(BaseModel):
    """Metadata for verified skills - tracks usage and success rate"""
    verified_by: str = Field("human", description="Who verified this skill")
    verified_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    session_id: str = Field(..., description="Session where skill was created")
    human_feedbacks_count: int = Field(0, description="Number of human corrections used")
    agent_recoveries_count: int = Field(0, description="Number of self-recoveries used")
    times_used: int = Field(0, description="How many times skill has been used")
    success_count: int = Field(0, description="How many times it succeeded")
    success_rate: float = Field(1.0, description="Current success rate (0.0-1.0)")

    class Config:
        json_schema_extra = {
            "example": {
                "verified_by": "human",
                "verified_at": "2025-01-15T11:00:00",
                "session_id": "session_001",
                "human_feedbacks_count": 2,
                "agent_recoveries_count": 1,
                "times_used": 5,
                "success_count": 5,
                "success_rate": 1.0
            }
        }


class FailureLearning(BaseModel):
    """Learning from execution failure - attached to KB items"""
    task: str = Field(..., description="Task being executed when failure occurred")
    step_num: int = Field(..., description="Step number where error occurred (1-indexed)")
    original_action: Dict[str, Any] = Field(..., description="Action that failed")
    original_error: str = Field(..., description="Error message from the failure")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())

    class Config:
        json_schema_extra = {
            "example": {
                "task": "Concatenate MF4 files",
                "step_num": 10,
                "original_action": {"tool_name": "Click-Tool", "loc": [500, 400]},
                "original_error": "Element 'Add Files' button not found",
                "timestamp": "2025-01-15T10:30:00"
            }
        }


class TaskVerification(BaseModel):
    """Human verification of task completion"""
    verification_id: str = Field(default_factory=lambda: f"verify_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    session_id: str = Field(..., description="Session being verified")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    status: VerificationStatus = Field(..., description="Completion status")
    reasoning: str = Field(..., description="Human's explanation of status")
    successful_steps: Optional[List[int]] = Field(None, description="Step numbers that worked")
    failed_steps: Optional[List[int]] = Field(None, description="Step numbers that failed")
    create_skill: bool = Field(False, description="Whether to save as verified skill")

    class Config:
        json_schema_extra = {
            "example": {
                "verification_id": "verify_20250115_110000",
                "session_id": "session_001",
                "status": "completed",
                "reasoning": "All steps executed successfully, result verified",
                "create_skill": True
            }
        }
