"""
Integrity Result, Decision, and MRDP models for TarkaRaksha.
Defines deterministic evaluation outcomes, control plane decisions, and Machine-Readable Drift Proofs.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator
from .enums import DecisionAction, IntegrityStatus
from .money import Money


class IntegrityResult(BaseModel):
    """
    Deterministic integrity verification outcome.
    UNKNOWN is a first-class state, distinct from PASS and DRIFT.
    """
    evaluation_id: str
    intent_id: str
    status: IntegrityStatus
    evaluated_at: datetime
    rule_results: Dict[str, bool] = Field(default_factory=dict)
    violations: List[str] = Field(default_factory=list)
    evidence_ids: List[str] = Field(default_factory=list)
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)
    explanation: str = ""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )

    @field_validator("evaluated_at", mode="before")
    @classmethod
    def validate_timezone(cls, v: Any) -> datetime:
        if isinstance(v, str):
            dt = datetime.fromisoformat(v)
        elif isinstance(v, datetime):
            dt = v
        else:
            raise TypeError(f"Timestamp must be datetime or ISO string, got {type(v).__name__}")
        
        if dt.tzinfo is None:
            raise ValueError("evaluated_at must be timezone-aware (e.g., UTC)")
        return dt

    @property
    def is_pass(self) -> bool:
        return self.status == IntegrityStatus.PASS

    @property
    def is_drift(self) -> bool:
        return self.status == IntegrityStatus.DRIFT

    @property
    def is_unknown(self) -> bool:
        return self.status == IntegrityStatus.UNKNOWN


class Decision(BaseModel):
    """
    System decision taken by the Control Plane based on deterministic verification.
    Keeps the verification observation distinct from lifecycle orchestration.
    """
    decision_id: str
    intent_id: str
    integrity_status: IntegrityStatus
    action: DecisionAction
    decided_at: datetime
    reason: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )

    @field_validator("decided_at", mode="before")
    @classmethod
    def validate_timezone(cls, v: Any) -> datetime:
        if isinstance(v, str):
            dt = datetime.fromisoformat(v)
        elif isinstance(v, datetime):
            dt = v
        else:
            raise TypeError(f"Timestamp must be datetime or ISO string, got {type(v).__name__}")
        
        if dt.tzinfo is None:
            raise ValueError("decided_at must be timezone-aware (e.g., UTC)")
        return dt


from enum import Enum


class MRDPErrorCode(str, Enum):
    """
    Stable error code taxonomy for TarkaRaksha's proposed Machine-Readable Drift Proof (MRDP).
    Maps deterministic verifier outcomes to machine-readable error categories.
    """
    ECONOMIC_AMOUNT_EXCEEDED = "ECONOMIC_AMOUNT_EXCEEDED"
    ECONOMIC_CURRENCY_MISMATCH = "ECONOMIC_CURRENCY_MISMATCH"
    SEMANTIC_SKU_MISMATCH = "SEMANTIC_SKU_MISMATCH"
    SEMANTIC_QUANTITY_MISMATCH = "SEMANTIC_QUANTITY_MISMATCH"
    SEMANTIC_UNAUTHORIZED_SUBSTITUTION = "SEMANTIC_UNAUTHORIZED_SUBSTITUTION"
    TEMPORAL_CONTRACT_EXPIRED = "TEMPORAL_CONTRACT_EXPIRED"
    TEMPORAL_DUPLICATE_EVENT = "TEMPORAL_DUPLICATE_EVENT"
    TEMPORAL_EXCESSIVE_CAPTURES = "TEMPORAL_EXCESSIVE_CAPTURES"
    TEMPORAL_TIMEOUT_LATE_SUCCESS = "TEMPORAL_TIMEOUT_LATE_SUCCESS"
    EVIDENCE_CONFLICT_UNRESOLVED = "EVIDENCE_CONFLICT_UNRESOLVED"
    EVIDENCE_INSUFFICIENT = "EVIDENCE_INSUFFICIENT"
    GENERAL_DRIFT = "GENERAL_DRIFT"


class MRDP(BaseModel):
    """
    TarkaRaksha's proposed Machine-Readable Drift Proof (MRDP).
    Structured, verifiable evidence bundle proving exact divergence between authorized intent and observed reality.
    Note: MRDP is a proposed protocol for agentic transaction integrity, not an industry standard.
    """
    protocol: str = "TarkaRaksha-MRDP"
    version: str = "1.0.0"
    mrdp_id: str
    intent_id: str
    error_code: str
    status: IntegrityStatus
    violation: str
    drift_source: str
    expected_value: Any
    observed_value: Any
    discrepancy_amount: Optional[Money] = None
    evidence_references: List[str] = Field(default_factory=list)
    remediation: Optional[str] = None
    revalidation_required: bool = True
    generated_at: datetime
    proof_digest: Optional[str] = None

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )

    @field_validator("generated_at", mode="before")
    @classmethod
    def validate_timezone(cls, v: Any) -> datetime:
        if isinstance(v, str):
            dt = datetime.fromisoformat(v)
        elif isinstance(v, datetime):
            dt = v
        else:
            raise TypeError(f"Timestamp must be datetime or ISO string, got {type(v).__name__}")
        
        if dt.tzinfo is None:
            raise ValueError("generated_at must be timezone-aware (e.g., UTC)")
        return dt

    @property
    def expected(self) -> Any:
        """Alias for expected_value."""
        return self.expected_value

    @property
    def observed(self) -> Any:
        """Alias for observed_value."""
        return self.observed_value

    @property
    def evidence_refs(self) -> List[str]:
        """Alias for evidence_references."""
        return self.evidence_references

    @property
    def remediation_hint(self) -> Optional[str]:
        """Alias for remediation."""
        return self.remediation
