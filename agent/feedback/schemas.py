"""
Feedback schemas for human-in-the-loop learning system

Defines data structures for:
- Multi-source learning (human proactive, human interrupt, agent self-exploration)
- Confidence levels
- Verification status
- Learning entries
"""

from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from agent.planning.schemas import ActionSchema


class ConfidenceLevel(str, Enum):
    """Agent confidence levels for decision-making"""
    HIGH = "high"      # 0.7-1.0: Execute autonomously
    MEDIUM = "medium"  # 0.4-0.7: Consider asking human
    LOW = "low"        # 0.0-0.4: Must ask human for guidance


class LearningSource(str, Enum):
    """Source of learning entry"""
    HUMAN_PROACTIVE = "human_proactive"          # Agent asks, human responds
    HUMAN_INTERRUPT = "human_interrupt"          # Human interrupts execution
    EXECUTION_FAILURE = "execution_failure"      # Execution failure with enriched context


class VerificationStatus(str, Enum):
    """Verification status from human"""
    COMPLETED = "completed"              # Task successfully completed
    NOT_COMPLETED = "not_completed"      # Task failed or incomplete
    PARTIALLY_COMPLETED = "partially_completed"  # Some steps worked


class LearningEntry(BaseModel):
    """
    Single learning entry from any source

    Stored in Mem0 for retrieval during future task planning
    """
    learning_id: str = Field(..., description="Unique learning identifier")
    session_id: str = Field(..., description="Session this learning belongs to")
    source: LearningSource = Field(..., description="Where this learning came from")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())

    # Context
    task: str = Field(..., description="Task being executed when learning occurred")
    step_num: Optional[int] = Field(None, description="Step number in plan")
    ui_state: Optional[str] = Field(None, description="UI state when learning occurred")

    # Learning data
    original_action: Optional[Dict[str, Any]] = Field(None, description="Original action that prompted learning")
    corrected_action: Optional[Dict[str, Any]] = Field(None, description="Corrected action from human")
    human_reasoning: Optional[str] = Field(None, description="Why human provided this correction")

    # For execution failures
    original_error: Optional[str] = Field(None, description="Error from execution failure")
    recovery_approach: Optional[str] = Field(None, description="Successful approach after rerun")

    class Config:
        json_schema_extra = {
            "example": {
                "learning_id": "learn_12345",
                "session_id": "session_001",
                "source": "human_proactive",
                "timestamp": "2025-01-15T10:30:00",
                "task": "Concatenate MF4 files",
                "step_num": 5,
                "original_action": {"tool_name": "Click-Tool", "loc": [450, 300]},
                "corrected_action": {"tool_name": "Shortcut-Tool", "shortcut": ["ctrl", "m"]},
                "human_reasoning": "Button not visible in this view, use keyboard shortcut"
            }
        }


class ProceduralGuidance(BaseModel):
    """
    Detailed procedural guidance from human

    Multi-step instructions for how to accomplish a goal
    """
    guidance_id: str = Field(default_factory=lambda: f"guide_{datetime.now().strftime('%Y%m%d_%H%M%S')}")

    # Goal this procedure achieves
    goal: str = Field(..., description="What this procedure accomplishes")

    # Step-by-step instructions
    steps: List[str] = Field(..., description="Ordered list of steps to follow")

    # Key insights
    key_points: Optional[List[str]] = Field(None, description="Important things to remember")

    # Common mistakes to avoid
    mistakes_to_avoid: Optional[List[str]] = Field(None, description="What NOT to do")

    # Alternative approaches
    alternatives: Optional[List[str]] = Field(None, description="Other ways to achieve the same goal")

    class Config:
        json_schema_extra = {
            "example": {
                "guidance_id": "guide_20250115_103000",
                "goal": "Add files to concatenate list",
                "steps": [
                    "Go to File menu",
                    "Click Open",
                    "Navigate to folder containing files",
                    "Click on any file",
                    "Press Ctrl+A to select all files",
                    "Press Enter to load all files"
                ],
                "key_points": [
                    "Ctrl+A selects all files in current folder",
                    "Files must be in same folder for batch selection"
                ],
                "mistakes_to_avoid": [
                    "Don't try to find 'Add Files' button - it doesn't exist",
                    "Don't click files one by one - use Ctrl+A"
                ]
            }
        }


