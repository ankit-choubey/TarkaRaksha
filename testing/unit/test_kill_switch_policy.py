"""Unit tests for I9 Kill Switch policy and transition rules."""
from datetime import datetime, timezone, timedelta
import pytest

from backend.app.domain.binding.contracts import (
    BindingContext,
    BindingVerificationOutcome,
    BindingViolationCode,
)
from backend.app.domain.kill_switch.contracts import (
    ExecutionDecision,
    KillSwitchState,
    KillTrigger,
    RevalidationRequest,
    UnauthorizedResumeError,
)
from backend.app.domain.kill_switch.policy import KillSwitchPolicy
from backend.app.domain.models.enums import EvidenceAuthority, EvidenceSource, IntegrityStatus
from backend.app.domain.models.evidence import Evidence
from backend.app.domain.models.intent import IntentContract, IntentItem
from backend.app.domain.models.integrity import IntegrityResult
from backend.app.domain.models.money import Money


@pytest.fixture
def now():
    return datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)


def test_permitted_transitions_validation():
    # Legal transitions
    KillSwitchPolicy.validate_transition(KillSwitchState.RUNNING, KillSwitchState.PAUSED)
    KillSwitchPolicy.validate_transition(KillSwitchState.RUNNING, KillSwitchState.REQUIRES_REVALIDATION)
    KillSwitchPolicy.validate_transition(KillSwitchState.RUNNING, KillSwitchState.KILLED)
    KillSwitchPolicy.validate_transition(KillSwitchState.PAUSED, KillSwitchState.RUNNING)
    KillSwitchPolicy.validate_transition(KillSwitchState.PAUSED, KillSwitchState.KILLED)
    KillSwitchPolicy.validate_transition(KillSwitchState.REQUIRES_REVALIDATION, KillSwitchState.RUNNING)
    KillSwitchPolicy.validate_transition(KillSwitchState.REQUIRES_REVALIDATION, KillSwitchState.KILLED)
    KillSwitchPolicy.validate_transition(KillSwitchState.KILLED, KillSwitchState.REQUIRES_REVALIDATION)

    # Idempotent no-ops
    KillSwitchPolicy.validate_transition(KillSwitchState.RUNNING, KillSwitchState.RUNNING)
    KillSwitchPolicy.validate_transition(KillSwitchState.KILLED, KillSwitchState.KILLED)


def test_forbidden_killed_to_running_direct_transition():
    # Direct transition from KILLED to RUNNING is strictly forbidden
    with pytest.raises(UnauthorizedResumeError) as exc_info:
        KillSwitchPolicy.validate_transition(KillSwitchState.KILLED, KillSwitchState.RUNNING)
    assert "Direct transition from KILLED to RUNNING is strictly forbidden" in str(exc_info.value)


def test_evaluate_integrity_findings_drift(now):
    drift_result = IntegrityResult(
        evaluation_id="eval_1",
        intent_id="intent_1",
        status=IntegrityStatus.DRIFT,
        evaluated_at=now,
        rule_results={"EconomicIntegrityRule": False},
        violations=["Amount discrepancy: expected 1000, observed 2000"],
    )
    finding = KillSwitchPolicy.evaluate_integrity_findings(drift_result)
    assert finding is not None
    new_state, decision, trigger, reason = finding
    assert new_state == KillSwitchState.KILLED
    assert decision == ExecutionDecision.BLOCK
    assert trigger == KillTrigger.CRITICAL_DRIFT
    assert "Amount discrepancy" in reason


def test_evaluate_integrity_findings_repeated_unknown(now):
    unknown_result = IntegrityResult(
        evaluation_id="eval_2",
        intent_id="intent_1",
        status=IntegrityStatus.UNKNOWN,
        evaluated_at=now,
        rule_results={},
        violations=["Evidence unavailable"],
    )
    # 1 attempt below tolerance: no finding
    assert KillSwitchPolicy.evaluate_integrity_findings(unknown_result, unknown_attempts=1, max_unknown_tolerance=2) is None

    # 2 attempts reached tolerance: requires revalidation
    finding = KillSwitchPolicy.evaluate_integrity_findings(unknown_result, unknown_attempts=2, max_unknown_tolerance=2)
    assert finding is not None
    new_state, decision, trigger, reason = finding
    assert new_state == KillSwitchState.REQUIRES_REVALIDATION
    assert decision == ExecutionDecision.REQUIRE_REVALIDATION
    assert trigger == KillTrigger.REPEATED_UNKNOWN


