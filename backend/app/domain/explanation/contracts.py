"""Authoritative domain contracts for I21 Evidence-Aware AI Explanation.

Defines structured explanation contexts, evidence provenance references,
structured claims, post-generation validation outcomes, and explanation results.

Invariant: AI proposes -> evidence proves -> deterministic logic decides.
The AI explanation layer is purely descriptive; it possesses zero authority
over transaction integrity, decisions, or execution states.
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.domain.kill_switch.contracts import KillSwitchState, KillTrigger
from backend.app.domain.models.enums import EvidenceAuthority, EvidenceSource, IntegrityStatus


class FindingCategory(str, Enum):
    """Categorization of an integrity, safety, or binding finding."""
    ECONOMIC = "ECONOMIC"
    SEMANTIC = "SEMANTIC"
    TEMPORAL = "TEMPORAL"
    BINDING = "BINDING"
    KILL_SWITCH = "KILL_SWITCH"
    POLICY = "POLICY"
    SYSTEM = "SYSTEM"


class ClaimType(str, Enum):
    """Distinguishes factual observations from analytical interpretations."""
    FACT = "FACT"
    INTERPRETATION = "INTERPRETATION"


class EvidenceReference(BaseModel):
    """
    Structured factual provenance item linking an explanation claim directly
    to an authoritative evidence record or verified transaction attribute.
    """
    evidence_id: str
    field_name: str
    source: EvidenceSource
    authority: EvidenceAuthority
    observed_value: Any
    expected_value: Optional[Any] = None
    is_authoritative: bool = False
    description: Optional[str] = None

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    @field_validator("evidence_id", "field_name")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("EvidenceReference identifiers cannot be empty or whitespace")
        return v.strip()


class ExplanationClaim(BaseModel):
    """
    A single claim in an explanation.
    Must cite valid evidence_ids from the explanation context.
    """
    claim_id: str
    claim_text: str
    evidence_refs: List[str] = Field(default_factory=list)
    authority_tier: EvidenceAuthority = EvidenceAuthority.AUTHORITATIVE
    claim_type: ClaimType = ClaimType.FACT
    category: FindingCategory = FindingCategory.SYSTEM

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    @field_validator("claim_id", "claim_text")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("ExplanationClaim identifiers and text cannot be empty or whitespace")
        return v.strip()


class ExplanationContext(BaseModel):
    """
    Immutable, deterministic, and serializable context supplied to the explanation engine.
    Contains only sanitized and necessary facts: no secrets, API keys, or private tokens.
    """
    context_id: str
    transaction_id: str
    intent_id: str
    agent_id: Optional[str] = None
    merchant_id: Optional[str] = None
    order_id: Optional[str] = None
    payment_id: Optional[str] = None
    attempt_id: Optional[str] = None

    deterministic_decision: IntegrityStatus
    decision_reason: str
    kill_switch_state: KillSwitchState
    kill_switch_trigger: Optional[KillTrigger] = None

    integrity_violations: List[str] = Field(default_factory=list)
    binding_violations: List[str] = Field(default_factory=list)
    evidence_references: List[EvidenceReference] = Field(default_factory=list)
    missing_evidence_fields: List[str] = Field(default_factory=list)
    uncertainty_notes: List[str] = Field(default_factory=list)
    revalidation_requirements: List[str] = Field(default_factory=list)

    governance_version: Optional[str] = None
    rules_version: Optional[str] = None
    snapshot_hash: Optional[str] = None
    certificate_id: Optional[str] = None
    mrdp_digest: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    @field_validator("context_id", "transaction_id", "intent_id", "decision_reason")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Context identifiers and reason cannot be empty or whitespace")
        return v.strip()

    @field_validator("created_at")
    @classmethod
    def validate_timezone(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("created_at must be timezone-aware (UTC)")
        return v

    @property
    def valid_evidence_ids(self) -> Set[str]:
        """Returns the set of recognized evidence IDs available in this context."""
        return {ref.evidence_id for ref in self.evidence_references}

    def get_evidence_ref(self, evidence_id: str) -> Optional[EvidenceReference]:
        """Finds an evidence reference by evidence_id."""
        for ref in self.evidence_references:
            if ref.evidence_id == evidence_id:
                return ref
        return None


class ExplanationValidationResult(BaseModel):
    """
    Deterministic verdict verifying the consistency of an explanation against
    the authoritative context.
    """
    is_valid: bool
    violations: List[str] = Field(default_factory=list)
    validated_at: datetime

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    @field_validator("validated_at")
    @classmethod
    def validate_timezone(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("validated_at must be timezone-aware (UTC)")
        return v


class ExplanationResult(BaseModel):
    """
    Complete structured explanation output for human review, UI display,
    and audit logging.
    """
    explanation_id: str
    transaction_id: str
    deterministic_decision: IntegrityStatus
    execution_state: KillSwitchState
    summary: str
    claims: List[ExplanationClaim] = Field(default_factory=list)
    mismatches: List[Dict[str, Any]] = Field(default_factory=list)
    missing_evidence: List[str] = Field(default_factory=list)
    uncertainties: List[str] = Field(default_factory=list)
    recommended_next_action: str
    validation_result: ExplanationValidationResult
    is_fallback: bool = False
    model_metadata: Dict[str, Any] = Field(default_factory=dict)
    generated_at: datetime

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    @field_validator("explanation_id", "transaction_id", "summary", "recommended_next_action")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Explanation identifiers, summary, and action must be non-empty")
        return v.strip()

    @field_validator("generated_at")
    @classmethod
    def validate_timezone(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("generated_at must be timezone-aware (UTC)")
        return v
