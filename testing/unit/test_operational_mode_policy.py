"""Unit tests for I10 Operational Deployment Mode Policy Engine.

Validates the complete Mode × Integrity Behavior Matrix (§9):
1. SHADOW:
   - PASS, DRIFT, UNKNOWN evaluated faithfully.
   - Enforcement disabled (enforcement_active=False).
   - Zero automated remediation (remediation_permitted=False).
   - Detection remains fully active (verdict unchanged).
2. GUARDED:
   - PASS + RUNNING -> ALLOW_EXECUTION.
   - PASS + PAUSED -> BLOCK_EXECUTION.
   - PASS + KILLED -> TRIGGER_SAFETY_CONTROL.
   - DRIFT + auto_remediation -> TRIGGER_REMEDIATION.
   - DRIFT + no auto_remediation -> BLOCK_EXECUTION.
   - UNKNOWN -> BLOCK_EXECUTION (fail-closed).
3. HUMAN_REVIEW:
   - Threshold amount trigger.
   - Drift / UNKNOWN review trigger.
   - Approved review on PASS -> ALLOW_EXECUTION.
   - Approved review on KILLED -> BLOCKED (Approval cannot bypass safety revalidation).
   - Approved review on DRIFT -> BLOCKED (Approval requires revalidation before execution).
   - Rejected review -> BLOCK_EXECUTION.
"""
from datetime import datetime, timezone
import pytest

from backend.app.domain.kill_switch.contracts import KillSwitchState
from backend.app.domain.models.enums import IntegrityStatus
from backend.app.domain.models.money import Money
from backend.app.domain.operational_mode import (
    HumanReviewRequirement,
    HumanReviewStatus,
    OperationalAction,
    OperationalMode,
    OperationalModeEngine,
    OperationalModePolicy,
)


@pytest.fixture
def base_time() -> datetime:
    return datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)


# =============================================================================
# SHADOW MODE TESTS
# =============================================================================

def test_shadow_mode_pass_observes_without_intervention(base_time: datetime):
    policy = OperationalModePolicy(mode=OperationalMode.SHADOW)
    res = OperationalModeEngine.evaluate(
        policy=policy,
        transaction_id="tx_shadow_01",
        integrity_status=IntegrityStatus.PASS,
        kill_switch_state=KillSwitchState.RUNNING,
        reference_time=base_time,
    )

    assert res.mode == OperationalMode.SHADOW
    assert res.action == OperationalAction.OBSERVE_ONLY
    assert res.enforcement_active is False
    assert res.can_execute_payment is True
    assert res.remediation_permitted is False
    assert res.integrity_status == IntegrityStatus.PASS


def test_shadow_mode_drift_records_drift_without_intervention(base_time: datetime):
    policy = OperationalModePolicy(mode=OperationalMode.SHADOW)
    res = OperationalModeEngine.evaluate(
        policy=policy,
        transaction_id="tx_shadow_02",
        integrity_status=IntegrityStatus.DRIFT,
        kill_switch_state=KillSwitchState.RUNNING,
        reference_time=base_time,
    )

    assert res.mode == OperationalMode.SHADOW
    assert res.action == OperationalAction.OBSERVE_ONLY
    assert res.enforcement_active is False
    # Crucial Invariant: DRIFT remains real DRIFT (no conversion to PASS)
    assert res.integrity_status == IntegrityStatus.DRIFT
    assert res.remediation_permitted is False


def test_shadow_mode_unknown_records_unknown_without_intervention(base_time: datetime):
    policy = OperationalModePolicy(mode=OperationalMode.SHADOW)
    res = OperationalModeEngine.evaluate(
        policy=policy,
        transaction_id="tx_shadow_03",
        integrity_status=IntegrityStatus.UNKNOWN,
        kill_switch_state=KillSwitchState.RUNNING,
        reference_time=base_time,
    )

    assert res.mode == OperationalMode.SHADOW
    assert res.action == OperationalAction.OBSERVE_ONLY
    assert res.enforcement_active is False
    assert res.integrity_status == IntegrityStatus.UNKNOWN
    assert res.remediation_permitted is False


