"""
Domain contracts for E5 — Transaction Passport.

Provides a unified, observational, read-only representation of the complete lifecycle
of a TarkaRaksha transaction by composing records already produced by the existing architecture.

Governing Principles:
- "AI proposes. Evidence proves. Deterministic logic decides."
- Downstream & observational: The Passport may represent authoritative results; it never creates or replaces them.
- Non-mutating: Composing or serializing a Passport has zero side-effects on transaction state, authorization, or evidence.
"""
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.domain.models.enums import IntegrityStatus, TransactionState
from backend.app.domain.models.money import Money


class PassportIdentitySection(BaseModel):
    """A. Transaction Identity & Binding Tuple."""
    transaction_id: str
    intent_id: str
    agent_ids: List[str]
    merchant_id: str
    order_id: Optional[str] = None
    payment_id: Optional[str] = None
    attempt_id: Optional[str] = None
    binding_verified: bool = False
    binding_details: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True, extra="forbid")


class PassportAuthorizationSection(BaseModel):
    """B. Authorization state & immutable constraints."""
    intent_id: str
    issued_by: str
    issued_at: datetime
    expires_at: datetime
    max_total: Money
    currency: str
    authorized_items: List[Dict[str, Any]] = Field(default_factory=list)
    allowed_substitutions: List[str] = Field(default_factory=list)
    policy_version: str = "1.0.0"
    contract_version: str = "1.0.0"
    constraints_summary: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True, extra="forbid")


class PassportAgentContextSection(BaseModel):
    """C. Buyer Agent Context & Proposal Details."""
    buyer_agent_id: str
    proposal_id: Optional[str] = None
    proposed_sku: Optional[str] = None
    proposed_quantity: Optional[int] = None
    proposed_max_total: Optional[Money] = None
    proposal_rationale: Optional[str] = None
    consumer_gate_status: Optional[str] = None  # VALID, INVALID, UNKNOWN
    consumer_gate_findings: List[Dict[str, Any]] = Field(default_factory=list)
    agent_lifecycle_events: List[str] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True, extra="forbid")


class PassportMerchantContextSection(BaseModel):
    """D. Merchant Context & Offer Details."""
    merchant_id: str
    merchant_name: Optional[str] = None
    offer_id: Optional[str] = None
    offered_items: List[Dict[str, Any]] = Field(default_factory=list)
    offered_subtotal: Optional[Money] = None
    offered_shipping: Optional[Money] = None
    offered_total: Optional[Money] = None
    inventory_status: Optional[str] = None
    capabilities: List[str] = Field(default_factory=list)
    merchant_gate_status: Optional[str] = None  # VALID, INVALID, UNKNOWN
    merchant_gate_findings: List[Dict[str, Any]] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True, extra="forbid")


class PassportLifecycleStateSection(BaseModel):
    """E. State Machine & Lifecycle Progression (T05 projection)."""
    current_state: TransactionState
    state_transitions: List[Dict[str, Any]] = Field(default_factory=list)
    attempt_count: int = 1
    created_at: datetime
    updated_at: datetime
    is_terminal: bool = False

    model_config = ConfigDict(frozen=True, extra="forbid")


class PassportIntegritySection(BaseModel):
    """F. Authoritative Deterministic Integrity Evaluation (T04)."""
    status: IntegrityStatus
    rules_version: str = "1.0.0"
    economic_findings: Dict[str, Any] = Field(default_factory=dict)
    semantic_findings: Dict[str, Any] = Field(default_factory=dict)
    temporal_findings: Dict[str, Any] = Field(default_factory=dict)
    rule_results: Dict[str, bool] = Field(default_factory=dict)
    violations: List[str] = Field(default_factory=list)
    evaluated_at: Optional[datetime] = None

    model_config = ConfigDict(frozen=True, extra="forbid")


