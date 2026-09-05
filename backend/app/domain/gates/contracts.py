"""Domain contracts for E2 — Consumer + Merchant Gate Composition.

Governing Principle:
AI proposes. Evidence proves. Deterministic logic decides.
Consumer and Merchant Gates produce structured validation facts.
They are NOT financial authorities and NEVER emit an authoritative PASS.
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.domain.models.money import Money
from backend.app.domain.models.evidence import Evidence, EvidenceAuthority, EvidenceSource


class GateStatus(str, Enum):
    """Deterministic validation status for gate checks.
    
    Note: VALID means validation checks passed without structural or policy errors.
    It is NOT an authoritative financial PASS. Authoritative PASS is decided
    strictly by the deterministic integrity engine (T04).
    """
    VALID = "VALID"
    INVALID = "INVALID"
    UNKNOWN = "UNKNOWN"


class ConsumerCheckType(str, Enum):
    """Categorical validation checks for consumer transaction context."""
    INTENT_BINDING = "INTENT_BINDING"
    AUTHORIZATION_CONSTRAINTS = "AUTHORIZATION_CONSTRAINTS"
    AGENT_IDENTITY = "AGENT_IDENTITY"
    TRANSACTION_CONTEXT = "TRANSACTION_CONTEXT"
    PROPOSAL_VALIDITY = "PROPOSAL_VALIDITY"


class MerchantCheckType(str, Enum):
    """Categorical validation checks for merchant transaction context."""
    MERCHANT_IDENTITY = "MERCHANT_IDENTITY"
    MERCHANT_CAPABILITY = "MERCHANT_CAPABILITY"
    SKU_VALIDITY = "SKU_VALIDITY"
    INVENTORY = "INVENTORY"
    PRICE = "PRICE"
    SHIPPING = "SHIPPING"
    FULFILLMENT = "FULFILLMENT"
    OFFER_EXPIRY = "OFFER_EXPIRY"
    MERCHANT_POLICY = "MERCHANT_POLICY"


class GateValidationFinding(BaseModel):
    """A factual, structured validation observation produced by a gate check."""
    check_type: str
    status: GateStatus
    reason: str
    field_name: Optional[str] = None
    expected_value: Optional[Any] = None
    observed_value: Optional[Any] = None
    details: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


GateFinding = GateValidationFinding


class ConsumerGateResult(BaseModel):
    """Structured validation outcome produced by the Consumer Gate."""
    gate_name: str = "ConsumerGate"
    status: GateStatus
    transaction_id: str
    intent_id: str
    agent_id: str
    is_valid: bool
    findings: List[GateValidationFinding] = Field(default_factory=list)
    validated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    @field_validator("validated_at", mode="before")
    @classmethod
    def validate_timezone(cls, v: Any) -> datetime:
        if isinstance(v, str):
            dt = datetime.fromisoformat(v)
        elif isinstance(v, datetime):
            dt = v
        else:
            raise TypeError(f"Timestamp must be datetime or ISO string, got {type(v).__name__}")
        if dt.tzinfo is None:
            raise ValueError("validated_at must be timezone-aware (e.g. UTC)")
        return dt

    def to_evidence(self, evidence_id: Optional[str] = None) -> Evidence:
        """Converts consumer gate validation facts into an advisory evidence record.
        
        Strict Invariant: Consumer Gate output is advisory/system-derived evidence.
        It possesses zero authority to declare a financial PASS.
        """
        eid = evidence_id or f"ev_consumer_gate_{self.transaction_id}_{self.validated_at.strftime('%Y%m%d%H%M%S')}"
        return Evidence(
            evidence_id=eid,
            intent_id=self.intent_id,
            transaction_id=self.transaction_id,
            source=EvidenceSource.AGENT,
            authority=EvidenceAuthority.ADVISORY,
            field_name="consumer_gate_validation",
            field_value={
                "gate_status": self.status.value,
                "is_valid": self.is_valid,
                "findings_count": len(self.findings),
                "agent_id": self.agent_id,
                "invalid_checks": [f.check_type for f in self.findings if f.status == GateStatus.INVALID],
            },
            observed_at=self.validated_at,
            is_authoritative=False,
            provenance={"gate": "ConsumerGate", "findings": [f.model_dump() for f in self.findings]},
        )


class MerchantGateResult(BaseModel):
    """Structured validation outcome produced by the Merchant Gate."""
    gate_name: str = "MerchantGate"
    status: GateStatus
    transaction_id: str
    merchant_id: str
    offer_id: Optional[str] = None
    is_valid: bool
    findings: List[GateValidationFinding] = Field(default_factory=list)
    validated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    @field_validator("validated_at", mode="before")
    @classmethod
    def validate_timezone(cls, v: Any) -> datetime:
        if isinstance(v, str):
            dt = datetime.fromisoformat(v)
        elif isinstance(v, datetime):
            dt = v
        else:
            raise TypeError(f"Timestamp must be datetime or ISO string, got {type(v).__name__}")
        if dt.tzinfo is None:
            raise ValueError("validated_at must be timezone-aware (e.g. UTC)")
        return dt

    def to_evidence(self, intent_id: str, evidence_id: Optional[str] = None) -> Evidence:
        """Converts merchant gate validation facts into merchant-attested evidence.
        
        Strict Invariant: Merchant Gate output is merchant-attested evidence.
        It possesses zero authority to declare a financial PASS.
        """
        eid = evidence_id or f"ev_merchant_gate_{self.transaction_id}_{self.validated_at.strftime('%Y%m%d%H%M%S')}"
        return Evidence(
            evidence_id=eid,
            intent_id=intent_id,
            transaction_id=self.transaction_id,
            source=EvidenceSource.MERCHANT,
            authority=EvidenceAuthority.MERCHANT_ATTESTED,
            field_name="merchant_gate_validation",
            field_value={
                "gate_status": self.status.value,
                "is_valid": self.is_valid,
                "merchant_id": self.merchant_id,
                "offer_id": self.offer_id,
                "invalid_checks": [f.check_type for f in self.findings if f.status == GateStatus.INVALID],
            },
            observed_at=self.validated_at,
            is_authoritative=False,
            provenance={"gate": "MerchantGate", "findings": [f.model_dump() for f in self.findings]},
        )


class GateCompositionOutcome(BaseModel):
    """Composite validation outcome combining both consumer and merchant gates."""
    transaction_id: str
    consumer_gate: ConsumerGateResult
    merchant_gate: Optional[MerchantGateResult] = None
    overall_status: GateStatus
    is_admissible: bool
    summary: str
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