def test_shadow_mode_killed_safety_state_observes_without_enforcement(base_time: datetime):
    policy = OperationalModePolicy(mode=OperationalMode.SHADOW)
    res = OperationalModeEngine.evaluate(
        policy=policy,
        transaction_id="tx_shadow_04",
        integrity_status=IntegrityStatus.DRIFT,
        kill_switch_state=KillSwitchState.KILLED,
        reference_time=base_time,
    )

    assert res.mode == OperationalMode.SHADOW
    assert res.action == OperationalAction.OBSERVE_ONLY
    assert res.enforcement_active is False


# =============================================================================
# GUARDED MODE TESTS
# =============================================================================

def test_guarded_mode_pass_and_running_permits_execution(base_time: datetime):
    policy = OperationalModePolicy(mode=OperationalMode.GUARDED)
    res = OperationalModeEngine.evaluate(
        policy=policy,
        transaction_id="tx_guarded_01",
        integrity_status=IntegrityStatus.PASS,
        kill_switch_state=KillSwitchState.RUNNING,
        reference_time=base_time,
    )

    assert res.action == OperationalAction.ALLOW_EXECUTION
    assert res.can_execute_payment is True
    assert res.enforcement_active is True
    assert res.remediation_permitted is False


def test_guarded_mode_paused_blocks_execution(base_time: datetime):
    policy = OperationalModePolicy(mode=OperationalMode.GUARDED)
    res = OperationalModeEngine.evaluate(
        policy=policy,
        transaction_id="tx_guarded_02",
        integrity_status=IntegrityStatus.PASS,
        kill_switch_state=KillSwitchState.PAUSED,
        reference_time=base_time,
    )

    assert res.action == OperationalAction.BLOCK_EXECUTION
    assert res.can_execute_payment is False


def test_guarded_mode_killed_triggers_safety_control(base_time: datetime):
    policy = OperationalModePolicy(mode=OperationalMode.GUARDED)
    res = OperationalModeEngine.evaluate(
        policy=policy,
        transaction_id="tx_guarded_03",
        integrity_status=IntegrityStatus.PASS,
        kill_switch_state=KillSwitchState.KILLED,
        reference_time=base_time,
    )

    assert res.action == OperationalAction.TRIGGER_SAFETY_CONTROL
    assert res.can_execute_payment is False


def test_guarded_mode_drift_triggers_bounded_remediation(base_time: datetime):
    policy = OperationalModePolicy(mode=OperationalMode.GUARDED, guarded_auto_remediation=True)
    res = OperationalModeEngine.evaluate(
        policy=policy,
        transaction_id="tx_guarded_04",
        integrity_status=IntegrityStatus.DRIFT,
        kill_switch_state=KillSwitchState.RUNNING,
        reference_time=base_time,
    )

    assert res.action == OperationalAction.TRIGGER_REMEDIATION
    assert res.can_execute_payment is False
    assert res.remediation_permitted is True


def test_guarded_mode_drift_with_remediation_disabled_blocks(base_time: datetime):
    policy = OperationalModePolicy(mode=OperationalMode.GUARDED, guarded_auto_remediation=False)
    res = OperationalModeEngine.evaluate(
        policy=policy,
        transaction_id="tx_guarded_05",
        integrity_status=IntegrityStatus.DRIFT,
        kill_switch_state=KillSwitchState.RUNNING,
        reference_time=base_time,
    )

    assert res.action == OperationalAction.BLOCK_EXECUTION
    assert res.can_execute_payment is False
    assert res.remediation_permitted is False