class PassportDriftSection(BaseModel):
    """G. Drift & MRDP Evidence (T07)."""
    has_drift: bool = False
    drift_detected_at: Optional[datetime] = None
    mrdp_id: Optional[str] = None
    mrdp_digest: Optional[str] = None
    discrepancy_amount: Optional[Money] = None
    discrepancy_details: Dict[str, Any] = Field(default_factory=dict)
    violated_rules: List[str] = Field(default_factory=list)
    mrdp_summary: Optional[str] = None

    model_config = ConfigDict(frozen=True, extra="forbid")


class PassportEvidenceSection(BaseModel):
    """H. Composed Evidence Hierarchy (T06)."""
    total_evidence_count: int = 0
    evidence_records: List[Dict[str, Any]] = Field(default_factory=list)
    authority_distribution: Dict[str, int] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True, extra="forbid")


class PassportSecuritySection(BaseModel):
    """I. Security & Threat Defense (E4)."""
    security_checked: bool = False
    threat_status: str = "NOT_EVALUATED"
    threats_detected: List[str] = Field(default_factory=list)
    prompt_injection_detected: bool = False
    capability_abuse_detected: bool = False
    replay_attack_detected: bool = False
    evidence_tampering_detected: bool = False
    kill_switch_state: Optional[str] = None

    model_config = ConfigDict(frozen=True, extra="forbid")


class PassportRecoverySection(BaseModel):
    """J. Compensatory Recovery (T11)."""
    recovery_invoked: bool = False
    recovery_attempts: int = 0
    action_type: Optional[str] = None
    action_amount: Optional[Money] = None
    target_reference: Optional[str] = None
    recovery_status: Optional[str] = None
    recovery_result: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(frozen=True, extra="forbid")


class PassportUnknownResolutionSection(BaseModel):
    """K. UNKNOWN Preservation & Resolution (T12)."""
    unknown_encountered: bool = False
    unknown_reason: Optional[str] = None
    resolution_attempts: int = 0
    resolution_outcome: Optional[str] = None
    final_unresolved: bool = False

    model_config = ConfigDict(frozen=True, extra="forbid")


class PassportRevalidationSection(BaseModel):
    """L. Bounded Revalidation Loop (E3 / I7)."""
    revalidation_invoked: bool = False
    replan_rounds: int = 0
    revised_proposal_present: bool = False
    revised_offer_present: bool = False
    revised_consumer_gate_status: Optional[str] = None
    revised_merchant_gate_status: Optional[str] = None
    revalidation_integrity_status: Optional[str] = None

    model_config = ConfigDict(frozen=True, extra="forbid")


class PassportCheckpointsAndTraceSection(BaseModel):
    """M. Checkpoints & Trace Fault Localization (I14 & I13)."""
    checkpoint_count: int = 0
    checkpoint_timeline_valid: Optional[bool] = None
    checkpoint_fingerprint: Optional[str] = None
    trace_stages_evaluated: int = 0
    divergence_stage: Optional[str] = None
    trace_root_cause: Optional[str] = None

    model_config = ConfigDict(frozen=True, extra="forbid")


class PassportSLAMetricsSection(BaseModel):
    """N. Operational & SLA Metrics (I15)."""
    sla_available: bool = False
    time_to_detect_ms: Optional[float] = None
    time_to_prove_ms: Optional[float] = None
    time_to_revalidate_ms: Optional[float] = None
    total_lifecycle_duration_ms: Optional[float] = None

    model_config = ConfigDict(frozen=True, extra="forbid")


class PassportPaymentSection(BaseModel):
    """O. Payment Provider State & Isolation (T09)."""
    provider: str = "RAZORPAY"
    payment_id: Optional[str] = None
    order_id: Optional[str] = None
    payment_status: Optional[str] = None
    amount: Optional[Money] = None
    method: Optional[str] = None
    payment_captured: bool = False
    integrity_status_distinction: str = "payment_state != integrity_state (CAPTURED != PASS)"

    model_config = ConfigDict(frozen=True, extra="forbid")


class PassportReplaySection(BaseModel):
    """P. Deterministic CPU Replay (T13)."""
    replay_available: bool = False
    replay_verdict: Optional[str] = None
    replayed_state: Optional[str] = None
    is_cpu_only: bool = True
    discrepancy_count: int = 0

    model_config = ConfigDict(frozen=True, extra="forbid")


