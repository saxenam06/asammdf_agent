"""
Human-in-the-loop feedback system for autonomous workflows
"""

from .communication_protocol import (
    CommunicationProtocol,
    RequestMessage,
    ResponseMessage,
    NotificationMessage
)

from .schemas import (
    ConfidenceLevel,
    LearningSource,
    VerificationStatus,
    LearningEntry,
    HumanFeedback,
    VerifiedSkillMetadata
)

__all__ = [
    'CommunicationProtocol',
    'RequestMessage',
    'ResponseMessage',
    'NotificationMessage',
    'ConfidenceLevel',
    'LearningSource',
    'VerificationStatus',
    'LearningEntry',
    'HumanFeedback',
    'VerifiedSkillMetadata'
]
