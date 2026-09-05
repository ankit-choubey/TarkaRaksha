"""Integration tests for I9 Kill Switch with TransactionService."""
from datetime import datetime, timezone, timedelta
from typing import Optional
import pytest

from backend.app.domain.kill_switch import (
    ExecutionBlockedError,
    ExecutionDecision,
    KillSwitchState,
    KillTrigger,
    RevalidationRequest,
    UnauthorizedResumeError,
)
from backend.app.domain.models import (
    CompleteTransactionRequest,
    CreateTransactionRequest,
    IntegrityStatus,
    IntentContract,
    IntentItem,
    Money,
    TransactionState,
    Evidence,
    EvidenceAuthority,
    EvidenceSource,
)
from backend.app.domain.models.payment import ProviderPayment
from backend.app.services.payment import (
    FakePaymentProvider,
    compute_payment_signature,
)
from backend.app.services.transaction_service import TransactionService

TEST_KEY_SECRET = "test_secret_key_ks_integ_12345"


def seed_mock_payment(
    provider: FakePaymentProvider,
    order_id: str,
    amount: Money,
    status: str = "captured",
    created_at: Optional[datetime] = None,
) -> ProviderPayment:
    payment_id = f"pay_mock_{order_id}_{amount.amount}"
    ts = created_at or datetime(2026, 9, 5, 12, 0, 1, tzinfo=timezone.utc)
    payment = ProviderPayment(
        payment_id=payment_id,
        order_id=order_id,
        amount=amount,
        status=status,
        method="card",
        captured=(status == "captured"),
        currency=amount.currency,
        created_at=ts,
    )
    provider.seed_payment(payment)
    return payment


@pytest.fixture
def now():
    return datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def fake_provider():
    return FakePaymentProvider(mock_secret=TEST_KEY_SECRET)


@pytest.fixture
def tx_service(fake_provider):
    return TransactionService(default_provider=fake_provider)


@pytest.fixture
def valid_intent(now):
    return IntentContract(
        intent_id="intent_ks_integ_1",
        issued_by="user_integ",
        issued_at=now - timedelta(minutes=10),
        expires_at=now + timedelta(hours=1),
        currency="INR",
        max_total=Money(amount=50000, currency="INR"),
        items=[
            IntentItem(
                item_id="item_ks_1",
                sku="SKU-KS-1",
                name="Kill Switch Test Item",
                quantity=1,
                unit_price=Money(amount=50000, currency="INR"),
                total_price=Money(amount=50000, currency="INR"),
            )
        ],
    )


def test_kill_switch_normal_execution_flow(tx_service, fake_provider, valid_intent, now):
    """Happy path: normal execution completes with PASS and remains RUNNING."""
    create_req = CreateTransactionRequest(intent=valid_intent)
    create_res = tx_service.create_transaction(create_req, now=now)

    # Initial safety state is RUNNING
    assert tx_service.get_kill_switch_state(create_res.transaction_id) == KillSwitchState.RUNNING

    payment = seed_mock_payment(
        provider=fake_provider,
        order_id=create_res.order_id,
        amount=Money(amount=50000, currency="INR"),
        status="captured",
        created_at=now + timedelta(seconds=1),
    )
    sig = compute_payment_signature(
        order_id=create_res.order_id,
        payment_id=payment.payment_id,
        secret=TEST_KEY_SECRET,
    )
    comp_req = CompleteTransactionRequest(
        transaction_id=create_res.transaction_id,
        order_id=create_res.order_id,
        payment_id=payment.payment_id,
        signature=sig,
    )
    comp_res = tx_service.complete_transaction(comp_req, now=now + timedelta(seconds=5))

    assert comp_res.state == TransactionState.PASS
    assert comp_res.integrity_status == IntegrityStatus.PASS
    assert tx_service.get_kill_switch_state(create_res.transaction_id) == KillSwitchState.RUNNING

    # Can execute check succeeds
    tx_service.kill_switch_service.assert_can_execute(create_res.transaction_id)


def test_kill_switch_administrative_kill_blocks_completion(tx_service, fake_provider, valid_intent, now):
    """Admin triggers kill_transaction: completion is blocked by execution safety gate."""
    create_req = CreateTransactionRequest(intent=valid_intent)
    create_res = tx_service.create_transaction(create_req, now=now)

    # Trigger admin kill switch
    tx_service.kill_transaction(
        transaction_id=create_res.transaction_id,
        trigger=KillTrigger.ADMINISTRATIVE_KILL,
        reason="Security team investigation",
        actor="SecOps_Lead",
    )
    assert tx_service.get_kill_switch_state(create_res.transaction_id) == KillSwitchState.KILLED

    payment = seed_mock_payment(
        provider=fake_provider,
        order_id=create_res.order_id,
        amount=Money(amount=50000, currency="INR"),
        status="captured",
        created_at=now + timedelta(seconds=1),
    )
    sig = compute_payment_signature(
        order_id=create_res.order_id,
        payment_id=payment.payment_id,
        secret=TEST_KEY_SECRET,
    )
    comp_req = CompleteTransactionRequest(
        transaction_id=create_res.transaction_id,
        order_id=create_res.order_id,
        payment_id=payment.payment_id,
        signature=sig,
    )

    with pytest.raises(ExecutionBlockedError) as exc_info:
        tx_service.complete_transaction(comp_req, now=now + timedelta(seconds=5))
    assert exc_info.value.state == KillSwitchState.KILLED
    assert exc_info.value.trigger == KillTrigger.ADMINISTRATIVE_KILL