def test_guarded_mode_unknown_fails_closed(base_time: datetime):
    policy = OperationalModePolicy(mode=OperationalMode.GUARDED)
    res = OperationalModeEngine.evaluate(
        policy=policy,
        transaction_id="tx_guarded_06",
        integrity_status=IntegrityStatus.UNKNOWN,
        kill_switch_state=KillSwitchState.RUNNING,
        reference_time=base_time,
    )

    assert res.action == OperationalAction.BLOCK_EXECUTION
    assert res.can_execute_payment is False
    assert res.integrity_status == IntegrityStatus.UNKNOWN


# =============================================================================
# HUMAN REVIEW MODE TESTS
# =============================================================================

def test_human_review_mode_clean_pass_below_threshold_allows(base_time: datetime):
    policy = OperationalModePolicy(
        mode=OperationalMode.HUMAN_REVIEW,
        review_threshold_amount=Money(amount=10000000, currency="INR"),  # ₹100,000 threshold
    )
    res = OperationalModeEngine.evaluate(
        policy=policy,
        transaction_id="tx_hr_01",
        integrity_status=IntegrityStatus.PASS,
        kill_switch_state=KillSwitchState.RUNNING,
        amount=Money(amount=5000000, currency="INR"),  # ₹50,000
        reference_time=base_time,
    )

    assert res.action == OperationalAction.ALLOW_EXECUTION
    assert res.can_execute_payment is True
    assert res.human_review_status == HumanReviewStatus.NOT_REQUIRED


def test_human_review_mode_amount_exceeding_threshold_requires_review(base_time: datetime):
    policy = OperationalModePolicy(
        mode=OperationalMode.HUMAN_REVIEW,
        review_threshold_amount=Money(amount=10000000, currency="INR"),  # ₹100,000 threshold
    )
    res = OperationalModeEngine.evaluate(
        policy=policy,
        transaction_id="tx_hr_02",
        integrity_status=IntegrityStatus.PASS,
        kill_switch_state=KillSwitchState.RUNNING,
        amount=Money(amount=15000000, currency="INR"),  # ₹150,000
        reference_time=base_time,
    )

    assert res.action == OperationalAction.REQUIRE_HUMAN_REVIEW
    assert res.can_execute_payment is False
    assert res.human_review_status == HumanReviewStatus.PENDING


def test_human_review_mode_drift_requires_review(base_time: datetime):
    policy = OperationalModePolicy(mode=OperationalMode.HUMAN_REVIEW, require_review_on_drift=True)
    res = OperationalModeEngine.evaluate(
        policy=policy,
        transaction_id="tx_hr_03",
        integrity_status=IntegrityStatus.DRIFT,
        kill_switch_state=KillSwitchState.RUNNING,
        reference_time=base_time,
    )

    assert res.action == OperationalAction.REQUIRE_HUMAN_REVIEW
    assert res.can_execute_payment is False
    assert res.human_review_status == HumanReviewStatus.PENDING


def test_human_review_approved_with_pass_allows_execution(base_time: datetime):
    policy = OperationalModePolicy(mode=OperationalMode.HUMAN_REVIEW)
    review = HumanReviewRequirement(
        review_id="rev_01",
        transaction_id="tx_hr_04",
        intent_id="intent_01",
        agent_id="buyer_alice",
        merchant_id="merchant_store",
        status=HumanReviewStatus.APPROVED,
        reason="Price drift reviewed and signed off",
        integrity_status=IntegrityStatus.PASS,
        kill_switch_state=KillSwitchState.RUNNING,
        required_at=base_time,
        reviewed_at=base_time,
        reviewed_by="risk_officer_bob",
        decision_rationale="Overcharge accepted as legitimate freight fee",
    )

    res = OperationalModeEngine.evaluate(
        policy=policy,
        transaction_id="tx_hr_04",
        integrity_status=IntegrityStatus.PASS,
        kill_switch_state=KillSwitchState.RUNNING,
        review_requirement=review,
        reference_time=base_time,
    )

    assert res.action == OperationalAction.ALLOW_EXECUTION
    assert res.can_execute_payment is True
    assert res.human_review_status == HumanReviewStatus.APPROVED


