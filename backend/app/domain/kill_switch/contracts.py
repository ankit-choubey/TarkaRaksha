"""Authoritative domain contracts for I9 Deterministic Kill Switch / Execution Safety Control.

Provides execution-control state models, trigger enums, immutable audit records,
and revalidation contracts.

Invariant: AI proposes -> evidence proves -> deterministic logic decides.
Zero LLM involvement in execution safety control.
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.domain.models.enums import EvidenceAuthority
from backend.app.domain.models.evidence import Evidence


class KillSwitchState(str, Enum):
    """
    Canonical deterministic execution-control state for a transaction context.
    Strictly distinguishes SAFE TO CONTINUE from EXECUTION BLOCKED.
    """
    RUNNING = "RUNNING"                   # Safe to continue; execution permitted
    PAUSED = "PAUSED"                     # Temporarily suspended (e.g. administrative pause or observation hold)
    REQUIRES_REVALIDATION = "REQUIRES_REVALIDATION" # Blocked pending authoritative revalidation (e.g. repeated UNKNOWN or expired auth)
    KILLED = "KILLED"                     # Execution terminated / blocked due to critical breach or explicit kill


class KillTrigger(str, Enum):
    """Authoritative triggers for safety intervention and execution blocking."""
    CRITICAL_DRIFT = "CRITICAL_DRIFT"                 # Integrity drift detected by deterministic evaluation
    REPEATED_UNKNOWN = "REPEATED_UNKNOWN"             # Missing or unresolved evidence beyond tolerance
    BINDING_VIOLATION = "BINDING_VIOLATION"           # Identity/context mismatch from I8 verifier
    POLICY_VIOLATION = "POLICY_VIOLATION"             # Policy-as-code violation (e.g. max cap exceeded)
    CAPABILITY_VIOLATION = "CAPABILITY_VIOLATION"     # Action outside declared agent capability
    EXPIRED_AUTHORIZATION = "EXPIRED_AUTHORIZATION"   # IntentContract or offer expired
    ATTEMPT_LIMIT_EXCEEDED = "ATTEMPT_LIMIT_EXCEEDED" # Max attempt limit reached
    ADMINISTRATIVE_KILL = "ADMINISTRATIVE_KILL"       # Explicit authorized control-plane kill command
    ADMINISTRATIVE_PAUSE = "ADMINISTRATIVE_PAUSE"     # Explicit authorized control-plane pause command


class ExecutionDecision(str, Enum):
    """Deterministic verdict on whether an execution step is permitted to proceed."""
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    REQUIRE_REVALIDATION = "REQUIRE_REVALIDATION"


class ExecutionBlockedError(ValueError):
    """Raised when an operation or financial action is attempted while execution is blocked/killed/paused."""
    def __init__(self, message: str, state: KillSwitchState, trigger: Optional[KillTrigger] = None):
        super().__init__(message)
        self.state = state
        self.trigger = trigger


class UnauthorizedResumeError(PermissionError):
    """Raised when resuming a blocked or killed transaction is attempted without proper authority or valid revalidation."""
    pass


class KillSwitchRecord(BaseModel):
    """
    Immutable, replay-compatible audit trail record for a kill switch transition or decision.
    Captures: WHAT happened, WHY execution stopped, WHICH context was affected,
    WHO/WHAT initiated it, WHEN it occurred, and WHAT revalidation is required.
    """
    record_id: str
    transaction_id: str
    prior_state: KillSwitchState
    resulting_state: KillSwitchState
    decision: ExecutionDecision
    trigger: Optional[KillTrigger] = None
    reason: str
    triggered_by: str = "SYSTEM"
    authority: EvidenceAuthority = EvidenceAuthority.AUTHORITATIVE
    timestamp: datetime
    details: Dict[str, Any] = Field(default_factory=dict)
    revalidation_requirements: Optional[List[str]] = None

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    @field_validator("record_id", "transaction_id", "reason", "triggered_by")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("String identifiers and reasons cannot be empty or whitespace")
        return v.strip()

    @field_validator("timestamp")
    @classmethod
    def validate_timezone(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("Timestamp must be timezone-aware (UTC)")
        return v


class RevalidationRequest(BaseModel):
    """
    Formal, authenticated request to revalidate and resume a blocked transaction.
    Requires explicit context matching to prevent cross-context revalidation.
    """
    request_id: str
    transaction_id: str
    intent_id: str
    agent_id: str
    merchant_id: str
    actor: str
    evidence: List[Evidence] = Field(default_factory=list)
    reason: str
    requested_at: datetime

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    @field_validator("request_id", "transaction_id", "intent_id", "agent_id", "merchant_id", "actor", "reason")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("All context identifiers and reason must be non-empty")
        return v.strip()

    @field_validator("requested_at")
    @classmethod
    def validate_timezone(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("requested_at must be timezone-aware (UTC)")
        return v


class RevalidationOutcome(BaseModel):
    """Structured deterministic outcome of evaluating a RevalidationRequest."""
    is_valid: bool
    decision: ExecutionDecision
    explanation: str
    evaluated_at: datetime
    violations: List[str] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    @field_validator("evaluated_at")
    @classmethod
    def validate_timezone(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("evaluated_at must be timezone-aware (UTC)")
        return v
