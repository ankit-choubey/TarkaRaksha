"""
Recovery Contracts, Error Hierarchy, and Result Models for TarkaRaksha (T11).
Enforces the safety principle:
Recovery subsystem is an authoritative control plane, not an autonomous money-moving agent.
Original authorized intent is strictly immutable and cannot be expanded.
"""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.domain.models import (
    ActionRequest,
    ActionType,
    CanonicalEvent,
    Evidence,
    Money,
    RecoveryProposal,
    TransactionState,
)


# Maximum allowed recovery attempts per transaction before forcing ABSTAIN (§7.42, §9.50)
MAX_RECOVERY_ATTEMPTS: int = 3


# --- Recovery Exception Hierarchy ---

class RecoveryError(Exception):
    """Base exception for all recovery control plane failures."""
    pass


class UnsafeActionRequestError(RecoveryError):
    """Raised when an ActionRequest attempts to violate financial, temporal, or authority bounds."""
    pass


class NonRecoverableDriftError(RecoveryError):
    """Raised when an integrity violation cannot be safely repaired within the authorized envelope."""
    pass


class RecoveryExhaustedError(RecoveryError):
    """Raised when recovery attempts reach or exceed MAX_RECOVERY_ATTEMPTS (3)."""
    pass


class RecoveryIdempotencyError(RecoveryError):
    """Raised when recovery execution encounters a conflicting duplicate idempotency key."""
    pass


class InvalidRecoveryStateError(RecoveryError):
    """Raised when recovery is attempted from an illegal lifecycle state (e.g. CREATED, PASS, ABSTAIN)."""
    pass


# --- Recovery Classification Enums & Models ---

class RecoverabilityStatus(str, Enum):
    """Deterministic classification of whether an integrity divergence is repairable."""
    RECOVERABLE = "RECOVERABLE"
    NON_RECOVERABLE = "NON_RECOVERABLE"
    UNKNOWN = "UNKNOWN"
    ABSTAIN = "ABSTAIN"


class RecoveryClassification(BaseModel):
    """
    Deterministic assessment of a transaction's recoverability.
    Computed strictly from explicit inputs (IntentContract, IntegrityResult, MRDP, attempts).
    """
    status: RecoverabilityStatus
    is_recoverable: bool
    reason: str
    recommended_action: Optional[ActionType] = None
    max_allowed_amount: Optional[Money] = None
    requires_operator_approval: bool = False
    current_attempt: int = 1
    max_attempts: int = MAX_RECOVERY_ATTEMPTS

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )


class RecoveryExecutionResult(BaseModel):
    """
    Factual execution result returned by the RecoveryExecutor.
    Contains new observations, side-effect identifiers, and canonical evidence.
    NEVER declares PASS independently.
    """
    execution_id: str
    action_request: ActionRequest
    status: str  # "SUCCESS", "FAILED", "ABSTAINED", "DUPLICATE"
    evidence: List[Evidence] = Field(default_factory=list)
    events: List[CanonicalEvent] = Field(default_factory=list)
    executed_at: datetime
    is_idempotent_replay: bool = False
    details: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )

    @field_validator("executed_at", mode="before")
    @classmethod
    def validate_timezone(cls, v: Any) -> datetime:
        if isinstance(v, str):
            dt = datetime.fromisoformat(v)
        elif isinstance(v, datetime):
            dt = v
        else:
            raise TypeError(f"Timestamp must be datetime or ISO string, got {type(v).__name__}")
        if dt.tzinfo is None:
            raise ValueError("executed_at must be timezone-aware (UTC)")
        return dt
