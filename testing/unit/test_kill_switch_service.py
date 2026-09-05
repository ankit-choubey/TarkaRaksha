"""Unit tests for KillSwitchService orchestrator."""
from datetime import datetime, timezone, timedelta
import pytest

from backend.app.domain.binding.contracts import (
    BindingContext,
    BindingVerificationOutcome,
    BindingViolationCode,
)
from backend.app.domain.kill_switch.contracts import (
    ExecutionBlockedError,
    ExecutionDecision,
    KillSwitchState,
    KillTrigger,
    RevalidationRequest,
    UnauthorizedResumeError,
)
from backend.app.domain.models.enums import EvidenceAuthority, EvidenceSource, IntegrityStatus
from backend.app.domain.models.evidence import Evidence
from backend.app.domain.models.intent import IntentContract, IntentItem
from backend.app.domain.models.integrity import IntegrityResult
from backend.app.domain.models.money import Money
from backend.app.services.kill_switch.service import KillSwitchService


@pytest.fixture
def now():
    return datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def valid_intent(now):
    return IntentContract(
        intent_id="intent_test_1",
        issued_by="buyer_1",
        issued_at=now - timedelta(minutes=10),
        expires_at=now + timedelta(hours=1),
        currency="INR",
        max_total=Money(amount=100000, currency="INR"),
        items=[
            IntentItem(
                item_id="item_1",
                sku="SKU-1",
                name="Valid Item",
                quantity=1,
                unit_price=Money(amount=100000, currency="INR"),
                total_price=Money(amount=100000, currency="INR"),
            )
        ],
    )


@pytest.fixture
def service():
    return KillSwitchService(max_unknown_tolerance=2)


def test_service_register_and_get_state(service, now):
    rec = service.register_transaction(
        transaction_id="tx_100",
        intent_id="intent_100",
        agent_id="agent_1",
        merchant_id="merchant_1",
        created_at=now,
    )
    assert rec.transaction_id == "tx_100"
    assert service.get_state("tx_100") == KillSwitchState.RUNNING

    ctx = service.get_context("tx_100")
    assert ctx["intent_id"] == "intent_100"
    assert ctx["agent_id"] == "agent_1"
    assert ctx["merchant_id"] == "merchant_1"

    # Default for unknown transaction is fail-closed KILLED
    assert service.get_state("tx_nonexistent") == KillSwitchState.KILLED


def test_assert_can_execute_running_succeeds(service, now):
    service.register_transaction("tx_101", "intent_1", created_at=now)
    # Should not raise
    service.assert_can_execute("tx_101", operation_name="create_order")


def test_assert_can_execute_blocked_raises(service, now):
    service.register_transaction("tx_102", "intent_1", created_at=now)
    service.kill(
        "tx_102",
        trigger=KillTrigger.POLICY_VIOLATION,
        reason="Test kill",
        timestamp=now,
    )
    with pytest.raises(ExecutionBlockedError) as exc_info:
        service.assert_can_execute("tx_102", operation_name="capture_payment")
    assert exc_info.value.state == KillSwitchState.KILLED
    assert exc_info.value.trigger == KillTrigger.POLICY_VIOLATION
    assert "capture_payment" in str(exc_info.value)


def test_kill_idempotency_and_history(service, now):
    service.register_transaction("tx_103", "intent_1", created_at=now)
    rec1 = service.kill("tx_103", trigger=KillTrigger.ADMINISTRATIVE_KILL, reason="Admin stopped tx", timestamp=now)
    rec2 = service.kill("tx_103", trigger=KillTrigger.ADMINISTRATIVE_KILL, reason="Admin stopped tx", timestamp=now)
    assert rec1.record_id == rec2.record_id

    history = service.get_history("tx_103")
    # init record + 1 kill record = 2 records total (not 3, because idempotent)
    assert len(history) == 2


def test_pause_unpause_flow(service, now):
    service.register_transaction("tx_104", "intent_1", created_at=now)
    p_rec = service.pause("tx_104", reason="Manual inspection needed", timestamp=now)
    assert p_rec.resulting_state == KillSwitchState.PAUSED
    assert service.get_state("tx_104") == KillSwitchState.PAUSED

    # Execution blocked while paused
    with pytest.raises(ExecutionBlockedError):
        service.assert_can_execute("tx_104")

    # Unpause restores to RUNNING
    u_rec = service.unpause("tx_104", reason="Inspection passed", timestamp=now)
    assert u_rec.resulting_state == KillSwitchState.RUNNING
    assert service.get_state("tx_104") == KillSwitchState.RUNNING

    # Can execute again
    service.assert_can_execute("tx_104")

    # Cannot unpause if not paused
    with pytest.raises(ValueError):
        service.unpause("tx_104")


def test_revalidation_lifecycle_from_killed(service, now):
    service.register_transaction(
        transaction_id="tx_105",
        intent_id="intent_105",
        agent_id="agent_1",
        merchant_id="merchant_1",
        created_at=now,
    )
    service.kill("tx_105", trigger=KillTrigger.CRITICAL_DRIFT, reason="Amount drift detected", timestamp=now)
    assert service.get_state("tx_105") == KillSwitchState.KILLED

    ev = Evidence(
        evidence_id="ev_1",
        intent_id="intent_105",
        transaction_id="tx_105",
        source=EvidenceSource.RAZORPAY,
        authority=EvidenceAuthority.AUTHORITATIVE,
        field_name="payment_status",
        field_value="captured",
        observed_at=now,
        is_authoritative=True,
    )
    req = RevalidationRequest(
        request_id="rev_1",
        transaction_id="tx_105",
        intent_id="intent_105",
        agent_id="agent_1",
        merchant_id="merchant_1",
        actor="super_admin",
        evidence=[ev],
        reason="Audited and resolved by human supervisor",
        requested_at=now,
    )

    outcome = service.revalidate("tx_105", req, reference_time=now)
    assert outcome.is_valid is True
    assert outcome.decision == ExecutionDecision.ALLOW
    assert service.get_state("tx_105") == KillSwitchState.RUNNING

    # Assert execution succeeds again
    service.assert_can_execute("tx_105")


