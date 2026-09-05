"""Authoritative service implementation for I10 Operational Deployment Modes.

Manages:
- Active operational mode policy (SHADOW / GUARDED / HUMAN_REVIEW)
- Auditable mode transitions with strict authority verification (anti-agent/LLM tamper)
- Human review requirements lifecycle (creation, explicit human approval/rejection)
- Cross-transaction and cross-agent review reuse defenses
- Execution gating integration
"""
from datetime import datetime, timezone
import uuid
from typing import Dict, List, Optional

from backend.app.domain.kill_switch.contracts import ExecutionBlockedError, KillSwitchState
from backend.app.domain.models.enums import IntegrityStatus
from backend.app.domain.models.money import Money
from backend.app.domain.operational_mode.contracts import (
    HumanReviewDecision,
    HumanReviewRequiredError,
    HumanReviewRequirement,
    HumanReviewStatus,
    ModeTransitionRecord,
    OperationalAction,
    OperationalEvaluationResult,
    OperationalMode,
    OperationalModePolicy,
)
from backend.app.domain.operational_mode.policy import OperationalModeEngine

# Forbidden actor prefixes / substrings for mode control & review approval
FORBIDDEN_ACTOR_KEYWORDS = [
    "agent",
    "buyer",
    "merchant",
    "ai",
    "llm",
    "groq",
    "tix",
    "bot",
    "autonomous",
    "model",
]


