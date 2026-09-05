"""Authoritative Domain Contracts for I7 — Bounded Agentic Negotiation / Replanning.

Principle:
NEGOTIATION MAY CHANGE THE PROPOSAL.
NEGOTIATION MUST NEVER CHANGE THE AUTHORIZATION.

The immutable IntentContract remains the hard authorization boundary.
Zero payment authorization authority resides in the negotiation layer.
"""
from datetime import datetime, timezone
from enum import Enum
import hashlib
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.domain.models.enums import IntegrityStatus
from backend.app.domain.models.money import Money


class NegotiationState(str, Enum):
    """Deterministic states of the bounded negotiation / replanning process."""
    NOT_STARTED = "NOT_STARTED"
    DRIFT_DETECTED = "DRIFT_DETECTED"
    REPLAN_REQUESTED = "REPLAN_REQUESTED"
    COUNTER_OFFER_RECEIVED = "COUNTER_OFFER_RECEIVED"
    REVALIDATING = "REVALIDATING"
    COMPLETED = "COMPLETED"      # Deterministic revalidation achieved PASS
    ABSTAINED = "ABSTAINED"      # Bounded limits exhausted or infeasible constraints
    ESCALATED = "ESCALATED"      # Human / buyer clarification required
    FAILED = "FAILED"            # Invariant breach or security rejection


class NegotiationViolationCode(str, Enum):
    """Deterministic violation codes for negotiation boundary breaches."""
    MAX_ROUNDS_EXCEEDED = "MAX_ROUNDS_EXCEEDED"
    MAX_REPLANS_EXCEEDED = "MAX_REPLANS_EXCEEDED"
    BUDGET_ESCALATION_ATTEMPT = "BUDGET_ESCALATION_ATTEMPT"
    UNAUTHORIZED_SUBSTITUTION = "UNAUTHORIZED_SUBSTITUTION"
    QUANTITY_ESCALATION = "QUANTITY_ESCALATION"
    CURRENCY_MUTATION = "CURRENCY_MUTATION"
    INTENT_MISMATCH = "INTENT_MISMATCH"
    TRANSACTION_MISMATCH = "TRANSACTION_MISMATCH"
    ATTEMPT_REUSE = "ATTEMPT_REUSE"
    PASS_INJECTION_ATTEMPT = "PASS_INJECTION_ATTEMPT"
    UNAUTHORIZED_PAYMENT_CLAIM = "UNAUTHORIZED_PAYMENT_CLAIM"
    TIX_BYPASS = "TIX_BYPASS"
    HISTORICAL_PROPOSAL_MUTATED = "HISTORICAL_PROPOSAL_MUTATED"


class NegotiationPolicy(BaseModel):
    """Immutable policy defining bounded limits for agentic negotiation."""
    max_rounds: int = 3
    max_replans: int = 3
    allow_substitutions: bool = True
    allow_partial: bool = False
    timeout_seconds: int = 300

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    @field_validator("max_rounds", "max_replans")
    @classmethod
    def validate_positive_bounds(cls, v: int) -> int:
        if isinstance(v, bool) or not isinstance(v, int) or v < 1 or v > 10:
            raise ValueError("Negotiation rounds/replans must be an integer between 1 and 10")
        return v


class NegotiationRoundRecord(BaseModel):
    """Immutable chronological audit record of an individual negotiation round."""
    round_number: int
    transaction_id: str
    intent_id: str
    attempt_id: str
    state: NegotiationState
    buyer_proposal_id: Optional[str] = None
    merchant_response_id: Optional[str] = None
    proposed_sku: Optional[str] = None
    proposed_quantity: Optional[int] = None
    offered_total: Optional[Money] = None
    drift_violations: List[str] = Field(default_factory=list)
    mrdp_id: Optional[str] = None
    tix_message_ids: List[str] = Field(default_factory=list)
    timestamp: datetime
    rationale: str = ""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    @field_validator("round_number")
    @classmethod
    def validate_round_number(cls, v: int) -> int:
        if isinstance(v, bool) or not isinstance(v, int) or v < 1:
            raise ValueError("round_number must be a positive integer >= 1")
        return v

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
            raise ValueError("Timestamp must be timezone-aware (e.g. UTC)")
        return dt


class NegotiationSession(BaseModel):
    """Immutable snapshot of the complete negotiation lifecycle."""
    session_id: str
    transaction_id: str
    intent_id: str
    buyer_agent_id: str
    merchant_id: str
    state: NegotiationState
    current_round: int = 0
    policy: NegotiationPolicy = Field(default_factory=NegotiationPolicy)
    rounds: List[NegotiationRoundRecord] = Field(default_factory=list)
    original_verdict: Optional[IntegrityStatus] = None
    original_violations: List[str] = Field(default_factory=list)
    final_verdict: Optional[IntegrityStatus] = None
    final_mrdp_id: Optional[str] = None
    is_settled: bool = False
    termination_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    @field_validator("session_id", "transaction_id", "intent_id", "buyer_agent_id", "merchant_id")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Identifier fields cannot be empty or whitespace.")
        return v.strip()

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def validate_timezone(cls, v: Any) -> datetime:
        if isinstance(v, str):
            dt = datetime.fromisoformat(v)
        elif isinstance(v, datetime):
            dt = v
        else:
            raise TypeError(f"Timestamp must be datetime or ISO string, got {type(v).__name__}")
        if dt.tzinfo is None:
            raise ValueError("Timestamp must be timezone-aware (e.g. UTC)")
        return dt
