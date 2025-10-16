"""
A2A-inspired communication protocol for agent-human interaction

Provides standardized JSON-RPC 2.0 format for:
- Agent requests to human (approvals, guidance)
- Human responses (corrections, approvals)
- Notifications (state updates, interrupts)
"""

from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
import uuid
from datetime import datetime
import json
import os


class RequestMessage(BaseModel):
    """A2A-inspired request format (agent → human)"""
    jsonrpc: str = "2.0"
    method: str = Field(..., description="Method name (e.g., 'human.request_approval')")
    params: Dict[str, Any] = Field(..., description="Request parameters")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())

    class Config:
        json_schema_extra = {
            "example": {
                "jsonrpc": "2.0",
                "method": "human.request_approval",
                "params": {
                    "agent_id": "executor",
                    "confidence": 0.4,
                    "proposed_action": {"tool_name": "Click-Tool", "tool_arguments": {"loc": [450, 300]}},
                    "justification": "Uncertain about button location"
                },
                "id": "req_12345",
                "timestamp": "2025-01-15T10:30:00"
            }
        }


class ResponseMessage(BaseModel):
    """A2A-inspired response format (human → agent)"""
    jsonrpc: str = "2.0"
    result: Optional[Dict[str, Any]] = Field(None, description="Success result")
    error: Optional[Dict[str, Any]] = Field(None, description="Error in JSON-RPC format")
    id: str = Field(..., description="Request ID this response is for")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())

    class Config:
        json_schema_extra = {
            "example": {
                "jsonrpc": "2.0",
                "result": {
                    "approved": False,
                    "correction": {"tool_name": "Shortcut-Tool", "shortcut": ["ctrl", "m"]},
                    "reasoning": "Use Ctrl+M shortcut instead"
                },
                "id": "req_12345",
                "timestamp": "2025-01-15T10:31:00"
            }
        }


class NotificationMessage(BaseModel):
    """A2A-inspired notification (no response expected)"""
    jsonrpc: str = "2.0"
    method: str = Field(..., description="Notification type (e.g., 'agent.state_update')")
    params: Dict[str, Any] = Field(..., description="Notification data")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())

    class Config:
        json_schema_extra = {
            "example": {
                "jsonrpc": "2.0",
                "method": "agent.interrupt",
                "params": {
                    "from": "human",
                    "reason": "Wrong button clicked",
                    "correction": {"type": "skip_step"}
                },
                "timestamp": "2025-01-15T10:32:00"
            }
        }