class OperationalModeService:
    """
    Deterministic operational deployment mode and human review control plane service.
    Guarantees that AI proposals cannot alter operational deployment modes or simulate human approvals.
    """

    def __init__(self, policy: Optional[OperationalModePolicy] = None):
        self._policy: OperationalModePolicy = policy or OperationalModePolicy()
        self._transition_history: List[ModeTransitionRecord] = []
        # Keyed by review_id
        self._review_requirements: Dict[str, HumanReviewRequirement] = {}
        # Mapping transaction_id -> review_id
        self._tx_to_review: Dict[str, str] = {}

    @property
    def policy(self) -> OperationalModePolicy:
        return self._policy

    def get_mode(self) -> OperationalMode:
        return self._policy.mode

    def get_transition_history(self) -> List[ModeTransitionRecord]:
        return list(self._transition_history)

    def set_mode(
        self,
        new_mode: OperationalMode,
        changed_by: str,
        reason: str,
        reference_time: Optional[datetime] = None,
    ) -> ModeTransitionRecord:
        """
        Authoritatively changes the active operational deployment mode.
        Strictly rejects attempts by AI agents or automated protocol entities to alter mode.
        """
        actor_clean = changed_by.strip().lower()
        for kw in FORBIDDEN_ACTOR_KEYWORDS:
            if kw in actor_clean:
                raise PermissionError(
                    f"Operational mode change forbidden: actor '{changed_by}' contains unauthorized role keyword '{kw}'. "
                    "Only human control-plane operators or system administrators may change deployment modes."
                )

        if not reason or not reason.strip():
            raise ValueError("A clear deterministic reason must be provided for an operational mode transition.")

        ts = reference_time or datetime.now(timezone.utc)
        record = ModeTransitionRecord(
            record_id=f"trans_{uuid.uuid4().hex[:12]}",
            previous_mode=self._policy.mode,
            new_mode=new_mode,
            reason=reason.strip(),
            changed_by=changed_by.strip(),
            timestamp=ts,
            policy_version=self._policy.policy_version,
        )

        self._policy = self._policy.model_copy(update={"mode": new_mode})
        self._transition_history.append(record)
        return record

    def update_policy(
        self,
        new_policy: OperationalModePolicy,
        changed_by: str,
        reason: str,
        reference_time: Optional[datetime] = None,
    ) -> ModeTransitionRecord:
        """Updates full operational mode policy with strict audit record."""
        actor_clean = changed_by.strip().lower()
        for kw in FORBIDDEN_ACTOR_KEYWORDS:
            if kw in actor_clean:
                raise PermissionError(f"Policy update forbidden for actor '{changed_by}'.")

        ts = reference_time or datetime.now(timezone.utc)
        record = ModeTransitionRecord(
            record_id=f"trans_{uuid.uuid4().hex[:12]}",
            previous_mode=self._policy.mode,
            new_mode=new_policy.mode,
            reason=reason.strip(),
            changed_by=changed_by.strip(),
            timestamp=ts,
            policy_version=new_policy.policy_version,
        )

        self._policy = new_policy
        self._transition_history.append(record)
        return record

    def create_review_requirement(
        self,
        transaction_id: str,
        intent_id: str,
        agent_id: str,
        merchant_id: str,
        reason: str,
        integrity_status: IntegrityStatus,
        kill_switch_state: KillSwitchState,
        reference_time: Optional[datetime] = None,
    ) -> HumanReviewRequirement:
        """
        Creates a formal, bound human review requirement.
        Strictly bound to the 4-tuple (transaction_id, intent_id, agent_id, merchant_id).
        """
        # If one already exists for this transaction, return it
        existing_id = self._tx_to_review.get(transaction_id)
        if existing_id and existing_id in self._review_requirements:
            return self._review_requirements[existing_id]

        ts = reference_time or datetime.now(timezone.utc)
        review_id = f"rev_{uuid.uuid4().hex[:12]}"

        req = HumanReviewRequirement(
            review_id=review_id,
            transaction_id=transaction_id,
            intent_id=intent_id,
            agent_id=agent_id,
            merchant_id=merchant_id,
            status=HumanReviewStatus.PENDING,
            reason=reason,
            integrity_status=integrity_status,
            kill_switch_state=kill_switch_state,
            required_at=ts,
            revalidation_required=True,
        )

        self._review_requirements[review_id] = req
        self._tx_to_review[transaction_id] = review_id
        return req

    def get_review_requirement(self, review_id: str) -> Optional[HumanReviewRequirement]:
        return self._review_requirements.get(review_id)

    def get_review_for_transaction(self, transaction_id: str) -> Optional[HumanReviewRequirement]:
        review_id = self._tx_to_review.get(transaction_id)
        if review_id:
            return self._review_requirements.get(review_id)
        return None

    def submit_human_review(
        self,
        decision: HumanReviewDecision,
        expected_intent_id: Optional[str] = None,
        expected_agent_id: Optional[str] = None,
        expected_merchant_id: Optional[str] = None,
    ) -> HumanReviewRequirement:
        """
        Submits an explicit, authenticated human review decision.
        
        Adversarial defenses:
        1. Reviewer identity validation: AI/LLM/agent identities strictly rejected.
        2. Cross-transaction reuse defense: decision.transaction_id MUST match requirement.transaction_id.
        3. Cross-agent & cross-merchant defense: context bindings validated.
        4. Immutability defense: Settled reviews cannot be modified or re-decided.
        """
        req = self._review_requirements.get(decision.review_id)
        if not req:
            raise KeyError(f"Review requirement '{decision.review_id}' does not exist.")

        # Cross-transaction reuse defense (§11, §18)
        if req.transaction_id != decision.transaction_id:
            raise ValueError(
                f"Cross-transaction review approval reuse detected and rejected: "
                f"review requirement is bound to transaction '{req.transaction_id}', "
                f"but decision was submitted for '{decision.transaction_id}'."
            )

        # Context binding checks
        if expected_intent_id and req.intent_id != expected_intent_id:
            raise ValueError(f"Intent mismatch: review bound to '{req.intent_id}', expected '{expected_intent_id}'.")
        if expected_agent_id and req.agent_id != expected_agent_id:
            raise ValueError(f"Agent mismatch: review bound to '{req.agent_id}', expected '{expected_agent_id}'.")
        if expected_merchant_id and req.merchant_id != expected_merchant_id:
            raise ValueError(f"Merchant mismatch: review bound to '{req.merchant_id}', expected '{expected_merchant_id}'.")

        # Identity validation: AI cannot simulate human approval (§5, §18)
        reviewer_clean = decision.reviewer_id.strip().lower()
        for kw in FORBIDDEN_ACTOR_KEYWORDS:
            if kw in reviewer_clean:
                raise PermissionError(
                    f"Human review approval rejected: reviewer identity '{decision.reviewer_id}' contains "
                    f"forbidden agent/model keyword '{kw}'. AI/LLM cannot act as human reviewer."
                )

        # Immutability defense
        if req.status != HumanReviewStatus.PENDING:
            raise ValueError(
                f"Review requirement '{decision.review_id}' is already settled ({req.status.value}) "
                f"by '{req.reviewed_by}' and is immutable."
            )

        updated_req = req.model_copy(
            update={
                "status": decision.decision,
                "reviewed_at": decision.timestamp,
                "reviewed_by": decision.reviewer_id,
                "decision_rationale": decision.rationale,
            }
        )

        self._review_requirements[decision.review_id] = updated_req
        return updated_req

    def evaluate_transaction(
        self,
        transaction_id: str,
        integrity_status: IntegrityStatus,
        kill_switch_state: KillSwitchState,
        amount: Optional[Money] = None,
        reference_time: Optional[datetime] = None,
    ) -> OperationalEvaluationResult:
        """
        Deterministically evaluates the transaction against the active operational mode policy.
        """
        existing_review = self.get_review_for_transaction(transaction_id)
        return OperationalModeEngine.evaluate(
            policy=self._policy,
            transaction_id=transaction_id,
            integrity_status=integrity_status,
            kill_switch_state=kill_switch_state,
            review_requirement=existing_review,
            amount=amount,
            reference_time=reference_time,
        )

    def assert_can_execute_payment(
        self,
        transaction_id: str,
        evaluation: OperationalEvaluationResult,
    ) -> None:
        """
        Enforces operational execution gating prior to financial authorization.
        
        - In SHADOW mode: Observe only; never blocks execution.
        - In GUARDED mode: Blocks if execution is not allowed.
        - In HUMAN_REVIEW mode: Raises HumanReviewRequiredError if review is pending, or ExecutionBlockedError if rejected/blocked.
        """
        if evaluation.can_execute_payment:
            return

        # SHADOW mode must never intervene financially
        if evaluation.mode == OperationalMode.SHADOW:
            return

        if evaluation.action == OperationalAction.REQUIRE_HUMAN_REVIEW:
            raise HumanReviewRequiredError(
                f"Payment execution held in HUMAN_REVIEW mode: {evaluation.reason}",
                review_id=evaluation.review_id or "pending",
                transaction_id=transaction_id,
            )

        raise ExecutionBlockedError(
            f"Payment execution blocked by operational mode policy ({evaluation.mode.value}): {evaluation.reason}",
            state=evaluation.kill_switch_state,
        )