def test_revalidation_failure_stays_blocked(service, now):
    service.register_transaction(
        transaction_id="tx_106",
        intent_id="intent_106",
        agent_id="agent_1",
        merchant_id="merchant_1",
        created_at=now,
    )
    service.kill("tx_106", trigger=KillTrigger.POLICY_VIOLATION, reason="Policy breached", timestamp=now)

    # Revalidation with missing evidence and mismatched agent
    bad_req = RevalidationRequest(
        request_id="rev_bad",
        transaction_id="tx_106",
        intent_id="intent_106",
        agent_id="wrong_agent",
        merchant_id="merchant_1",
        actor="attacker",
        evidence=[],
        reason="Forged revalidation",
        requested_at=now,
    )

    outcome = service.revalidate("tx_106", bad_req, reference_time=now)
    assert outcome.is_valid is False
    assert outcome.decision == ExecutionDecision.BLOCK
    assert service.get_state("tx_106") == KillSwitchState.KILLED

    with pytest.raises(ExecutionBlockedError):
        service.assert_can_execute("tx_106")


def test_evaluate_and_enforce_expired_intent(service, now):
    expired_intent = IntentContract(
        intent_id="intent_exp",
        issued_by="buyer_1",
        issued_at=now - timedelta(hours=2),
        expires_at=now - timedelta(minutes=5),  # expired
        currency="INR",
        max_total=Money(amount=50000, currency="INR"),
        items=[
            IntentItem(
                item_id="item_1",
                sku="SKU-1",
                name="Item",
                quantity=1,
                unit_price=Money(amount=50000, currency="INR"),
                total_price=Money(amount=50000, currency="INR"),
            )
        ],
    )
    service.register_transaction("tx_107", "intent_exp", created_at=now)
    rec = service.evaluate_and_enforce("tx_107", intent=expired_intent, reference_time=now)

    assert rec is not None
    assert rec.resulting_state == KillSwitchState.REQUIRES_REVALIDATION
    assert rec.trigger == KillTrigger.EXPIRED_AUTHORIZATION
    assert service.get_state("tx_107") == KillSwitchState.REQUIRES_REVALIDATION


def test_evaluate_and_enforce_binding_violation(service, valid_intent, now):
    service.register_transaction("tx_108", valid_intent.intent_id, created_at=now)
    bad_binding = BindingVerificationOutcome(
        is_valid=False,
        status=IntegrityStatus.DRIFT,
        violations=[BindingViolationCode.INTENT_MISMATCH],
        details={"error": "Intent mismatch detected"},
        explanation="Intent mismatch detected",
        verified_at=now,
    )
    rec = service.evaluate_and_enforce(
        "tx_108",
        intent=valid_intent,
        binding_outcome=bad_binding,
        reference_time=now,
    )
    assert rec is not None
    assert rec.resulting_state == KillSwitchState.KILLED
    assert rec.trigger == KillTrigger.BINDING_VIOLATION
    assert service.get_state("tx_108") == KillSwitchState.KILLED


def test_evaluate_and_enforce_critical_drift(service, valid_intent, now):
    service.register_transaction("tx_109", valid_intent.intent_id, created_at=now)
    drift_result = IntegrityResult(
        evaluation_id="eval_109",
        intent_id=valid_intent.intent_id,
        status=IntegrityStatus.DRIFT,
        evaluated_at=now,
        rule_results={"EconomicIntegrityRule": False},
        violations=["Payment amount drift: expected 100000, observed 99999"],
    )
    rec = service.evaluate_and_enforce(
        "tx_109",
        intent=valid_intent,
        integrity_result=drift_result,
        reference_time=now,
    )
    assert rec is not None
    assert rec.resulting_state == KillSwitchState.KILLED
    assert rec.trigger == KillTrigger.CRITICAL_DRIFT
    assert service.get_state("tx_109") == KillSwitchState.KILLED


def test_evaluate_and_enforce_unknown_tolerance(service, valid_intent, now):
    service.register_transaction("tx_110", valid_intent.intent_id, created_at=now)
    unknown_result = IntegrityResult(
        evaluation_id="eval_110",
        intent_id=valid_intent.intent_id,
        status=IntegrityStatus.UNKNOWN,
        evaluated_at=now,
        rule_results={},
        violations=["Webhook delay: evidence missing"],
    )

    # 1st UNKNOWN: within tolerance (max_tolerance=2), does not initiate revalidation
    rec1 = service.evaluate_and_enforce(
        "tx_110",
        intent=valid_intent,
        integrity_result=unknown_result,
        reference_time=now,
    )
    assert rec1 is None
    assert service.get_state("tx_110") == KillSwitchState.RUNNING

    # 2nd UNKNOWN: tolerance reached (2 unknown attempts >= max_unknown_tolerance 2)
    rec2 = service.evaluate_and_enforce(
        "tx_110",
        intent=valid_intent,
        integrity_result=unknown_result,
        reference_time=now,
    )
    assert rec2 is not None
    assert rec2.resulting_state == KillSwitchState.REQUIRES_REVALIDATION
    assert rec2.trigger == KillTrigger.REPEATED_UNKNOWN
    assert service.get_state("tx_110") == KillSwitchState.REQUIRES_REVALIDATION
