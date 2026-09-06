"""
Deterministic Scenario Lab Domain Contracts for TarkaRaksha (I11).

Provides immutable, canonical data structures for scenario definitions,
input snapshots, and evaluation results.

Invariants:
1. Scenarios define controlled inputs and test assertions; they DO NOT implement business logic.
2. The Scenario Lab reuses existing production-shaped components (T04, T05, T06, T07, T13, I8, I9, I10, I19).
3. Expected results are test assertions; actual results are computed by the authoritative engine.
4. Identical snapshot + reference_time -> bit-for-bit identical digest and result.
5. No reputation scores, no live financial side-effects, no random identifiers.
"""
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.domain.models import (
    CanonicalEvent,
    Evidence,
    EvidenceAuthority,
    EvidenceSource,
    IntegrityResult,
    IntegrityStatus,
    IntentContract,
    Money,
    MRDP,
    TransactionState,
)
from backend.app.domain.models.payment import ProviderOrder, ProviderPayment
from backend.app.domain.binding.contracts import BindingContext
from backend.app.domain.operational_mode import OperationalMode


class ScenarioId(str, Enum):
    """Canonical 12 scenario identifiers for TarkaRaksha Scenario Lab (I11)."""
    HAPPY_PATH = "HAPPY_PATH"
    PRICE_DRIFT = "PRICE_DRIFT"
    WRONG_SKU = "WRONG_SKU"
    INVENTORY_DISAPPEARS = "INVENTORY_DISAPPEARS"
    DELIVERY_DRIFT = "DELIVERY_DRIFT"
    DUPLICATE_PAYMENT = "DUPLICATE_PAYMENT"
    DELAYED_WEBHOOK = "DELAYED_WEBHOOK"
    REPLAY_ATTACK = "REPLAY_ATTACK"
    PROMPT_INJECTION_IN_EVIDENCE = "PROMPT_INJECTION_IN_EVIDENCE"
    MERCHANT_AGENT_COMPROMISED = "MERCHANT_AGENT_COMPROMISED"
    BUYER_AGENT_REUSE = "BUYER_AGENT_REUSE"
    UNKNOWN_PROVIDER_STATE = "UNKNOWN_PROVIDER_STATE"


class ScenarioCategory(str, Enum):
    """Categorization for scenario taxonomy."""
    HAPPY_PATH = "HAPPY_PATH"
    INTEGRITY = "INTEGRITY"
    SECURITY = "SECURITY"
    AGENTIC = "AGENTIC"
    PROVIDER = "PROVIDER"
    EVIDENCE = "EVIDENCE"


class ScenarioStatus(str, Enum):
    """Evaluation status comparing expected assertion vs actual authoritative outcome."""
    PASS = "PASS"    # Actual outcome matched expected assertion
    FAIL = "FAIL"    # Actual outcome differed from expected assertion
    ERROR = "ERROR"  # Unhandled exception during scenario execution


class ScenarioInputSnapshot(BaseModel):
    """
    Immutable, deterministic input snapshot representing the environment and
    transaction context fed into the production-shaped execution pipeline.
    """
    scenario_id: ScenarioId
    version: str = "1.0.0"
    intent: IntentContract
    order: Optional[ProviderOrder] = None
    payment: Optional[ProviderPayment] = None
    evidence: List[Evidence] = Field(default_factory=list)
    events: List[CanonicalEvent] = Field(default_factory=list)
    binding_context: Optional[BindingContext] = None
    mode: OperationalMode = OperationalMode.GUARDED
    reference_time: datetime
    fault_injection: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    @field_validator("reference_time", mode="before")
    @classmethod
    def validate_reference_time_tz(cls, v: Any) -> datetime:
        if isinstance(v, str):
            dt = datetime.fromisoformat(v)
        elif isinstance(v, datetime):
            dt = v
        else:
            raise TypeError(f"Timestamp must be datetime or ISO string, got {type(v).__name__}")
        if dt.tzinfo is None:
            raise ValueError("reference_time must be timezone-aware (e.g. UTC)")
        return dt

    def compute_digest(self) -> str:
        """Computes a deterministic SHA-256 digest of the input snapshot."""
        canonical_data = {
            "scenario_id": self.scenario_id.value,
            "version": self.version,
            "intent_id": self.intent.intent_id,
            "intent_max_total": self.intent.max_total.amount,
            "order_id": self.order.order_id if self.order else None,
            "payment_id": self.payment.payment_id if self.payment else None,
            "payment_amount": self.payment.amount.amount if self.payment else None,
            "evidence_ids": sorted([e.evidence_id for e in self.evidence]),
            "event_ids": sorted([ev.event_id for ev in self.events]),
            "mode": self.mode.value,
            "reference_time": self.reference_time.isoformat(),
            "fault_injection": self.fault_injection,
        }
        encoded = json.dumps(canonical_data, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


class ScenarioResult(BaseModel):
    """
    Deterministic evaluation output from running a scenario against the
    authoritative TarkaRaksha pipeline.
    """
    scenario_id: ScenarioId
    scenario_version: str
    input_snapshot_hash: str
    expected_verdict: str
    actual_verdict: str
    scenario_status: ScenarioStatus
    integrity_status: Optional[IntegrityStatus] = None
    transaction_state: Optional[TransactionState] = None
    mrdp_digest: Optional[str] = None
    violations: List[str] = Field(default_factory=list)
    evidence_count: int = 0
    events_processed: int = 0
    reference_time: datetime
    policy_version: str = "1.0.0"
    rules_version: str = "1.0.0"
    details: Dict[str, Any] = Field(default_factory=dict)
    human_readable_report: str = ""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )


class ScenarioDefinition(BaseModel):
    """
    Deterministic specification of a scenario in the Scenario Lab.
    Contains metadata, category, assertions, and snapshot builder.
    """
    scenario_id: ScenarioId
    name: str
    description: str
    category: ScenarioCategory
    version: str = "1.0.0"
    rules_version: str = "1.0.0"
    policy_version: str = "1.0.0"
    expected_verdict: str
    expected_policy_action: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    fault_description: Optional[str] = None
    initial_conditions: Optional[str] = None
    mutation_input: Optional[str] = None
    expected_behavior: Optional[str] = None
    expected_proof: Optional[str] = None
    provider_mode: str = "SYNTHETIC_OFFLINE_FIXTURE_RUN"
    related_capability: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    def compute_definition_digest(self) -> str:
        """Computes a deterministic SHA-256 digest of the scenario definition."""
        canonical_data = {
            "scenario_id": self.scenario_id.value,
            "name": self.name,
            "category": self.category.value,
            "version": self.version,
            "rules_version": self.rules_version,
            "policy_version": self.policy_version,
            "expected_verdict": self.expected_verdict,
            "expected_policy_action": self.expected_policy_action,
            "tags": sorted(self.tags),
        }
        encoded = json.dumps(canonical_data, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


class ScenarioSuiteResult(BaseModel):
    """
    Deterministic summary of running a suite of scenarios in the Scenario Lab.
    """
    suite_version: str = "1.0.0"
    total_scenarios: int
    passed_scenarios: int
    failed_scenarios: int
    results: List[ScenarioResult]
    is_all_passed: bool
    summary: str

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )


class ScenarioProofComparisonItem(BaseModel):
    """Row in the proof comparison table (Expected vs Observed)."""
    parameter: str
    expected_value: str
    observed_value: str
    is_match: bool
    notes: Optional[str] = None

    model_config = ConfigDict(frozen=True, extra="forbid")


class ScenarioProofChainStage(BaseModel):
    """Stage in the deterministic proof chain."""
    stage_name: str
    status: str  # e.g., "VALID", "MUTATED", "DETECTED", "VERIFIED", "CONTAINED"
    description: str
    evidence_ref: Optional[str] = None
    timestamp: Optional[datetime] = None

    model_config = ConfigDict(frozen=True, extra="forbid")


class ScenarioNarrative(BaseModel):
    """
    Authoritative 5-Question narrative explaining the scenario journey:
    1. What was authorized?
    2. What happened?
    3. Did it match?
    4. Why?
    5. What happened next?
    """
    what_was_authorized: str
    what_happened: str
    did_it_match: str
    why: str
    what_happened_next: str

    model_config = ConfigDict(frozen=True, extra="forbid")


class ScenarioProof(BaseModel):
    """
    Read-only, observational proof projection for an executed scenario.
    Provides complete tamper-evident audit trail connecting the scenario
    input to authoritative backend verdicts, MRDP, evidence, and E7 Control Room.
    """
    proof_id: str
    scenario_id: ScenarioId
    scenario_name: str
    category: ScenarioCategory
    transaction_id: str
    intent_id: str
    agent_id: str
    merchant_id: str
    order_id: Optional[str] = None
    payment_id: Optional[str] = None
    attempt_id: Optional[str] = None
    execution_mode: str = "SYNTHETIC_OFFLINE_FIXTURE_RUN"
    expected_verdict: str
    actual_verdict: str
    scenario_status: ScenarioStatus
    integrity_status: Optional[IntegrityStatus] = None
    transaction_state: Optional[TransactionState] = None
    mrdp_digest: Optional[str] = None
    mrdp_error_code: Optional[str] = None
    violations: List[str] = Field(default_factory=list)
    evidence_count: int = 0
    evidence_records: List[Dict[str, Any]] = Field(default_factory=list)
    security_findings: Dict[str, Any] = Field(default_factory=dict)
    recovery_summary: Optional[Dict[str, Any]] = None
    replay_verdict: Optional[str] = None
    comparison: List[ScenarioProofComparisonItem] = Field(default_factory=list)
    narrative: ScenarioNarrative
    proof_chain: List[ScenarioProofChainStage] = Field(default_factory=list)
    proof_digest: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    def compute_digest(self) -> str:
        """Computes a tamper-evident SHA-256 digest over the authoritative proof projection."""
        canonical_data = {
            "proof_id": self.proof_id,
            "scenario_id": self.scenario_id.value,
            "transaction_id": self.transaction_id,
            "intent_id": self.intent_id,
            "agent_id": self.agent_id,
            "merchant_id": self.merchant_id,
            "expected_verdict": self.expected_verdict,
            "actual_verdict": self.actual_verdict,
            "scenario_status": self.scenario_status.value,
            "integrity_status": self.integrity_status.value if self.integrity_status else None,
            "mrdp_digest": self.mrdp_digest,
            "violations": sorted(self.violations),
            "evidence_count": self.evidence_count,
            "execution_mode": self.execution_mode,
            "comparison_count": len(self.comparison),
            "proof_chain_count": len(self.proof_chain),
        }
        encoded = json.dumps(canonical_data, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()
