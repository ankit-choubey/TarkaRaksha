"""Pure deterministic evaluation engine for I10 Operational Deployment Modes.

Enforces:
- Mode × Integrity behavior matrix
- Separation of fact detection from policy enforcement
- SHADOW non-intervention guarantee (DETECTION = ACTIVE, ENFORCEMENT = DISABLED)
- GUARDED bounded action controls
- HUMAN_REVIEW explicit approval boundaries
- Strict preservation of I9 execution safety and I8 binding
"""
from datetime import datetime, timezone
import uuid
from typing import Optional

from backend.app.domain.kill_switch.contracts import KillSwitchState
from backend.app.domain.models.enums import IntegrityStatus
from backend.app.domain.models.money import Money
from backend.app.domain.operational_mode.contracts import (
    HumanReviewRequirement,
    HumanReviewStatus,
    OperationalAction,
    OperationalEvaluationResult,
    OperationalMode,
    OperationalModePolicy,
)


class OperationalModeEngine:
    """Pure deterministic policy evaluation engine for operational deployment modes."""

    @classmethod
    def evaluate(
        cls,
        policy: OperationalModePolicy,
        transaction_id: str,
        integrity_status: IntegrityStatus,
        kill_switch_state: KillSwitchState,
        review_requirement: Optional[HumanReviewRequirement] = None,
        amount: Optional[Money] = None,
        reference_time: Optional[datetime] = None,
    ) -> OperationalEvaluationResult:
        """
        Deterministically evaluates the operational mode policy against the transaction reality.
        
        Zero wall-clock dependence; uses explicit reference_time.
        Zero LLM calls; pure deterministic business logic.
        """
        eval_time = reference_time or datetime.now(timezone.utc)
        eval_id = f"op_eval_{uuid.uuid4().hex[:12]}"

        # =========================================================================
        # 1. SHADOW MODE: Observe & Record; Enforcement Disabled
        # =========================================================================
        if policy.mode == OperationalMode.SHADOW:
            # Detection is active (verdict recorded faithfully), enforcement disabled
            # SHADOW must not intervene financially or trigger remediation
            return OperationalEvaluationResult(
                evaluation_id=eval_id,
                transaction_id=transaction_id,
                mode=OperationalMode.SHADOW,
                action=OperationalAction.OBSERVE_ONLY,
                integrity_status=integrity_status,
                kill_switch_state=kill_switch_state,
                human_review_status=HumanReviewStatus.NOT_REQUIRED,
                review_id=None,
                enforcement_active=False,
                can_execute_payment=True,  # TarkaRaksha does not block financial execution in shadow mode
                remediation_permitted=False,  # Invariant: SHADOW never triggers automated remediation
                reason=f"SHADOW mode active: transaction evaluated as {integrity_status.value} (safety {kill_switch_state.value}); observation only, enforcement disabled.",
                policy_version=policy.policy_version,
                timestamp=eval_time,
            )

        # =========================================================================
        # 2. GUARDED MODE: Bounded Automated Remediation & Safety Gating
        # =========================================================================
        if policy.mode == OperationalMode.GUARDED:
            # I9 safety gate takes precedence
            if kill_switch_state in (KillSwitchState.KILLED, KillSwitchState.REQUIRES_REVALIDATION):
                return OperationalEvaluationResult(
                    evaluation_id=eval_id,
                    transaction_id=transaction_id,
                    mode=OperationalMode.GUARDED,
                    action=OperationalAction.TRIGGER_SAFETY_CONTROL,
                    integrity_status=integrity_status,
                    kill_switch_state=kill_switch_state,
                    human_review_status=HumanReviewStatus.NOT_REQUIRED,
                    review_id=None,
                    enforcement_active=True,
                    can_execute_payment=False,
                    remediation_permitted=False,
                    reason=f"GUARDED mode: execution blocked by I9 safety control ({kill_switch_state.value}).",
                    policy_version=policy.policy_version,
                    timestamp=eval_time,
                )

            if kill_switch_state == KillSwitchState.PAUSED:
                return OperationalEvaluationResult(
                    evaluation_id=eval_id,
                    transaction_id=transaction_id,
                    mode=OperationalMode.GUARDED,
                    action=OperationalAction.BLOCK_EXECUTION,
                    integrity_status=integrity_status,
                    kill_switch_state=kill_switch_state,
                    human_review_status=HumanReviewStatus.NOT_REQUIRED,
                    review_id=None,
                    enforcement_active=True,
                    can_execute_payment=False,
                    remediation_permitted=False,
                    reason="GUARDED mode: execution temporarily suspended by administrative pause.",
                    policy_version=policy.policy_version,
                    timestamp=eval_time,
                )

            # Normal safety state RUNNING: evaluate integrity
            if integrity_status == IntegrityStatus.PASS:
                return OperationalEvaluationResult(
                    evaluation_id=eval_id,
                    transaction_id=transaction_id,
                    mode=OperationalMode.GUARDED,
                    action=OperationalAction.ALLOW_EXECUTION,
                    integrity_status=IntegrityStatus.PASS,
                    kill_switch_state=kill_switch_state,
                    human_review_status=HumanReviewStatus.NOT_REQUIRED,
                    review_id=None,
                    enforcement_active=True,
                    can_execute_payment=True,
                    remediation_permitted=False,
                    reason="GUARDED mode: deterministic integrity PASS and safety RUNNING; execution permitted.",
                    policy_version=policy.policy_version,
                    timestamp=eval_time,
                )

            if integrity_status == IntegrityStatus.DRIFT:
                remed_allowed = policy.guarded_auto_remediation
                return OperationalEvaluationResult(
                    evaluation_id=eval_id,
                    transaction_id=transaction_id,
                    mode=OperationalMode.GUARDED,
                    action=OperationalAction.TRIGGER_REMEDIATION if remed_allowed else OperationalAction.BLOCK_EXECUTION,
                    integrity_status=IntegrityStatus.DRIFT,
                    kill_switch_state=kill_switch_state,
                    human_review_status=HumanReviewStatus.NOT_REQUIRED,
                    review_id=None,
                    enforcement_active=True,
                    can_execute_payment=False,
                    remediation_permitted=remed_allowed,
                    reason=f"GUARDED mode: integrity DRIFT detected; automated remediation {'triggered' if remed_allowed else 'disabled by policy'}.",
                    policy_version=policy.policy_version,
                    timestamp=eval_time,
                )

            # UNKNOWN integrity status
            return OperationalEvaluationResult(
                evaluation_id=eval_id,
                transaction_id=transaction_id,
                mode=OperationalMode.GUARDED,
                action=OperationalAction.BLOCK_EXECUTION,
                integrity_status=IntegrityStatus.UNKNOWN,
                kill_switch_state=kill_switch_state,
                human_review_status=HumanReviewStatus.NOT_REQUIRED,
                review_id=None,
                enforcement_active=True,
                can_execute_payment=False,
                remediation_permitted=False,
                reason="GUARDED mode: UNKNOWN integrity status; execution fail-closed pending authoritative evidence.",
                policy_version=policy.policy_version,
                timestamp=eval_time,
            )

        # =========================================================================
        # 3. HUMAN_REVIEW MODE: Explicit Approval Gating
        # =========================================================================
        if policy.mode == OperationalMode.HUMAN_REVIEW:
            # Check if there is an existing review decision
            if review_requirement is not None:
                # If explicitly REJECTED
                if review_requirement.status == HumanReviewStatus.REJECTED:
                    return OperationalEvaluationResult(
                        evaluation_id=eval_id,
                        transaction_id=transaction_id,
                        mode=OperationalMode.HUMAN_REVIEW,
                        action=OperationalAction.BLOCK_EXECUTION,
                        integrity_status=integrity_status,
                        kill_switch_state=kill_switch_state,
                        human_review_status=HumanReviewStatus.REJECTED,
                        review_id=review_requirement.review_id,
                        enforcement_active=True,
                        can_execute_payment=False,
                        remediation_permitted=False,
                        reason=f"HUMAN_REVIEW mode: execution rejected by human reviewer ({review_requirement.reviewed_by}): {review_requirement.decision_rationale or 'No rationale'}.",
                        policy_version=policy.policy_version,
                        timestamp=eval_time,
                    )

                # If explicitly APPROVED
                if review_requirement.status == HumanReviewStatus.APPROVED:
                    # Invariant: Human approval cannot directly resume KILLED transaction without revalidation
                    if kill_switch_state in (KillSwitchState.KILLED, KillSwitchState.REQUIRES_REVALIDATION):
                        return OperationalEvaluationResult(
                            evaluation_id=eval_id,
                            transaction_id=transaction_id,
                            mode=OperationalMode.HUMAN_REVIEW,
                            action=OperationalAction.TRIGGER_SAFETY_CONTROL,
                            integrity_status=integrity_status,
                            kill_switch_state=kill_switch_state,
                            human_review_status=HumanReviewStatus.APPROVED,
                            review_id=review_requirement.review_id,
                            enforcement_active=True,
                            can_execute_payment=False,
                            remediation_permitted=False,
                            reason="HUMAN_REVIEW mode: human review approved, but execution remains blocked by I9 safety control; authoritative revalidation required.",
                            policy_version=policy.policy_version,
                            timestamp=eval_time,
                        )

                    # If deterministic integrity is PASS and safety is RUNNING
                    if integrity_status == IntegrityStatus.PASS and kill_switch_state == KillSwitchState.RUNNING:
                        return OperationalEvaluationResult(
                            evaluation_id=eval_id,
                            transaction_id=transaction_id,
                            mode=OperationalMode.HUMAN_REVIEW,
                            action=OperationalAction.ALLOW_EXECUTION,
                            integrity_status=IntegrityStatus.PASS,
                            kill_switch_state=kill_switch_state,
                            human_review_status=HumanReviewStatus.APPROVED,
                            review_id=review_requirement.review_id,
                            enforcement_active=True,
                            can_execute_payment=True,
                            remediation_permitted=False,
                            reason=f"HUMAN_REVIEW mode: approved by reviewer ({review_requirement.reviewed_by}) and verified PASS; execution permitted.",
                            policy_version=policy.policy_version,
                            timestamp=eval_time,
                        )

                    # Approved, but integrity is DRIFT or UNKNOWN: requires revalidation before payment
                    return OperationalEvaluationResult(
                        evaluation_id=eval_id,
                        transaction_id=transaction_id,
                        mode=OperationalMode.HUMAN_REVIEW,
                        action=OperationalAction.BLOCK_EXECUTION,
                        integrity_status=integrity_status,
                        kill_switch_state=kill_switch_state,
                        human_review_status=HumanReviewStatus.APPROVED,
                        review_id=review_requirement.review_id,
                        enforcement_active=True,
                        can_execute_payment=False,
                        remediation_permitted=False,
                        reason=f"HUMAN_REVIEW mode: human review approved, but deterministic integrity status is {integrity_status.value}; revalidation required before execution.",
                        policy_version=policy.policy_version,
                        timestamp=eval_time,
                    )

                # Still PENDING review
                return OperationalEvaluationResult(
                    evaluation_id=eval_id,
                    transaction_id=transaction_id,
                    mode=OperationalMode.HUMAN_REVIEW,
                    action=OperationalAction.REQUIRE_HUMAN_REVIEW,
                    integrity_status=integrity_status,
                    kill_switch_state=kill_switch_state,
                    human_review_status=HumanReviewStatus.PENDING,
                    review_id=review_requirement.review_id,
                    enforcement_active=True,
                    can_execute_payment=False,
                    remediation_permitted=False,
                    reason=f"HUMAN_REVIEW mode: action stopped pending human review ({review_requirement.reason}).",
                    policy_version=policy.policy_version,
                    timestamp=eval_time,
                )

            # No review requirement object provided yet: determine if one is required
            needs_review = False
            review_reason = ""

            if kill_switch_state in (KillSwitchState.KILLED, KillSwitchState.REQUIRES_REVALIDATION, KillSwitchState.PAUSED):
                needs_review = True
                review_reason = f"Safety intervention active ({kill_switch_state.value})"
            elif integrity_status == IntegrityStatus.DRIFT and policy.require_review_on_drift:
                needs_review = True
                review_reason = "Integrity drift detected"
            elif integrity_status == IntegrityStatus.UNKNOWN and policy.require_review_on_unknown:
                needs_review = True
                review_reason = "Integrity status is UNKNOWN (insufficient/conflicting evidence)"
            elif policy.review_threshold_amount and amount and amount.currency == policy.review_threshold_amount.currency:
                if amount.amount > policy.review_threshold_amount.amount:
                    needs_review = True
                    review_reason = f"Transaction amount ({amount.amount}) exceeds policy threshold ({policy.review_threshold_amount.amount})"

            if needs_review:
                return OperationalEvaluationResult(
                    evaluation_id=eval_id,
                    transaction_id=transaction_id,
                    mode=OperationalMode.HUMAN_REVIEW,
                    action=OperationalAction.REQUIRE_HUMAN_REVIEW,
                    integrity_status=integrity_status,
                    kill_switch_state=kill_switch_state,
                    human_review_status=HumanReviewStatus.PENDING,
                    review_id=None,
                    enforcement_active=True,
                    can_execute_payment=False,
                    remediation_permitted=False,
                    reason=f"HUMAN_REVIEW mode: sensitive action requires explicit human approval ({review_reason}).",
                    policy_version=policy.policy_version,
                    timestamp=eval_time,
                )

            # Clean PASS within authorized parameters and RUNNING safety state
            if integrity_status == IntegrityStatus.PASS and kill_switch_state == KillSwitchState.RUNNING:
                return OperationalEvaluationResult(
                    evaluation_id=eval_id,
                    transaction_id=transaction_id,
                    mode=OperationalMode.HUMAN_REVIEW,
                    action=OperationalAction.ALLOW_EXECUTION,
                    integrity_status=IntegrityStatus.PASS,
                    kill_switch_state=kill_switch_state,
                    human_review_status=HumanReviewStatus.NOT_REQUIRED,
                    review_id=None,
                    enforcement_active=True,
                    can_execute_payment=True,
                    remediation_permitted=False,
                    reason="HUMAN_REVIEW mode: clean transaction within authorized limits; no review required.",
                    policy_version=policy.policy_version,
                    timestamp=eval_time,
                )

            # Fallback fail-closed
            return OperationalEvaluationResult(
                evaluation_id=eval_id,
                transaction_id=transaction_id,
                mode=OperationalMode.HUMAN_REVIEW,
                action=OperationalAction.BLOCK_EXECUTION,
                integrity_status=integrity_status,
                kill_switch_state=kill_switch_state,
                human_review_status=HumanReviewStatus.NOT_REQUIRED,
                review_id=None,
                enforcement_active=True,
                can_execute_payment=False,
                remediation_permitted=False,
                reason="HUMAN_REVIEW mode: execution blocked by default policy rule.",
                policy_version=policy.policy_version,
                timestamp=eval_time,
            )