class CommunicationProtocol:
    """
    Simple A2A-inspired protocol for agent-human communication

    Features:
    - Standardized JSON-RPC 2.0 message format
    - Request-response pairing (via id)
    - Notification support (one-way messages)
    - Complete audit trail
    """

    def __init__(self, log_dir: str = "agent/feedback/memory/message_logs"):
        """
        Initialize communication protocol

        Args:
            log_dir: Directory to store message logs
        """
        self.log_dir = log_dir
        self.message_log: List[Dict[str, Any]] = []
        self.pending_requests: Dict[str, RequestMessage] = {}

        # Create log directory
        os.makedirs(log_dir, exist_ok=True)

    def create_request(
        self,
        method: str,
        params: Dict[str, Any],
        request_id: Optional[str] = None
    ) -> RequestMessage:
        """
        Create A2A-inspired request

        Args:
            method: Method name (e.g., 'human.request_approval')
            params: Request parameters
            request_id: Optional custom request ID

        Returns:
            RequestMessage instance
        """
        request = RequestMessage(
            method=method,
            params=params,
            id=request_id or str(uuid.uuid4())
        )

        # Log request
        self.message_log.append(request.model_dump())
        self.pending_requests[request.id] = request

        return request

    def create_response(
        self,
        request_id: str,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[Dict[str, Any]] = None
    ) -> ResponseMessage:
        """
        Create A2A-inspired response

        Args:
            request_id: ID of the request this responds to
            result: Success result (mutually exclusive with error)
            error: Error result in JSON-RPC format

        Returns:
            ResponseMessage instance
        """
        response = ResponseMessage(
            id=request_id,
            result=result,
            error=error
        )

        # Log response
        self.message_log.append(response.model_dump())

        # Remove from pending
        if request_id in self.pending_requests:
            del self.pending_requests[request_id]

        return response

    def create_notification(
        self,
        method: str,
        params: Dict[str, Any]
    ) -> NotificationMessage:
        """
        Create A2A-inspired notification (no response expected)

        Args:
            method: Notification type (e.g., 'agent.state_update')
            params: Notification data

        Returns:
            NotificationMessage instance
        """
        notification = NotificationMessage(
            method=method,
            params=params
        )

        # Log notification
        self.message_log.append(notification.model_dump())

        return notification

    def get_message_log(self) -> List[Dict[str, Any]]:
        """Get complete message log for audit trail"""
        return self.message_log.copy()

    def get_pending_requests(self) -> List[RequestMessage]:
        """Get all requests awaiting response"""
        return list(self.pending_requests.values())

    def save_session_log(self, session_id: str):
        """
        Save message log for a session

        Args:
            session_id: Session identifier
        """
        log_file = os.path.join(self.log_dir, f"{session_id}_messages.json")

        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump({
                "session_id": session_id,
                "message_count": len(self.message_log),
                "messages": self.message_log,
                "saved_at": datetime.now().isoformat()
            }, f, indent=2)

        print(f"  [Saved] message log: {len(self.message_log)} messages -> {os.path.basename(log_file)}")

    def load_session_log(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Load message log from a previous session

        Args:
            session_id: Session identifier

        Returns:
            List of messages
        """
        log_file = os.path.join(self.log_dir, f"{session_id}_messages.json")

        if not os.path.exists(log_file):
            return []

        with open(log_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get("messages", [])

    def clear_log(self):
        """Clear current message log"""
        self.message_log.clear()
        self.pending_requests.clear()


if __name__ == "__main__":
    """Test communication protocol"""

    protocol = CommunicationProtocol()

    # Test 1: Request-Response
    print("Test 1: Agent requests approval from human")
    request = protocol.create_request(
        method="human.request_approval",
        params={
            "agent_id": "executor",
            "confidence": 0.4,
            "proposed_action": {"tool_name": "Click-Tool", "loc": [450, 300]},
            "justification": "Uncertain about button location"
        }
    )
    print(f"  Created request: {request.id}")
    print(f"  Pending requests: {len(protocol.get_pending_requests())}")

    response = protocol.create_response(
        request_id=request.id,
        result={
            "approved": False,
            "correction": {"tool_name": "Shortcut-Tool", "shortcut": ["ctrl", "m"]},
            "reasoning": "Use Ctrl+M shortcut instead"
        }
    )
    print(f"  Created response for: {response.id}")
    print(f"  Pending requests after response: {len(protocol.get_pending_requests())}")

    # Test 2: Notification
    print("\nTest 2: Human interrupt notification")
    notification = protocol.create_notification(
        method="agent.interrupt",
        params={
            "from": "human",
            "reason": "Wrong action detected",
            "correction": {"type": "skip_step"}
        }
    )
    print(f"  Created notification: {notification.method}")

    # Test 3: Audit trail
    print("\nTest 3: Audit trail")
    log = protocol.get_message_log()
    print(f"  Total messages: {len(log)}")
    for i, msg in enumerate(log, 1):
        print(f"    {i}. {msg.get('method', 'response')} at {msg['timestamp']}")

    # Test 4: Save/load
    print("\nTest 4: Save session log")
    protocol.save_session_log("test_session_001")

    loaded = protocol.load_session_log("test_session_001")
    print(f"  Loaded {len(loaded)} messages from saved session")