def test_kill_switch_administrative_pause_blocks_until_unpaused(tx_service, fake_provider, valid_intent, now):
    """Admin pauses transaction: execution blocked until unpaused."""
    create_req = CreateTransactionRequest(intent=valid_intent)
    create_res = tx_service.create_transaction(create_req, now=now)

    tx_service.pause_transaction(
        transaction_id=create_res.transaction_id,
        reason="Operational inspection hold",
        actor="OpsManager",
    )
    assert tx_service.get_kill_switch_state(create_res.transaction_id) == KillSwitchState.PAUSED

    payment = seed_mock_payment(
        provider=fake_provider,
        order_id=create_res.order_id,
        amount=Money(amount=50000, currency="INR"),
        status="captured",
        created_at=now + timedelta(seconds=1),
    )
    sig = compute_payment_signature(
        order_id=create_res.order_id,
        payment_id=payment.payment_id,
        secret=TEST_KEY_SECRET,
    )
    comp_req = CompleteTransactionRequest(
        transaction_id=create_res.transaction_id,
        order_id=create_res.order_id,
        payment_id=payment.payment_id,
        signature=sig,
    )

    # Blocked while paused
    with pytest.raises(ExecutionBlockedError) as exc_info:
        tx_service.complete_transaction(comp_req, now=now + timedelta(seconds=5))
    assert exc_info.value.state == KillSwitchState.PAUSED

    # Unpause
    tx_service.unpause_transaction(create_res.transaction_id, reason="Inspection cleared")
    assert tx_service.get_kill_switch_state(create_res.transaction_id) == KillSwitchState.RUNNING

    # Now completion succeeds
    comp_res = tx_service.complete_transaction(comp_req, now=now + timedelta(seconds=10))
    assert comp_res.state == TransactionState.PASS


def test_kill_switch_drift_triggers_killed_and_blocks_further_execution(tx_service, fake_provider, valid_intent, now):
    """Critical drift transitions kill switch to KILLED, preventing retry/continuation."""
    create_req = CreateTransactionRequest(intent=valid_intent)
    create_res = tx_service.create_transaction(create_req, now=now)

    # Seed payment with drifted overcharged amount (60000 instead of 50000)
    payment = seed_mock_payment(
        provider=fake_provider,
        order_id=create_res.order_id,
        amount=Money(amount=60000, currency="INR"),
        status="captured",
        created_at=now + timedelta(seconds=1),
    )
    sig = compute_payment_signature(
        order_id=create_res.order_id,
        payment_id=payment.payment_id,
        secret=TEST_KEY_SECRET,
    )
    comp_req = CompleteTransactionRequest(
        transaction_id=create_res.transaction_id,
        order_id=create_res.order_id,
        payment_id=payment.payment_id,
        signature=sig,
    )

    comp_res = tx_service.complete_transaction(comp_req, now=now + timedelta(seconds=5))
    assert comp_res.state == TransactionState.DRIFT
    assert comp_res.integrity_status == IntegrityStatus.DRIFT

    # Safety control state is now deterministically KILLED
    assert tx_service.get_kill_switch_state(create_res.transaction_id) == KillSwitchState.KILLED

    history = tx_service.get_kill_switch_history(create_res.transaction_id)
    assert any(h.trigger == KillTrigger.CRITICAL_DRIFT for h in history)

    # Any subsequent attempt to complete or execute on this transaction is blocked
    with pytest.raises(ExecutionBlockedError) as exc_info:
        tx_service.complete_transaction(comp_req, now=now + timedelta(seconds=10))
    assert exc_info.value.state == KillSwitchState.KILLED
    assert exc_info.value.trigger == KillTrigger.CRITICAL_DRIFT


def test_kill_switch_revalidation_and_resumption(tx_service, fake_provider, valid_intent, now):
    """Transaction killed by drift can only resume after authoritative revalidation."""
    create_req = CreateTransactionRequest(intent=valid_intent)
    create_res = tx_service.create_transaction(create_req, now=now)

    # Admin kills transaction
    tx_service.kill_transaction(
        transaction_id=create_res.transaction_id,
        trigger=KillTrigger.POLICY_VIOLATION,
        reason="Suspicious transaction activity",
        actor="RiskEngine",
    )
    assert tx_service.get_kill_switch_state(create_res.transaction_id) == KillSwitchState.KILLED

    # Direct resume without revalidation is strictly blocked
    with pytest.raises(UnauthorizedResumeError):
        from backend.app.domain.kill_switch.policy import KillSwitchPolicy
        KillSwitchPolicy.validate_transition(KillSwitchState.KILLED, KillSwitchState.RUNNING)

    # Revalidation request with authoritative evidence
    ev = Evidence(
        evidence_id="ev_auth_1",
        intent_id=valid_intent.intent_id,
        transaction_id=create_res.transaction_id,
        source=EvidenceSource.RAZORPAY,
        authority=EvidenceAuthority.AUTHORITATIVE,
        field_name="payment_status",
        field_value="captured",
        observed_at=now,
        is_authoritative=True,
    )
    reval_req = RevalidationRequest(
        request_id="rev_req_01",
        transaction_id=create_res.transaction_id,
        intent_id=valid_intent.intent_id,
        agent_id="user_integ",
        merchant_id="merchant_default",
        actor="ChiefRiskOfficer",
        evidence=[ev],
        reason="Verified transaction legitimate through direct bank statement",
        requested_at=now + timedelta(minutes=5),
    )

    reval_outcome = tx_service.revalidate_transaction(
        transaction_id=create_res.transaction_id,
        request=reval_req,
        reference_time=now + timedelta(minutes=5),
    )
    assert reval_outcome.is_valid is True
    assert reval_outcome.decision == ExecutionDecision.ALLOW
    assert tx_service.get_kill_switch_state(create_res.transaction_id) == KillSwitchState.RUNNING

    # Execution gating now allows execution
    tx_service.kill_switch_service.assert_can_execute(create_res.transaction_id)
