"""Authoritative domain contracts for I8 Transaction Binding.

Binds:
- intent_id
- agent_id
- merchant_id
- transaction_id
- order_id
- payment_id
- attempt_id

Zero LLM involvement. Deterministic integrity verification only.
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.domain.models.enums import IntegrityStatus
from backend.app.domain.models.evidence import Evidence


class BindingStatus(str, Enum):
    """Integrity state of a bound entity relationship."""
    VALID = "VALID"
    DRIFT = "DRIFT"
    UNKNOWN = "UNKNOWN"


class AttemptStatus(str, Enum):
    """Lifecycle status of a checkout execution attempt."""
    INITIATED = "INITIATED"
    CONSUMED = "CONSUMED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"


class BindingViolationCode(str, Enum):
    """Canonical error / violation codes for binding discrepancies."""
    INTENT_MISMATCH = "INTENT_MISMATCH"
    AGENT_MISMATCH = "AGENT_MISMATCH"
    MERCHANT_MISMATCH = "MERCHANT_MISMATCH"
    TRANSACTION_MISMATCH = "TRANSACTION_MISMATCH"
    ORDER_MISMATCH = "ORDER_MISMATCH"
    PAYMENT_MISMATCH = "PAYMENT_MISMATCH"
    ATTEMPT_MISMATCH = "ATTEMPT_MISMATCH"
    DUPLICATE_ATTEMPT_REUSED = "DUPLICATE_ATTEMPT_REUSED"
    CROSS_TRANSACTION_REUSE = "CROSS_TRANSACTION_REUSE"
    AMOUNT_NON_SUFFICIENCY = "AMOUNT_NON_SUFFICIENCY"
    UNRESOLVED_PROVIDER_STATE = "UNRESOLVED_PROVIDER_STATE"
    FORMAT_INVALID = "FORMAT_INVALID"


class BindingContext(BaseModel):
    """Authoritative binding context anchored at transaction creation."""
    intent_id: str
    agent_id: str
    merchant_id: str
    transaction_id: str
    order_id: str
    attempt_id: str = "att_1"
    created_at: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    @field_validator("intent_id", "agent_id", "merchant_id", "transaction_id", "order_id", "attempt_id")
    @classmethod
    def validate_non_empty_strings(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Binding context identifiers cannot be empty or whitespace")
        return v.strip()

    @field_validator("created_at")
    @classmethod
    def validate_timezone(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("created_at must be timezone-aware (UTC)")
        return v


class PaymentBindingClaim(BaseModel):
    """Claimed binding tuple submitted during payment completion or verification."""
    intent_id: str
    agent_id: str
    merchant_id: str
    transaction_id: str
    order_id: str
    payment_id: str
    attempt_id: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    @field_validator("intent_id", "agent_id", "merchant_id", "transaction_id", "order_id", "payment_id", "attempt_id")
    @classmethod
    def validate_non_empty_strings(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Claim identifiers cannot be empty or whitespace")
        return v.strip()


class AttemptRecord(BaseModel):
    """Immutable audit record of a specific checkout attempt for a transaction."""
    attempt_id: str
    transaction_id: str
    agent_id: str
    merchant_id: str
    status: AttemptStatus
    initiated_at: datetime
    consumed_at: Optional[datetime] = None
    payment_id: Optional[str] = None

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    @field_validator("attempt_id", "transaction_id", "agent_id", "merchant_id")
    @classmethod
    def validate_non_empty_strings(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("AttemptRecord identifiers cannot be empty or whitespace")
        return v.strip()


class BindingVerificationOutcome(BaseModel):
    """Structured deterministic outcome of evaluating a PaymentBindingClaim against authoritative context."""
    is_valid: bool
    status: IntegrityStatus  # PASS, DRIFT, UNKNOWN
    violations: List[BindingViolationCode] = Field(default_factory=list)
    details: Dict[str, Any] = Field(default_factory=dict)
    explanation: str
    verified_at: datetime

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    @field_validator("verified_at")
    @classmethod
    def validate_timezone(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("verified_at must be timezone-aware (UTC)")
        return v

    def to_evidence(self, intent_id: Optional[str] = None, transaction_id: Optional[str] = None) -> Evidence:
        """Convert binding verification outcome into a canonical Evidence record."""
        from backend.app.domain.models.enums import EvidenceAuthority, EvidenceSource

        eff_intent_id = intent_id or self.details.get("intent_id") or "intent_unspecified"
        return Evidence(
            evidence_id=f"ev_binding_{self.verified_at.strftime('%Y%m%d%H%M%S%f')}",
            intent_id=eff_intent_id,
            transaction_id=transaction_id or self.details.get("transaction_id"),
            source=EvidenceSource.SYSTEM,
            authority=EvidenceAuthority.SYSTEM_DERIVED,
            field_name="transaction_binding",
            field_value={
                "is_valid": self.is_valid,
                "status": self.status.value,
                "violations": [v.value for v in self.violations],
                "explanation": self.explanation,
                "details": self.details,
            },
            observed_at=self.verified_at,
            is_authoritative=True,
            provenance={
                "verifier": "TransactionBindingVerifier",
                "rules": ["I8_BINDING_INTEGRITY"],
            },
        )
