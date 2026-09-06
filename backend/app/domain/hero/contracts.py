"""
Domain contracts for I22 — Complete Hero Transaction.

Defines the typed, immutable contracts for the end-to-end hero transaction lifecycle:
- HeroStage: explicit lifecycle progression stages
- HeroStageTransition: timestamped stage history entry
- HeroDriftNotice: structured drift notification sent to agents
- HeroTransactionRecord: complete composed audit artifact of the journey
"""
from datetime import datetime
from enum import Enum
import hashlib
import json
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from backend.app.domain.binding.contracts import BindingContext, BindingVerificationOutcome
from backend.app.domain.checkpoint.contracts import IntegrityCheckpointTimeline
from backend.app.domain.explanation import ExplanationResult
from backend.app.domain.kill_switch.contracts import KillSwitchState
from backend.app.domain.models import (
    IntegrityResult,
    IntentContract,
    MRDP,
    ProviderOrder,
    ProviderPayment,
)
from backend.app.domain.sla.contracts import IntegritySLAMetricsReport
from backend.app.domain.trace.contracts import IntegrityTrace


class HeroStage(str, Enum):
    """
    Explicit high-level stages for the complete hero transaction lifecycle (I22).
    Enforces deterministic stage progression and disallows illegal skips.
    """
    INTENT_RECEIVED = "INTENT_RECEIVED"
    BUYER_PROPOSED = "BUYER_PROPOSED"
    MERCHANT_OFFERED = "MERCHANT_OFFERED"
    INITIAL_VALIDATION = "INITIAL_VALIDATION"
    INITIAL_PASS = "INITIAL_PASS"
    MUTATION_INJECTED = "MUTATION_INJECTED"
    DRIFT_DETECTED = "DRIFT_DETECTED"
    MRDP_GENERATED = "MRDP_GENERATED"
    DRIFT_NOTIFIED = "DRIFT_NOTIFIED"
    BUYER_REPLANNED = "BUYER_REPLANNED"
    MERCHANT_REOFFERED = "MERCHANT_REOFFERED"
    REVALIDATION = "REVALIDATION"
    REVALIDATED_PASS = "REVALIDATED_PASS"
    PAYMENT_EXECUTED = "PAYMENT_EXECUTED"
    PAYMENT_VERIFIED = "PAYMENT_VERIFIED"
    FINAL_INTEGRITY = "FINAL_INTEGRITY"
    COMPLETED = "COMPLETED"


class HeroStageTransition(BaseModel):
    """
    Timestamped record of a stage progression within the hero transaction.
    """
    stage: HeroStage
    timestamp: datetime
    description: str
    stage_data: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True, extra="forbid")


class HeroDriftNotice(BaseModel):
    """
    Structured drift signal emitted to agents when authoritative drift is detected.
    Provides verifiable facts without leaking credentials or secrets.
    """
    transaction_id: str
    violated_constraint: str
    authorized_max: int  # in paise
    observed_total: int   # in paise
    evidence_ids: List[str]
    mrdp_digest: str
    remediation_required: str
    timestamp: datetime

    model_config = ConfigDict(frozen=True, extra="forbid")


class HeroTransactionRecord(BaseModel):
    """
    Single high-level lifecycle artifact representing the complete hero transaction journey.
    Composes and references underlying authoritative components without duplicating them.
    """
    hero_transaction_id: str
    transaction_id: str
    intent: IntentContract
    current_stage: HeroStage
    stage_history: List[HeroStageTransition]

    buyer_id: str
    merchant_id: str

    # Initial Offer & Evaluation
    initial_offer: Optional[Dict[str, Any]] = None
    initial_integrity_result: Optional[IntegrityResult] = None

    # Deliberate Commerce Mutation & Drift Proof
    mutation: Optional[Dict[str, Any]] = None
    drift_integrity_result: Optional[IntegrityResult] = None
    mrdp: Optional[MRDP] = None
    drift_notice: Optional[HeroDriftNotice] = None

    # Agent Replan & Merchant Remediation
    replan_proposal: Optional[Dict[str, Any]] = None
    remediated_offer: Optional[Dict[str, Any]] = None
    revalidated_integrity_result: Optional[IntegrityResult] = None

    # Safety Gating & Binding
    kill_switch_state: Optional[KillSwitchState] = None
    binding_context: Optional[BindingContext] = None
    binding_outcome: Optional[BindingVerificationOutcome] = None

    # Payment Execution & Final Integrity
    payment_order: Optional[ProviderOrder] = None
    payment_result: Optional[ProviderPayment] = None
    final_integrity_result: Optional[IntegrityResult] = None

    # Agent Exchange (TIX)
    tix_message_count: int = 0
    tix_chain_valid: bool = False

    # Observability & Audit Layers
    trace: Optional[IntegrityTrace] = None
    checkpoint_timeline: Optional[IntegrityCheckpointTimeline] = None
    sla_report: Optional[IntegritySLAMetricsReport] = None
    explanation: Optional[ExplanationResult] = None
    replay_result: Optional[Any] = None
    certification_status: Optional[str] = None

    # Execution Meta
    execution_mode: str = "SYNTHETIC_OFFLINE_HERO_RUN"  # "REAL_RAZORPAY_TEST_MODE" or "SYNTHETIC_OFFLINE_HERO_RUN"
    started_at: datetime
    completed_at: Optional[datetime] = None
    hero_message: Optional[str] = None
    lifecycle_digest: str = ""

    model_config = ConfigDict(frozen=True, extra="forbid")

    def compute_lifecycle_digest(self) -> str:
        """
        Computes a deterministic SHA-256 fingerprint over the hero transaction's canonical facts.
        """
        canonical_dict = {
            "hero_transaction_id": self.hero_transaction_id,
            "transaction_id": self.transaction_id,
            "intent_id": self.intent.intent_id,
            "current_stage": self.current_stage.value,
            "stage_count": len(self.stage_history),
            "buyer_id": self.buyer_id,
            "merchant_id": self.merchant_id,
            "initial_verdict": self.initial_integrity_result.status.value if self.initial_integrity_result else None,
            "drift_verdict": self.drift_integrity_result.status.value if self.drift_integrity_result else None,
            "mrdp_digest": self.mrdp.proof_digest if self.mrdp else None,
            "revalidated_verdict": self.revalidated_integrity_result.status.value if self.revalidated_integrity_result else None,
            "final_verdict": self.final_integrity_result.status.value if self.final_integrity_result else None,
            "tix_message_count": self.tix_message_count,
            "execution_mode": self.execution_mode,
        }
        encoded = json.dumps(canonical_dict, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()