class TransactionPassport(BaseModel):
    """
    Top-level, immutable Transaction Passport contract.
    Unified observational representation of a verified transaction lifecycle.
    """
    passport_id: str
    transaction_id: str
    final_outcome: str  # PASS, DRIFT, UNKNOWN, ABSTAIN, etc.
    final_proven: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    passport_digest: str = ""

    identity: PassportIdentitySection
    authorization: PassportAuthorizationSection
    agent_context: PassportAgentContextSection
    merchant_context: PassportMerchantContextSection
    lifecycle_state: PassportLifecycleStateSection
    integrity: PassportIntegritySection
    drift: PassportDriftSection
    evidence: PassportEvidenceSection
    security: PassportSecuritySection
    recovery: PassportRecoverySection
    unknown_resolution: PassportUnknownResolutionSection
    revalidation: PassportRevalidationSection
    checkpoints_trace: PassportCheckpointsAndTraceSection
    sla_metrics: PassportSLAMetricsSection
    payment: PassportPaymentSection
    replay: PassportReplaySection

    model_config = ConfigDict(frozen=True, extra="forbid")

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
            raise ValueError("generated_at must be timezone-aware (UTC)")
        return dt

    def compute_digest(self) -> str:
        """
        Computes a deterministic SHA-256 fingerprint over the Passport's canonical facts.
        """
        canonical_dict = {
            "passport_id": self.passport_id,
            "transaction_id": self.transaction_id,
            "intent_id": self.identity.intent_id,
            "agent_ids": sorted(self.identity.agent_ids),
            "merchant_id": self.identity.merchant_id,
            "order_id": self.identity.order_id,
            "payment_id": self.identity.payment_id,
            "max_total": self.authorization.max_total.model_dump(),
            "final_outcome": self.final_outcome,
            "integrity_status": self.integrity.status.value,
            "has_drift": self.drift.has_drift,
            "mrdp_digest": self.drift.mrdp_digest,
            "evidence_count": self.evidence.total_evidence_count,
            "payment_captured": self.payment.payment_captured,
        }
        encoded = json.dumps(canonical_dict, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def to_text_summary(self) -> str:
        """
        Produces the canonical human-readable Passport summary text (§9 E-Series Plan).
        """
        intent_status = "VERIFIED" if self.authorization.authorized_items else "UNVERIFIED"
        buyer_status = "VERIFIED" if self.agent_context.consumer_gate_status == "VALID" else (self.agent_context.consumer_gate_status or "UNVERIFIED")
        merchant_status = "VERIFIED" if self.merchant_context.merchant_gate_status == "VALID" else (self.merchant_context.merchant_gate_status or "UNVERIFIED")
        offer_status = "VERIFIED" if self.merchant_context.offered_total is not None else "UNVERIFIED"
        auth_status = "VERIFIED" if self.identity.binding_verified or self.authorization.max_total.amount > 0 else "UNVERIFIED"
        pay_status = "VERIFIED" if self.payment.payment_captured or self.payment.payment_id else "N/A"
        fulfillment_status = "DRIFT" if self.drift.has_drift else "VERIFIED"
        recovery_status = self.recovery.recovery_status or ("COMPLETED" if self.recovery.recovery_invoked else "N/A")
        revalidation_status = self.revalidation.revalidation_integrity_status or ("PASS" if self.revalidation.revalidation_invoked else "N/A")
        final_status = self.final_outcome

        return (
            "TRANSACTION PASSPORT\n\n"
            f"Intent         {intent_status}\n"
            f"Buyer Agent    {buyer_status}\n"
            f"Merchant       {merchant_status}\n"
            f"Offer          {offer_status}\n"
            f"Authorization  {auth_status}\n"
            f"Payment        {pay_status}\n"
            f"Fulfillment    {fulfillment_status}\n"
            f"Recovery       {recovery_status}\n"
            f"Revalidation   {revalidation_status}\n"
            f"Final          {final_status}"
        )
