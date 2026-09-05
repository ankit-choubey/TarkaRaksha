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
