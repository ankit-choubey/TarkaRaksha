"""
Domain models and exceptions for TarkaRaksha transaction state machine.
Defines transition records, transition requests, and state machine exceptions.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.domain.models.enums import TransactionState, ActionType, IntegrityStatus


class StateMachineError(Exception):
    """Base exception for all state machine domain errors."""
    pass


class InvalidStateTransitionError(StateMachineError):
    """
    Raised when an illegal or unsupported state transition is attempted.
    Includes current state, attempted destination state, and failure reason.
    """
    def __init__(self, from_state: TransactionState, to_state: TransactionState, reason: str):
        self.from_state = from_state
        self.to_state = to_state
        self.reason = reason
        super().__init__(
            f"Invalid state transition from {from_state.value} to {to_state.value}: {reason}"
        )


class SafetyInvariantViolationError(StateMachineError):
    """
    Raised when an action or transition violates a hard safety invariant
    (e.g., attempting a financial capture while in UNKNOWN or ABSTAIN state).
    """
    def __init__(self, state: TransactionState, action: Optional[ActionType], reason: str):
        self.state = state
        self.action = action
        self.reason = reason
        action_str = f" for action {action.value}" if action else ""
        super().__init__(
            f"Safety invariant violation in state {state.value}{action_str}: {reason}"
        )


class StateTransitionRecord(BaseModel):
    """
    Immutable audit record of an executed state transition.
    Contains explicit timestamps, transition metadata, and contextual audit proof.
    """
    transition_id: str
    from_state: TransactionState
    to_state: TransactionState
    timestamp: datetime
    reason: str
    triggered_by: str = "SYSTEM"  # e.g., "SYSTEM", "DETERMINISTIC_ENGINE", "AGENT_PROPOSAL", "OPERATOR"
    is_verified: bool = True
    context: Dict[str, Any] = Field(default_factory=dict)
    integrity_status: Optional[IntegrityStatus] = None

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )

    @field_validator("timestamp", mode="before")
    @classmethod
    def validate_timezone(cls, v: Any) -> datetime:
        if isinstance(v, str):
            dt = datetime.fromisoformat(v)
        elif isinstance(v, datetime):
            dt = v
        else:
            raise TypeError(f"Timestamp must be datetime or ISO string, got {type(v).__name__}")
        
        if dt.tzinfo is None:
            raise ValueError("Timestamp must be timezone-aware (e.g., UTC)")
        return dt


class StateTransitionRequest(BaseModel):
    """
    Typed request to perform a state transition.
    Requires explicit target state, reason, and execution context.
    """
    to_state: TransactionState
    reason: str
    timestamp: datetime
    triggered_by: str = "SYSTEM"
    context: Dict[str, Any] = Field(default_factory=dict)
    action_type: Optional[ActionType] = None
    integrity_status: Optional[IntegrityStatus] = None

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )

    @field_validator("timestamp", mode="before")
    @classmethod
    def validate_timezone(cls, v: Any) -> datetime:
        if isinstance(v, str):
            dt = datetime.fromisoformat(v)
        elif isinstance(v, datetime):
            dt = v
        else:
            raise TypeError(f"Timestamp must be datetime or ISO string, got {type(v).__name__}")
        
        if dt.tzinfo is None:
            raise ValueError("Timestamp must be timezone-aware (e.g., UTC)")
        return dt