def test_evaluate_binding_findings(now):
    binding_outcome = BindingVerificationOutcome(
        is_valid=False,
        status=IntegrityStatus.DRIFT,
        violations=[BindingViolationCode.ORDER_MISMATCH],
        details={"order_id": "Mismatch"},
        explanation="Order binding mismatch detected",
        verified_at=now,
    )
    finding = KillSwitchPolicy.evaluate_binding_outcome(binding_outcome)
    assert finding is not None
    new_state, decision, trigger, reason = finding
    assert new_state == KillSwitchState.KILLED
    assert decision == ExecutionDecision.BLOCK
    assert trigger == KillTrigger.BINDING_VIOLATION
    assert "ORDER_MISMATCH" in reason


def test_evaluate_intent_freshness(now):
    intent = IntentContract(
        intent_id="intent_exp",
        issued_by="user_1",
        issued_at=now - timedelta(hours=2),
        expires_at=now - timedelta(minutes=10),  # expired 10 minutes ago
        currency="INR",
        max_total=Money(amount=50000, currency="INR"),
        items=[
            IntentItem(
                item_id="item_1",
                sku="SKU-1",
                name="Authorized Item",
                quantity=1,
                unit_price=Money(amount=50000, currency="INR"),
                total_price=Money(amount=50000, currency="INR"),
            )
        ],
    )
    finding = KillSwitchPolicy.evaluate_intent_freshness(intent, reference_time=now)
    assert finding is not None
    new_state, decision, trigger, reason = finding
    assert new_state == KillSwitchState.REQUIRES_REVALIDATION
    assert decision == ExecutionDecision.REQUIRE_REVALIDATION
    assert trigger == KillTrigger.EXPIRED_AUTHORIZATION


def test_evaluate_revalidation_success(now):
    ev = Evidence(
        evidence_id="ev_1",
        intent_id="intent_1",
        transaction_id="tx_1",
        source=EvidenceSource.RAZORPAY,
        authority=EvidenceAuthority.AUTHORITATIVE,
        field_name="payment_status",
        field_value="captured",
        observed_at=now,
        is_authoritative=True,
    )
    req = RevalidationRequest(
        request_id="rev_1",
        transaction_id="tx_1",
        intent_id="intent_1",
        agent_id="agent_1",
        merchant_id="merch_1",
        actor="admin_auditor",
        evidence=[ev],
        reason="Verified bank evidence",
        requested_at=now,
    )
    outcome = KillSwitchPolicy.evaluate_revalidation(
        request=req,
        expected_transaction_id="tx_1",
        expected_intent_id="intent_1",
        expected_agent_id="agent_1",
        expected_merchant_id="merch_1",
        reference_time=now,
    )
    assert outcome.is_valid is True
    assert outcome.decision == ExecutionDecision.ALLOW
    assert len(outcome.violations) == 0


def test_evaluate_revalidation_mismatched_context(now):
    req = RevalidationRequest(
        request_id="rev_2",
        transaction_id="tx_attacker_substituted",
        intent_id="intent_1",
        agent_id="agent_1",
        merchant_id="merch_1",
        actor="admin_auditor",
        evidence=[],
        reason="Tampered request",
        requested_at=now,
    )
    outcome = KillSwitchPolicy.evaluate_revalidation(
        request=req,
        expected_transaction_id="tx_1",
        expected_intent_id="intent_1",
        expected_agent_id="agent_1",
        expected_merchant_id="merch_1",
        reference_time=now,
    )
    assert outcome.is_valid is False
    assert outcome.decision == ExecutionDecision.BLOCK
    assert any("Mismatched transaction_id" in v for v in outcome.violations)
    assert any("requires at least one authoritative evidence item" in v for v in outcome.violations)
