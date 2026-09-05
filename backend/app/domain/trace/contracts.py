"""Authoritative domain contracts for Innovation I13 — Integrity Trace / Fault Localization.

Provides immutable lifecycle step sequence models, stage enums, context binding snapshots,
field discrepancies, fault locations, and the authoritative IntegrityTrace schema.

Core Invariant:
AI proposes -> evidence proves -> deterministic logic decides.
I13 is a pure deterministic trace/fault localization layer. Zero authoritative LLM logic.
"""
from datetime import datetime, timezone
from enum import Enum
import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.domain.models.enums import IntegrityStatus
from backend.app.domain.kill_switch.contracts import KillSwitchState


class LifecycleStage(str, Enum):
    """
    Canonical 8-stage chronological progression of a transaction lifecycle.
    Evaluated strictly in sequence: INTENT -> AGENT -> MERCHANT -> ORDER -> ATTEMPT -> PAYMENT -> GATEWAY -> COMPLETION.
    """
    INTENT = "INTENT"          # Stage 1: Authorization and intent formation
    AGENT = "AGENT"            # Stage 2: Buyer/seller agent delegation and identity binding
    MERCHANT = "MERCHANT"      # Stage 3: Merchant selection, catalog conformance, terms
    ORDER = "ORDER"            # Stage 4: Gateway order creation and binding
    ATTEMPT = "ATTEMPT"        # Stage 5: Checkout attempt tracking, single-use tokenization
    PAYMENT = "PAYMENT"        # Stage 6: Payment authorization, amount, currency, recipient
    GATEWAY = "GATEWAY"        # Stage 7: Provider settlement, signature, and capture
    COMPLETION = "COMPLETION"  # Stage 8: Final outcome verification and state commitment


class StageIntegrityStatus(str, Enum):
    """Integrity state of an individual lifecycle step."""
    CONFIRMED_VALID = "CONFIRMED_VALID"          # Authoritative evidence proves step satisfies all invariants
    DIVERGENCE_DETECTED = "DIVERGENCE_DETECTED"  # Authoritative evidence demonstrates deterministic violation/drift
    UNKNOWN = "UNKNOWN"                          # Insufficient evidence or unresolved conflict prevents validation
    UNREACHED = "UNREACHED"                      # Transaction halted or failed before reaching this stage


class ContextBindingSnapshot(BaseModel):
    """Immutable snapshot of bound identifiers across all 6 core contexts."""
    transaction_id: str
    intent_id: Optional[str] = None
    agent_id: Optional[str] = None
    merchant_id: Optional[str] = None
    order_id: Optional[str] = None
    payment_id: Optional[str] = None
    attempt_id: Optional[str] = None

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    @field_validator("transaction_id")
    @classmethod
    def validate_tx_id(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("transaction_id cannot be empty or whitespace")
        return v.strip()


class FieldDiscrepancy(BaseModel):
    """Structured delta between expected baseline and observed runtime value."""
    field_name: str
    expected_value: Any
    observed_value: Any
    evidence_ref: Optional[str] = None
    description: str

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    @field_validator("field_name", "description")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Field cannot be empty or whitespace")
        return v.strip()


class LifecycleStep(BaseModel):
    """Immutable audit record for a single stage in the chronological lifecycle."""
    sequence: int  # 1 to 8
    stage: LifecycleStage
    status: StageIntegrityStatus
    expected_context: Dict[str, Any] = Field(default_factory=dict)
    observed_context: Dict[str, Any] = Field(default_factory=dict)
    discrepancies: List[FieldDiscrepancy] = Field(default_factory=list)
    findings: List[str] = Field(default_factory=list)
    evidence_refs: List[str] = Field(default_factory=list)
    timestamp: Optional[datetime] = None

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    @field_validator("sequence")
    @classmethod
    def validate_sequence(cls, v: int) -> int:
        if v < 1 or v > 8:
            raise ValueError(f"Sequence must be between 1 and 8 inclusive, got {v}")
        return v

    @field_validator("timestamp")
    @classmethod
    def validate_timezone(cls, v: Optional[datetime]) -> Optional[datetime]:
        if v is not None and v.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware (UTC)")
        return v


class FirstDivergence(BaseModel):
    """The earliest chronological point where integrity diverged from expected baseline."""
    stage: LifecycleStage
    step_sequence: int
    finding: str
    primary_discrepancy: Optional[FieldDiscrepancy] = None
    evidence_refs: List[str] = Field(default_factory=list)
    detected_at: Optional[datetime] = None

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    @field_validator("step_sequence")
    @classmethod
    def validate_step_sequence(cls, v: int) -> int:
        if v < 1 or v > 8:
            raise ValueError(f"step_sequence must be between 1 and 8, got {v}")
        return v

    @field_validator("detected_at")
    @classmethod
    def validate_timezone(cls, v: Optional[datetime]) -> Optional[datetime]:
        if v is not None and v.tzinfo is None:
            raise ValueError("detected_at must be timezone-aware (UTC)")
        return v


class FaultLocation(BaseModel):
    """Identifies a specific component and failure code implicated in a divergence."""
    stage: LifecycleStage
    component: str
    finding_code: str
    description: str
    evidence_refs: List[str] = Field(default_factory=list)
    is_authoritative: bool = True

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    @field_validator("component", "finding_code", "description")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("String field cannot be empty")
        return v.strip()


class IntegrityTrace(BaseModel):
    """
    Authoritative deterministic trace and fault localization report for a transaction.
    Non-authoritative over decisions: mirrors deterministic verifier and safety states.
    """
    trace_id: str
    transaction_id: str
    deterministic_decision: IntegrityStatus
    execution_state: KillSwitchState
    context_bindings: ContextBindingSnapshot
    steps: List[LifecycleStep]
    first_divergence: Optional[FirstDivergence] = None
    fault_locations: List[FaultLocation] = Field(default_factory=list)
    missing_evidence: List[str] = Field(default_factory=list)
    uncertainties: List[str] = Field(default_factory=list)
    governance_version: str = "gov_v1.0.0"
    reproducibility_reference: Optional[str] = None
    generated_at: datetime

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    @field_validator("trace_id", "transaction_id")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Identifier cannot be empty")
        return v.strip()

    @field_validator("generated_at")
    @classmethod
    def validate_timezone(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("generated_at must be timezone-aware (UTC)")
        return v

    @field_validator("steps")
    @classmethod
    def validate_steps_order(cls, v: List[LifecycleStep]) -> List[LifecycleStep]:
        if not v:
            raise ValueError("IntegrityTrace must contain lifecycle steps")
        # Ensure steps are ordered by sequence 1..N
        sequences = [s.sequence for s in v]
        if sequences != sorted(sequences):
            raise ValueError("Lifecycle steps must be in ascending chronological order")
        return v
