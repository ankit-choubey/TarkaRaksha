"""
Domain Contracts and Observational Models for the Control Room (E7).

Architectural Invariants:
- AI is advisory. Deterministic verification is authoritative.
- The Control Room is purely an observational, read-only projection surface.
  It maintains ZERO parallel mutable state, ZERO secondary state machines,
  and NEVER decides PASS/DRIFT/UNKNOWN, authorizes payment, or executes recovery.
- CAPTURED != PASS: Payment status remains strictly decoupled from integrity status.
- Real vs Synthetic: Explicitly labels synthetic offline simulation vs real Razorpay Test Mode.
"""
from datetime import datetime
import hashlib
import json
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from backend.app.domain.models.money import Money
from backend.app.domain.models.enums import IntegrityStatus, TransactionState


class ControlRoomIdentity(BaseModel):
    """Canonical 7-tuple context binding for a transaction."""
    transaction_id: str
    intent_id: str
    agent_id: str
    merchant_id: str
    order_id: str
    payment_id: str
    attempt_id: str

    model_config = ConfigDict(frozen=True, extra="forbid")


class ControlRoomLifecycle(BaseModel):
    """Lifecycle and state machine progression."""
    current_state: str  # TransactionState value
    hero_stage: Optional[str] = None
    is_terminal: bool = False
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_ms: Optional[float] = None

    model_config = ConfigDict(frozen=True, extra="forbid")


class ControlRoomAuthorization(BaseModel):
    """Immutable intent authorization boundary."""
    max_total: Money
    currency: str = "INR"
    allowed_skus: List[str] = Field(default_factory=list)
    allowed_substitutions: List[str] = Field(default_factory=list)
    issued_at: datetime
    expires_at: Optional[datetime] = None

    model_config = ConfigDict(frozen=True, extra="forbid")


class ControlRoomBuyerAgent(BaseModel):
    """Buyer Agent context and advisory AI proposal."""
    agent_id: str
    intent_id: str
    proposed_sku: Optional[str] = None
    proposed_quantity: Optional[int] = None
    proposed_unit_price: Optional[Money] = None
    proposal_rationale: Optional[str] = None
    advisory_model: str = "openai/gpt-oss-20b"
    gate_status: Optional[str] = None  # e.g., "VALID", "INVALID", "UNKNOWN"
    replanning_status: Optional[str] = None

    model_config = ConfigDict(frozen=True, extra="forbid")


class ControlRoomMerchantAgent(BaseModel):
    """Merchant Agent context, inventory claim, and offer."""
    merchant_id: str
    offer_id: Optional[str] = None
    sku: Optional[str] = None
    quantity: Optional[int] = None
    unit_price: Optional[Money] = None
    shipping: Optional[Money] = None
    discount: Optional[Money] = None
    tax: Optional[Money] = None
    total: Optional[Money] = None
    inventory_status: Optional[str] = None
    delivery_estimate: Optional[str] = None
    capabilities: List[str] = Field(default_factory=list)
    gate_status: Optional[str] = None

    model_config = ConfigDict(frozen=True, extra="forbid")


class ControlRoomIntegrity(BaseModel):
    """Authoritative deterministic integrity verdict and rule breakdown."""
    status: IntegrityStatus  # PASS, DRIFT, UNKNOWN, ABSTAIN
    expected_total: Optional[Money] = None
    observed_total: Optional[Money] = None
    discrepancy_amount: Optional[Money] = None
    economic_verdict: Optional[bool] = None
    semantic_verdict: Optional[bool] = None
    temporal_verdict: Optional[bool] = None
    violations: List[str] = Field(default_factory=list)
    authoritative_engine: str = "T04_DETERMINISTIC_ENGINE"

    model_config = ConfigDict(frozen=True, extra="forbid")


class ControlRoomDriftProof(BaseModel):
    """Machine-Readable Drift Proof (MRDP) when drift occurs."""
    mrdp_id: str
    error_code: str
    drift_source: str
    expected_value: Any = None
    observed_value: Any = None
    remediation: Optional[str] = None
    proof_digest: str

    model_config = ConfigDict(frozen=True, extra="forbid")


class ControlRoomRecovery(BaseModel):
    """Compensatory recovery and revalidation loop."""
    recovery_invoked: bool = False
    action_type: Optional[str] = None
    action_amount: Optional[Money] = None
    recovery_status: Optional[str] = None
    replan_rounds: int = 0
    revalidation_verdict: Optional[IntegrityStatus] = None
    revalidated_pass: bool = False
    attempts_count: int = 0
    max_attempts: int = 3

    model_config = ConfigDict(frozen=True, extra="forbid")


