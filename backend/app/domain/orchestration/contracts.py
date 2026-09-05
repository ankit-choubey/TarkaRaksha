"""Authoritative Domain Contracts for E3 — Agentic Transaction Lifecycle Orchestration.

Guiding Invariant:
AI proposes. Evidence proves. Deterministic logic decides.

The Orchestration Layer has control-flow authority, not truth/financial authority.
It coordinates the bounded lifecycle connecting:
Buyer Agent -> Intent -> Consumer Gate -> Merchant Agent -> Merchant Gate ->
TIX / Evidence -> Security Guard -> Deterministic Integrity (T04) ->
PASS / DRIFT / UNKNOWN -> Replan / Resolve / Recover / Replay / Complete.
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.domain.models.enums import IntegrityStatus, TransactionState
from backend.app.domain.models.money import Money
from backend.app.domain.models.integrity import IntegrityResult, MRDP


class LifecycleStage(str, Enum):
    """Deterministic stages of the orchestrated agentic transaction lifecycle."""
    INITIALIZED = "INITIALIZED"
    INTENT_BOUND = "INTENT_BOUND"
    BUYER_PROPOSED = "BUYER_PROPOSED"
    CONSUMER_GATE_VERIFIED = "CONSUMER_GATE_VERIFIED"
    MERCHANT_OFFERED = "MERCHANT_OFFERED"
    MERCHANT_GATE_VERIFIED = "MERCHANT_GATE_VERIFIED"
    TIX_COMMITTED = "TIX_COMMITTED"
    SECURITY_EVALUATED = "SECURITY_EVALUATED"
    INTEGRITY_EVALUATED = "INTEGRITY_EVALUATED"
    DRIFT_REPLANNING = "DRIFT_REPLANNING"
    DRIFT_REVALIDATED = "DRIFT_REVALIDATED"
    UNKNOWN_RESOLVING = "UNKNOWN_RESOLVING"
    UNKNOWN_RESOLVED = "UNKNOWN_RESOLVED"
    PAYMENT_BOUND = "PAYMENT_BOUND"
    RECOVERING = "RECOVERING"
    COMPLETED = "COMPLETED"
    ABSTAINED = "ABSTAINED"
    BLOCKED = "BLOCKED"


class LifecyclePolicy(BaseModel):
    """Immutable configuration policy enforcing hard bounds on the agentic lifecycle."""
    max_replans: int = 3
    max_unknown_resolutions: int = 3
    auto_replan_on_drift: bool = True
    auto_resolve_unknown: bool = True
    allow_substitutions: bool = True
    strict_security_kill_switch: bool = True

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    @field_validator("max_replans")
    @classmethod
    def validate_max_replans(cls, v: int) -> int:
        if isinstance(v, bool) or not isinstance(v, int) or v < 1 or v > 10:
            raise ValueError("max_replans must be an integer between 1 and 10")
        return v

    @field_validator("max_unknown_resolutions")
    @classmethod
    def validate_max_resolutions(cls, v: int) -> int:
        if isinstance(v, bool) or not isinstance(v, int) or v < 1 or v > 5:
            raise ValueError("max_unknown_resolutions must be an integer between 1 and 5")
        return v


class LifecycleStepRecord(BaseModel):
    """Immutable chronological audit record of a discrete step in the lifecycle."""
    step_index: int
    stage: LifecycleStage
    action: str
    status: str
    details: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True, extra="forbid")

    @field_validator("timestamp", mode="before")
    @classmethod
    def validate_timestamp(cls, v: Any) -> datetime:
        if isinstance(v, str):
            dt = datetime.fromisoformat(v)
        elif isinstance(v, datetime):
            dt = v
        else:
            raise TypeError(f"timestamp must be datetime or ISO string, got {type(v).__name__}")
        if dt.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware (UTC)")
        return dt


class LifecycleOutcome(BaseModel):
    """Authoritative snapshot outcome produced by the agentic lifecycle orchestrator."""
    transaction_id: str
    intent_id: str
    agent_id: str
    merchant_id: str
    stage: LifecycleStage
    integrity_status: Optional[IntegrityStatus] = None
    transaction_state: TransactionState
    is_terminal: bool = False
    drift_count: int = 0
    replan_rounds: int = 0
    resolution_attempts: int = 0
    mrdp_id: Optional[str] = None
    security_cleared: bool = True
    payment_bound: bool = False
    order_id: Optional[str] = None
    payment_id: Optional[str] = None
    steps: List[LifecycleStepRecord] = Field(default_factory=list)
    history: List[str] = Field(default_factory=list)
    orchestrated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True, extra="forbid")

    @field_validator("orchestrated_at", mode="before")
    @classmethod
    def validate_orchestrated_at(cls, v: Any) -> datetime:
        if isinstance(v, str):
            dt = datetime.fromisoformat(v)
        elif isinstance(v, datetime):
            dt = v
        else:
            raise TypeError(f"orchestrated_at must be datetime or ISO string, got {type(v).__name__}")
        if dt.tzinfo is None:
            raise ValueError("orchestrated_at must be timezone-aware (UTC)")
        return dt


class LifecycleViolationError(Exception):
    """Raised when lifecycle invariants, boundaries, or authority constraints are breached."""
    pass
