"""
UNKNOWN Resolution Contracts, Enums, and Error Hierarchy for TarkaRaksha (T12).
Enforces the core invariant:
UNKNOWN is a legitimate first-class state, not a defect to be guessed away.
Resolution is strictly achieved through safe, non-side-effecting observation
and deterministic evidence reconciliation.
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.domain.models import (
    CanonicalEvent,
    Evidence,
    IntegrityResult,
    Money,
)

# Maximum resolution attempts before escalating to ABSTAIN (§9, §18)
MAX_RESOLUTION_ATTEMPTS: int = 3


class ResolutionCategory(str, Enum):
    """
    Deterministic classification of UNKNOWN resolution possibilities (§4).
    """
    RESOLVABLE = "RESOLVABLE"          # Resolvable by additional authoritative provider observation
    REMAINS_UNKNOWN = "REMAINS_UNKNOWN" # Authoritative evidence is still missing or provider unreachable
    ABSTAIN = "ABSTAIN"                # Unsafe to proceed (e.g. contract expired, irreconcilable conflict, attempts exhausted)


class ResolutionStrategy(str, Enum):
    """
    Non-side-effecting observation strategies to resolve UNKNOWN state (§8).
    """
    FETCH_PAYMENT = "FETCH_PAYMENT"              # Query authoritative provider payment state by payment ID
    FETCH_ORDER_PAYMENTS = "FETCH_ORDER_PAYMENTS" # Query all payments for the order on the provider gateway
    RECONCILE_EVIDENCE = "RECONCILE_EVIDENCE"     # Re-evaluate evidence hierarchy against newly ingested records
    HOLD_OBSERVATION = "HOLD_OBSERVATION"         # Cease observation to prevent financial or authorization risk


class ResolutionDiagnosis(BaseModel):
    """
    Deterministic diagnostic assessment of why a transaction is UNKNOWN and what safe strategy to apply.
    """
    category: ResolutionCategory
    strategy: ResolutionStrategy
    missing_fields: List[str] = Field(default_factory=list)
    conflicting_fields: List[str] = Field(default_factory=list)
    reason: str
    current_attempt: int = 1
    max_attempts: int = MAX_RESOLUTION_ATTEMPTS

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )


class ResolutionResult(BaseModel):
    """
    Outcome of an UNKNOWN resolution execution.
    Contains any newly ingested canonical evidence and the deterministic re-evaluation result.
    """
    resolution_id: str
    category: ResolutionCategory
    strategy: ResolutionStrategy
    new_evidence: List[Evidence] = Field(default_factory=list)
    new_events: List[CanonicalEvent] = Field(default_factory=list)
    integrity_result: IntegrityResult
    is_idempotent_replay: bool = False
    resolved_at: datetime
    details: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )

    @field_validator("resolved_at", mode="before")
    @classmethod
    def validate_timezone(cls, v: Any) -> datetime:
        if isinstance(v, str):
            dt = datetime.fromisoformat(v)
        elif isinstance(v, datetime):
            dt = v
        else:
            raise TypeError(f"Timestamp must be datetime or ISO string, got {type(v).__name__}")
        if dt.tzinfo is None:
            raise ValueError("resolved_at must be timezone-aware (e.g. UTC)")
        return dt


# --- UNKNOWN Resolution Exception Hierarchy ---

class ResolutionError(Exception):
    """Base exception for UNKNOWN resolution operations."""
    pass


class InvalidResolutionStateError(ResolutionError):
    """Raised when UNKNOWN resolution is attempted from an illegal lifecycle state."""
    pass


class ResolutionExhaustedError(ResolutionError):
    """Raised when resolution attempt bounds have been exhausted."""
    pass


class ResolutionConflictError(ResolutionError):
    """Raised when contradictory authoritative evidence cannot be reconciled safely."""
    pass