class ControlRoomPayment(BaseModel):
    """Payment provider details preserving CAPTURED != PASS invariant."""
    provider: str = "razorpay"
    order_id: str
    payment_id: str
    payment_status: str  # created, authorized, captured, failed, pending
    amount: Money
    payment_captured: bool
    integrity_vs_payment_distinction: str = "CAPTURED_IS_NOT_PASS"

    model_config = ConfigDict(frozen=True, extra="forbid")


class ControlRoomSecurity(BaseModel):
    """E4 Threat findings and execution safety gating."""
    binding_verified: bool = True
    kill_switch_state: str = "RUNNING"  # RUNNING, PAUSED, KILLED, REQUIRES_REVALIDATION
    threat_status: str = "CLEAN"  # CLEAN, THREAT_DETECTED, BLOCKED
    threats_detected: List[str] = Field(default_factory=list)
    prompt_injection_detected: bool = False
    tampering_detected: bool = False

    model_config = ConfigDict(frozen=True, extra="forbid")


class ControlRoomEvidenceItem(BaseModel):
    """Evidence record with provenance and authority ranking."""
    evidence_id: str
    field_name: str
    field_value_repr: str
    source: str
    authority: str  # AUTHORITATIVE, MERCHANT_ATTESTED, ADVISORY
    recorded_at: datetime
    is_synthetic: bool = False

    model_config = ConfigDict(frozen=True, extra="forbid")


class ControlRoomReplay(BaseModel):
    """Deterministic CPU-only replay verdict."""
    replay_available: bool = False
    replay_verdict: Optional[str] = None  # MATCH, MISMATCH, INVALID_REPLAY
    is_cpu_only: bool = True
    discrepancy_count: int = 0

    model_config = ConfigDict(frozen=True, extra="forbid")


class ControlRoomObservability(BaseModel):
    """Checkpoints, trace, and SLA latency metrics."""
    checkpoints_count: int = 0
    checkpoints_timeline_valid: bool = True
    last_valid_checkpoint: Optional[str] = None
    trace_divergence_stage: Optional[str] = None
    time_to_detect_ms: Optional[float] = None
    time_to_prove_ms: Optional[float] = None
    time_to_revalidate_ms: Optional[float] = None

    model_config = ConfigDict(frozen=True, extra="forbid")


class ControlRoomTimelineStage(BaseModel):
    """Chronological lifecycle stage event."""
    stage_id: str
    stage_name: str
    timestamp: datetime
    status: str  # PASS, DRIFT, INFO, PENDING
    description: str

    model_config = ConfigDict(frozen=True, extra="forbid")


class ControlRoomSnapshot(BaseModel):
    """
    Unified read-only projection model for the Real-time Control Room (E7).
    Compiles all transaction facts without introducing secondary mutable state.
    """
    identity: ControlRoomIdentity
    lifecycle: ControlRoomLifecycle
    authorization: ControlRoomAuthorization
    buyer_agent: ControlRoomBuyerAgent
    merchant_agent: ControlRoomMerchantAgent
    integrity: ControlRoomIntegrity
    drift_proof: Optional[ControlRoomDriftProof] = None
    recovery: ControlRoomRecovery
    payment: ControlRoomPayment
    security: ControlRoomSecurity
    evidence_records: List[ControlRoomEvidenceItem] = Field(default_factory=list)
    replay: ControlRoomReplay
    observability: ControlRoomObservability
    timeline: List[ControlRoomTimelineStage] = Field(default_factory=list)
    execution_mode: str = "SYNTHETIC_OFFLINE_HERO_RUN"  # or REAL_RAZORPAY_TEST_MODE
    hero_message: Optional[str] = None
    snapshot_digest: str = ""

    model_config = ConfigDict(frozen=True, extra="forbid")

    def compute_digest(self) -> str:
        """Computes deterministic SHA-256 digest of core transaction facts."""
        payload = {
            "transaction_id": self.identity.transaction_id,
            "intent_id": self.identity.intent_id,
            "lifecycle_state": self.lifecycle.current_state,
            "integrity_status": self.integrity.status.value,
            "payment_captured": self.payment.payment_captured,
            "payment_status": self.payment.payment_status,
            "recovery_status": self.recovery.recovery_status,
            "replay_verdict": self.replay.replay_verdict,
            "execution_mode": self.execution_mode,
        }
        raw_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw_json.encode("utf-8")).hexdigest()


class ControlRoomSummary(BaseModel):
    """Lightweight summary card for recent transaction feed."""
    transaction_id: str
    intent_id: str
    current_state: str
    integrity_status: IntegrityStatus
    payment_status: str
    payment_captured: bool
    max_authorized: Money
    observed_total: Optional[Money] = None
    execution_mode: str
    started_at: datetime

    model_config = ConfigDict(frozen=True, extra="forbid")
