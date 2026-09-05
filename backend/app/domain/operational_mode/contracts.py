"""Domain contracts for I10 Operational Deployment Modes: SHADOW / GUARDED / HUMAN_REVIEW.

Defines:
- OperationalMode: SHADOW (observe-only), GUARDED (bounded automation), HUMAN_REVIEW (approval-gated)
- HumanReviewStatus: NOT_REQUIRED, PENDING, APPROVED, REJECTED
- OperationalAction: ALLOW_EXECUTION, BLOCK_EXECUTION, OBSERVE_ONLY, TRIGGER_REMEDIATION, REQUIRE_HUMAN_REVIEW, TRIGGER_SAFETY_CONTROL
- OperationalModePolicy: Deterministic policy specification
- ModeTransitionRecord: Audit record for mode changes
- HumanReviewRequirement & HumanReviewDecision: Deterministic human review boundary
- OperationalEvaluationResult: Authoritative evaluation outcome

Invariants:
- AI proposes -> evidence proves -> deterministic logic decides.
- Detection is active in all modes; enforcement is disabled in SHADOW.
- Human review is an explicit decision boundary, not a fake or automated approval.
- Zero payment authority resides in operational mode or human review.
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.domain.kill_switch.contracts import KillSwitchState
from backend.app.domain.models.enums import IntegrityStatus
from backend.app.domain.models.money import Money


class OperationalMode(str, Enum):
    """
    Canonical operational deployment modes (§3, §4, §5).
    Controls whether TarkaRaksha actively intervenes or purely observes.
    """
    SHADOW = "SHADOW"              # Observe & evaluate; record facts; zero financial intervention
    GUARDED = "GUARDED"            # Bounded automated remediation & safety gating; continue only when policy permits
    HUMAN_REVIEW = "HUMAN_REVIEW"  # Stop sensitive automated actions; require explicit human approval


class HumanReviewStatus(str, Enum):
    """Lifecycle status of a human review requirement."""
    NOT_REQUIRED = "NOT_REQUIRED"  # No review required for this action
    PENDING = "PENDING"            # Review requirement created; action blocked pending approval
    APPROVED = "APPROVED"          # Explicitly approved by authenticated human operator
    REJECTED = "REJECTED"          # Explicitly rejected by authenticated human operator


class OperationalAction(str, Enum):
    """Deterministic action determined by the operational mode policy."""
    ALLOW_EXECUTION = "ALLOW_EXECUTION"              # Action safe to proceed
    BLOCK_EXECUTION = "BLOCK_EXECUTION"              # Action blocked by policy / drift / rejection
    OBSERVE_ONLY = "OBSERVE_ONLY"                    # SHADOW mode: record facts without intervention
    TRIGGER_REMEDIATION = "TRIGGER_REMEDIATION"      # GUARDED mode: trigger bounded automated remediation (I7)
    REQUIRE_HUMAN_REVIEW = "REQUIRE_HUMAN_REVIEW"    # HUMAN_REVIEW mode: require human approval
    TRIGGER_SAFETY_CONTROL = "TRIGGER_SAFETY_CONTROL"# Critical safety intervention (I9 Kill Switch)


class HumanReviewRequiredError(PermissionError):
    """Raised when an operation requires pending human review before it can proceed."""
    def __init__(self, message: str, review_id: str, transaction_id: str):
        super().__init__(message)
        self.review_id = review_id
        self.transaction_id = transaction_id


class OperationalModePolicy(BaseModel):
    """
    Deterministic configuration for operational mode enforcement.
    Strictly specifies how mode interacts with integrity, safety, and review thresholds.
    """
    policy_id: str = "op-policy-default"
    mode: OperationalMode = OperationalMode.GUARDED
    rules_version: str = "integrity-1.0.0"
    policy_version: str = "merchant-policy-1.0.0"
    allow_shadow_remediation: bool = False             # Invariant: SHADOW must never intervene financially
    guarded_auto_remediation: bool = True              # GUARDED mode may trigger bounded I7 remediation
    review_threshold_amount: Optional[Money] = None     # Transactions exceeding this amount require human review
    require_review_on_drift: bool = True               # HUMAN_REVIEW requires review on DRIFT
    require_review_on_unknown: bool = True             # HUMAN_REVIEW requires review on UNKNOWN
    require_review_on_kill: bool = True                # Safety kills require human review before any continuation

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )

    @field_validator("policy_id", "rules_version", "policy_version")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Policy identifiers and versions cannot be empty or whitespace.")
        return v.strip()


class ModeTransitionRecord(BaseModel):
    """
    Immutable audit record capturing an authoritative change of operational mode.
    Mode transitions cannot be initiated by AI, Buyer Agent, Merchant Agent, or TIX.
    """
    record_id: str
    previous_mode: OperationalMode
    new_mode: OperationalMode
    reason: str
    changed_by: str
    timestamp: datetime
    policy_version: str

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )

    @field_validator("record_id", "reason", "changed_by", "policy_version")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("String fields in ModeTransitionRecord cannot be empty or whitespace.")
        return v.strip()

    @field_validator("timestamp", mode="before")
    @classmethod
    def validate_timestamp(cls, v: Any) -> datetime:
        if isinstance(v, str):
            dt = datetime.fromisoformat(v)
        elif isinstance(v, datetime):
            dt = v
        else:
            raise TypeError(f"Timestamp must be datetime or ISO string, got {type(v).__name__}")
        if dt.tzinfo is None:
            raise ValueError("Timestamp must be timezone-aware (UTC)")
        return dt


class HumanReviewRequirement(BaseModel):
    """
    Immutable representation of an explicit human review requirement.
    Tied strictly to transaction_id, intent_id, agent_id, and merchant_id.
    Cannot be reused across transactions, agents, or merchants.
    """
    review_id: str
    transaction_id: str
    intent_id: str
    agent_id: str
    merchant_id: str
    status: HumanReviewStatus = HumanReviewStatus.PENDING
    reason: str
    integrity_status: IntegrityStatus
    kill_switch_state: KillSwitchState
    required_at: datetime
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[str] = None
    decision_rationale: Optional[str] = None
    revalidation_required: bool = True

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )

    @field_validator("review_id", "transaction_id", "intent_id", "agent_id", "merchant_id", "reason")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Identifier and reason fields cannot be empty or whitespace.")
        return v.strip()

    @field_validator("required_at", "reviewed_at", mode="before")
    @classmethod
    def validate_timestamp(cls, v: Any) -> Optional[datetime]:
        if v is None:
            return None
        if isinstance(v, str):
            dt = datetime.fromisoformat(v)
        elif isinstance(v, datetime):
            dt = v
        else:
            raise TypeError(f"Timestamp must be datetime or ISO string, got {type(v).__name__}")
        if dt.tzinfo is None:
            raise ValueError("Timestamp must be timezone-aware (UTC)")
        return dt


class HumanReviewDecision(BaseModel):
    """
    Explicit decision submitted by an authorized human operator for a pending review.
    AI cannot act as reviewer; decision cannot be empty or automatic.
    """
    review_id: str
    transaction_id: str
    decision: HumanReviewStatus
    reviewer_id: str
    rationale: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )

    @field_validator("review_id", "transaction_id", "reviewer_id", "rationale")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Decision fields cannot be empty or whitespace.")
        return v.strip()

    @field_validator("decision")
    @classmethod
    def validate_decision(cls, v: HumanReviewStatus) -> HumanReviewStatus:
        if v not in (HumanReviewStatus.APPROVED, HumanReviewStatus.REJECTED):
            raise ValueError("Human review decision must be explicitly APPROVED or REJECTED.")
        return v

    @field_validator("timestamp", mode="before")
    @classmethod
    def validate_timestamp(cls, v: Any) -> datetime:
        if isinstance(v, str):
            dt = datetime.fromisoformat(v)
        elif isinstance(v, datetime):
            dt = v
        else:
            raise TypeError(f"Timestamp must be datetime or ISO string, got {type(v).__name__}")
        if dt.tzinfo is None:
            raise ValueError("Timestamp must be timezone-aware (UTC)")
        return dt


class OperationalEvaluationResult(BaseModel):
    """
    Authoritative outcome of deterministic operational mode policy evaluation.
    Captures permitted action, enforcement status, and review binding.
    """
    evaluation_id: str
    transaction_id: str
    mode: OperationalMode
    action: OperationalAction
    integrity_status: IntegrityStatus
    kill_switch_state: KillSwitchState
    human_review_status: HumanReviewStatus = HumanReviewStatus.NOT_REQUIRED
    review_id: Optional[str] = None
    enforcement_active: bool
    can_execute_payment: bool
    remediation_permitted: bool
    reason: str
    policy_version: str
    timestamp: datetime

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )

    @field_validator("evaluation_id", "transaction_id", "reason", "policy_version")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("String fields in OperationalEvaluationResult cannot be empty or whitespace.")
        return v.strip()

    @field_validator("timestamp", mode="before")
    @classmethod
    def validate_timestamp(cls, v: Any) -> datetime:
        if isinstance(v, str):
            dt = datetime.fromisoformat(v)
        elif isinstance(v, datetime):
            dt = v
        else:
            raise TypeError(f"Timestamp must be datetime or ISO string, got {type(v).__name__}")
        if dt.tzinfo is None:
            raise ValueError("Timestamp must be timezone-aware (UTC)")
        return dt