def test_human_review_approved_on_killed_state_cannot_bypass_safety(base_time: datetime):
    """
    CRITICAL INVARIANT (§10, §18):
    Human approval CANNOT directly resume a KILLED transaction.
    Authoritative revalidation through verified evidence is unconditionally required.
    """
    policy = OperationalModePolicy(mode=OperationalMode.HUMAN_REVIEW)
    review = HumanReviewRequirement(
        review_id="rev_02",
        transaction_id="tx_hr_05",
        intent_id="intent_01",
        agent_id="buyer_alice",
        merchant_id="merchant_store",
        status=HumanReviewStatus.APPROVED,
        reason="Operator approved",
        integrity_status=IntegrityStatus.PASS,
        kill_switch_state=KillSwitchState.KILLED,
        required_at=base_time,
        reviewed_at=base_time,
        reviewed_by="risk_officer_bob",
    )

    res = OperationalModeEngine.evaluate(
        policy=policy,
        transaction_id="tx_hr_05",
        integrity_status=IntegrityStatus.PASS,
        kill_switch_state=KillSwitchState.KILLED,
        review_requirement=review,
        reference_time=base_time,
    )

    # Must remain blocked by I9 safety control
    assert res.action == OperationalAction.TRIGGER_SAFETY_CONTROL
    assert res.can_execute_payment is False
    assert "authoritative revalidation required" in res.reason


def test_human_review_approved_on_drift_requires_revalidation(base_time: datetime):
    """Approval does not mean PASS; revalidation must succeed."""
    policy = OperationalModePolicy(mode=OperationalMode.HUMAN_REVIEW)
    review = HumanReviewRequirement(
        review_id="rev_03",
        transaction_id="tx_hr_06",
        intent_id="intent_01",
        agent_id="buyer_alice",
        merchant_id="merchant_store",
        status=HumanReviewStatus.APPROVED,
        reason="Operator approved",
        integrity_status=IntegrityStatus.DRIFT,
        kill_switch_state=KillSwitchState.RUNNING,
        required_at=base_time,
        reviewed_at=base_time,
        reviewed_by="risk_officer_bob",
    )

    res = OperationalModeEngine.evaluate(
        policy=policy,
        transaction_id="tx_hr_06",
        integrity_status=IntegrityStatus.DRIFT,
        kill_switch_state=KillSwitchState.RUNNING,
        review_requirement=review,
        reference_time=base_time,
    )

    assert res.action == OperationalAction.BLOCK_EXECUTION
    assert res.can_execute_payment is False
    assert "revalidation required" in res.reason


def test_human_review_rejected_blocks_execution(base_time: datetime):
    policy = OperationalModePolicy(mode=OperationalMode.HUMAN_REVIEW)
    review = HumanReviewRequirement(
        review_id="rev_04",
        transaction_id="tx_hr_07",
        intent_id="intent_01",
        agent_id="buyer_alice",
        merchant_id="merchant_store",
        status=HumanReviewStatus.REJECTED,
        reason="Price drift rejected",
        integrity_status=IntegrityStatus.DRIFT,
        kill_switch_state=KillSwitchState.RUNNING,
        required_at=base_time,
        reviewed_at=base_time,
        reviewed_by="risk_officer_bob",
        decision_rationale="Unauthorized item fee detected",
    )

    res = OperationalModeEngine.evaluate(
        policy=policy,
        transaction_id="tx_hr_07",
        integrity_status=IntegrityStatus.PASS,
        kill_switch_state=KillSwitchState.RUNNING,
        review_requirement=review,
        reference_time=base_time,
    )

    assert res.action == OperationalAction.BLOCK_EXECUTION
    assert res.can_execute_payment is False
    assert res.human_review_status == HumanReviewStatus.REJECTED