class HumanFeedback(BaseModel):
    """
    Human feedback on agent execution

    Can be approval, correction, or guidance
    """
    feedback_id: str = Field(default_factory=lambda: f"fb_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    session_id: str = Field(..., description="Session identifier")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())

    # Feedback type
    approved: bool = Field(..., description="Whether human approved the action")
    correction: Optional[Dict[str, Any]] = Field(None, description="Corrected action if not approved")
    reasoning: str = Field(..., description="Human's explanation")

    # Detailed procedural guidance (optional)
    procedural_guidance: Optional[ProceduralGuidance] = Field(None, description="Step-by-step procedure if provided")

    # Context
    original_action: Dict[str, Any] = Field(..., description="Action being evaluated")
    agent_confidence: float = Field(..., description="Agent's confidence when asking")

    class Config:
        json_schema_extra = {
            "example": {
                "feedback_id": "fb_20250115_103000",
                "session_id": "session_001",
                "approved": False,
                "correction": {"tool_name": "Shortcut-Tool", "shortcut": ["ctrl", "m"]},
                "reasoning": "Use keyboard shortcut instead of clicking",
                "original_action": {"tool_name": "Click-Tool", "loc": [450, 300]},
                "agent_confidence": 0.4
            }
        }


class VerifiedSkillMetadata(BaseModel):
    """
    Metadata for a verified skill

    Tracks provenance and success rate
    """
    verified_by: str = Field("human", description="Who verified this skill")
    verified_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    session_id: str = Field(..., description="Session where skill was created")

    # Learning sources that contributed
    human_feedbacks_count: int = Field(0, description="Number of human corrections used")
    agent_recoveries_count: int = Field(0, description="Number of self-recoveries used")

    # Usage tracking
    times_used: int = Field(0, description="How many times skill has been used")
    success_count: int = Field(0, description="How many times it succeeded")

    # Success rate (updated over time)
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


class HumanInterruptLearning(BaseModel):
    """
    Learning from human interrupt/correction

    Used when human stops execution and provides corrected action
    Fields match LearningEntry for direct conversion
    """
    task: str = Field(..., description="Task being executed")
    step_num: int = Field(..., description="Step number where interrupt occurred")
    original_action: Dict[str, Any] = Field(..., description="Original action that was corrected")
    corrected_action: Dict[str, Any] = Field(..., description="Corrected action from human")
    human_reasoning: str = Field(..., description="Human's explanation for correction")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())

    class Config:
        json_schema_extra = {
            "example": {
                "task": "Step 5",
                "step_num": 5,
                "original_action": {"tool_name": "Click-Tool", "loc": [450, 300]},
                "corrected_action": {"tool_name": "Shortcut-Tool", "shortcut": ["ctrl", "m"]},
                "human_reasoning": "Button not visible, use shortcut instead"
            }
        }


class FailureLearning(BaseModel):
    """
    Learning from execution failure

    Captures failure context. Related docs are retrieved dynamically during planning,
    not stored with the learning. The LLM planner will use failure history to determine
    alternative approaches - we don't try to track recovery at step level.
    """
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
                "original_error": "Element 'Add Files' button not found"
            }
        }


class TaskVerification(BaseModel):
    """
    Human verification of task completion

    Determines if workflow becomes a verified skill
    """
    verification_id: str = Field(default_factory=lambda: f"verify_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    session_id: str = Field(..., description="Session being verified")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())

    # Verification result
    status: VerificationStatus = Field(..., description="Completion status")
    reasoning: str = Field(..., description="Human's explanation of status")

    # Details for partial completion
    successful_steps: Optional[List[int]] = Field(None, description="Step numbers that worked")
    failed_steps: Optional[List[int]] = Field(None, description="Step numbers that failed")

    # Whether to create verified skill
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


if __name__ == "__main__":
    """Test schemas"""

    print("Testing Feedback Schemas\n")

    # Test 1: Learning Entry (human proactive)
    print("1. Human Proactive Learning:")
    learning1 = LearningEntry(
        learning_id="learn_001",
        session_id="session_test",
        source=LearningSource.HUMAN_PROACTIVE,
        task="Concatenate MF4 files",
        step_num=5,
        original_action={"tool_name": "Click-Tool", "loc": [450, 300]},
        corrected_action={"tool_name": "Shortcut-Tool", "shortcut": ["ctrl", "m"]},
        human_reasoning="Button not visible, use shortcut"
    )
    print(f"   ID: {learning1.learning_id}")
    print(f"   Source: {learning1.source}")
    print(f"   Reasoning: {learning1.human_reasoning}\n")

    # Test 2: Learning Entry (execution failure)
    print("2. Execution Failure Learning:")
    learning2 = LearningEntry(
        learning_id="learn_002",
        session_id="session_test",
        source=LearningSource.EXECUTION_FAILURE,
        task="Concatenate MF4 files",
        step_num=15,
        original_action={"tool_name": "Click-Tool", "loc": [500, 400]},
        original_error="Element not found",
        recovery_approach="Used File->Open menu instead"
    )
    print(f"   ID: {learning2.learning_id}")
    print(f"   Source: {learning2.source}")
    print(f"   Recovery: {learning2.recovery_approach}\n")

    # Test 3: Human Feedback
    print("3. Human Feedback:")
    feedback = HumanFeedback(
        session_id="session_test",
        approved=False,
        correction={"tool_name": "Shortcut-Tool", "shortcut": ["ctrl", "m"]},
        reasoning="Keyboard shortcut is more reliable",
        original_action={"tool_name": "Click-Tool", "loc": [450, 300]},
        agent_confidence=0.4
    )
    print(f"   ID: {feedback.feedback_id}")
    print(f"   Approved: {feedback.approved}")
    print(f"   Reasoning: {feedback.reasoning}\n")

    # Test 4: Verified Skill Metadata
    print("4. Verified Skill Metadata:")
    metadata = VerifiedSkillMetadata(
        session_id="session_test",
        human_feedbacks_count=2,
        agent_recoveries_count=1,
        times_used=5,
        success_count=5
    )
    print(f"   Verified at: {metadata.verified_at}")
    print(f"   Human feedbacks: {metadata.human_feedbacks_count}")
    print(f"   Agent recoveries: {metadata.agent_recoveries_count}")
    print(f"   Success rate: {metadata.success_rate}\n")

    # Test 5: Task Verification
    print("5. Task Verification:")
    verification = TaskVerification(
        session_id="session_test",
        status=VerificationStatus.COMPLETED,
        reasoning="All steps executed successfully",
        create_skill=True
    )
    print(f"   ID: {verification.verification_id}")
    print(f"   Status: {verification.status}")
    print(f"   Create skill: {verification.create_skill}\n")

    # Test 6: Confidence Levels
    print("6. Confidence Levels:")
    for level in ConfidenceLevel:
        print(f"   {level.value}")

    print("\n[SUCCESS] All schemas validated!")
