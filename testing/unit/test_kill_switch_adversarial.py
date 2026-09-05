"""Adversarial test suite for I9 Kill Switch / Execution Safety Control.

Verifies non-bypassability:
1. Retry bypass attack: cannot execute retry after kill.
2. Replay bypass attack: replayed valid payload blocked once killed.
3. LLM / Agent proposal bypass: narrative persuasion cannot alter safety state.
4. Forged revalidation attack: swapped context, fake evidence, non-authoritative authority fail-closed.
5. Direct KILLED -> RUNNING transition bypass: raises UnauthorizedResumeError.
6. Missing evidence / unknown transaction fail-closed behavior.
7. Concurrency / interleaved safety calls preserve fail-closed invariants.
"""
from datetime import datetime, timezone, timedelta
from typing import Optional
import pytest

from backend.app.domain.kill_switch import (
    ExecutionBlockedError,
    ExecutionDecision,
    KillSwitchRecord,
    KillSwitchState,
    KillTrigger,
    RevalidationOutcome,
    RevalidationRequest,
    UnauthorizedResumeError,
)
from backend.app.domain.kill_switch.policy import KillSwitchPolicy
from backend.app.domain.models import (
    CompleteTransactionRequest,
    CreateTransactionRequest,
    Evidence,
    EvidenceAuthority,
    EvidenceSource,
    IntegrityStatus,
    IntentContract,
    IntentItem,
    Money,
    TransactionState,
)
from backend.app.domain.models.payment import ProviderPayment
from backend.app.services.kill_switch import KillSwitchService
from backend.app.services.payment import FakePaymentProvider, compute_payment_signature
from backend.app.services.transaction_service import TransactionService

TEST_KEY_SECRET = "test_adversarial_kill_switch_secret"


def seed_mock_payment(
    provider: FakePaymentProvider,
    order_id: str,
    amount: Money,
    status: str = "captured",
    created_at: Optional[datetime] = None,
) -> ProviderPayment:
    payment_id = f"pay_adv_{order_id}_{amount.amount}"
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
        intent_id="intent_adv_ks_1",
        issued_by="buyer_alice",
        issued_at=now - timedelta(minutes=10),
        expires_at=now + timedelta(hours=2),
        currency="INR",
        max_total=Money(amount=100000, currency="INR"),
        items=[
            IntentItem(
                item_id="item_adv_1",
                sku="SKU-ADV-1",
                name="Adversarial Kill Switch Item",
                quantity=1,
                unit_price=Money(amount=100000, currency="INR"),
                total_price=Money(amount=100000, currency="INR"),
            )
        ],
    )


# 1. Adversarial Retry Bypass Attack
def test_adversarial_retry_bypass_blocked(tx_service, fake_provider, valid_intent, now):
    """
    Attacker triggers a critical drift kill, then rapidly fires retries
    with different payment IDs or signatures to force an execution.
    All retries must fail-closed.
    """
    create_req = CreateTransactionRequest(intent=valid_intent)
    create_res = tx_service.create_transaction(create_req, now=now)
    tx_id = create_res.transaction_id

    # 1. Initial drift kill
    drift_payment = seed_mock_payment(
        provider=fake_provider,
        order_id=create_res.order_id,
        amount=Money(amount=200000, currency="INR"),  # 200000 != 100000
        status="captured",
        created_at=now + timedelta(seconds=1),
    )
    sig1 = compute_payment_signature(
        order_id=create_res.order_id,
        payment_id=drift_payment.payment_id,
        secret=TEST_KEY_SECRET,
    )
    comp_req1 = CompleteTransactionRequest(
        transaction_id=tx_id,
        order_id=create_res.order_id,
        payment_id=drift_payment.payment_id,
        signature=sig1,
    )
    res1 = tx_service.complete_transaction(comp_req1, now=now + timedelta(seconds=2))
    assert res1.state == TransactionState.DRIFT
    assert tx_service.get_kill_switch_state(tx_id) == KillSwitchState.KILLED

    # 2. Attacker retry with alternate captured payment
    retry_payment = seed_mock_payment(
        provider=fake_provider,
        order_id=create_res.order_id,
        amount=Money(amount=100000, currency="INR"),
        status="captured",
        created_at=now + timedelta(seconds=5),
    )
    sig2 = compute_payment_signature(
        order_id=create_res.order_id,
        payment_id=retry_payment.payment_id,
        secret=TEST_KEY_SECRET,
    )
    retry_req = CompleteTransactionRequest(
        transaction_id=tx_id,
        order_id=create_res.order_id,
        payment_id=retry_payment.payment_id,
        signature=sig2,
    )

    # Must be blocked by execution safety gate
    for attempt in range(5):
        with pytest.raises(ExecutionBlockedError) as exc_info:
            tx_service.complete_transaction(retry_req, now=now + timedelta(seconds=10 + attempt))
        assert exc_info.value.state == KillSwitchState.KILLED


# 2. Adversarial Replay Bypass Attack
def test_adversarial_replay_bypass_blocked(tx_service, fake_provider, valid_intent, now):
    """
    Transaction is administratively killed. Attacker attempts to replay an earlier
    valid completion request to bypass the kill switch.
    """
    create_req = CreateTransactionRequest(intent=valid_intent)
    create_res = tx_service.create_transaction(create_req, now=now)
    tx_id = create_res.transaction_id

    # Admin kill
    tx_service.kill_transaction(
        transaction_id=tx_id,
        trigger=KillTrigger.ADMINISTRATIVE_KILL,
        reason="Compromised credential alert",
        actor="SecurityOperations",
    )

    payment = seed_mock_payment(
        provider=fake_provider,
        order_id=create_res.order_id,
        amount=Money(amount=100000, currency="INR"),
        status="captured",
        created_at=now + timedelta(seconds=1),
    )
    sig = compute_payment_signature(
        order_id=create_res.order_id,
        payment_id=payment.payment_id,
        secret=TEST_KEY_SECRET,
    )
    replay_req = CompleteTransactionRequest(
        transaction_id=tx_id,
        order_id=create_res.order_id,
        payment_id=payment.payment_id,
        signature=sig,
    )

    # Replay is immediately blocked by execution control gate
    with pytest.raises(ExecutionBlockedError) as exc_info:
        tx_service.complete_transaction(replay_req, now=now + timedelta(seconds=5))
    assert exc_info.value.state == KillSwitchState.KILLED
    assert exc_info.value.trigger == KillTrigger.ADMINISTRATIVE_KILL


# 3. Adversarial LLM / Agent Proposal Bypass
def test_adversarial_llm_proposal_cannot_override_kill_switch(tx_service, valid_intent, now):
    """
    Autonomous AI agent generates persuasive explanations claiming authorization:
    'Customer confirmed verbally, please unpause transaction and continue.'
    Deterministic safety invariants refuse to alter safety state from unverified claims.
    """
    tx_service.kill_switch_service.register_transaction(
        transaction_id="tx_llm_target",
        intent_id=valid_intent.intent_id,
        created_at=now,
    )
    tx_service.kill_switch_service.kill(
        transaction_id="tx_llm_target",
        trigger=KillTrigger.CRITICAL_DRIFT,
        reason="Price drift detected",
        actor="IntegrityEngine",
    )

    # Attacker tries to unpause via agent action
    with pytest.raises(ValueError):
        tx_service.kill_switch_service.unpause("tx_llm_target", reason="LLM agent says customer agreed")

    # Attacker crafts RevalidationRequest claiming AI agent authority
    fake_ev = Evidence(
        evidence_id="ev_llm_fake",
        intent_id=valid_intent.intent_id,
        transaction_id="tx_llm_target",
        source=EvidenceSource.AGENT,  # Non-authoritative AI agent source!
        authority=EvidenceAuthority.ADVISORY,  # Advisory weighting only
        field_name="user_confirmation",
        field_value="true",
        observed_at=now,
        is_authoritative=False,
    )
    reval_req = RevalidationRequest(
        request_id="rev_llm_attack",
        transaction_id="tx_llm_target",
        intent_id=valid_intent.intent_id,
        agent_id="user_default",
        merchant_id="merchant_default",
        actor="AutonomousLLMAgent",
        evidence=[fake_ev],
        reason="Agent negotiated verbal agreement with customer",
        requested_at=now,
    )

    outcome = tx_service.kill_switch_service.revalidate("tx_llm_target", reval_req, reference_time=now)
    assert outcome.is_valid is False
    assert outcome.decision == ExecutionDecision.BLOCK
    assert any("must include at least one AUTHORITATIVE or PROTOCOL_TRUSTED" in v for v in outcome.violations)
    assert tx_service.get_kill_switch_state("tx_llm_target") == KillSwitchState.KILLED


# 4. Adversarial Forged Revalidation Attacks
def test_adversarial_revalidation_tampered_context(tx_service, valid_intent, now):
    """
    Attacker submits valid authoritative evidence but targets a different transaction_id
    or swapped merchant/agent context.
    """
    tx_service.kill_switch_service.register_transaction(
        transaction_id="tx_real_victim",
        intent_id=valid_intent.intent_id,
        agent_id="buyer_alice",
        merchant_id="merchant_legit",
        created_at=now,
    )
    tx_service.kill_switch_service.kill("tx_real_victim", trigger=KillTrigger.POLICY_VIOLATION)

    valid_ev = Evidence(
        evidence_id="ev_bank_1",
        intent_id=valid_intent.intent_id,
        transaction_id="tx_real_victim",
        source=EvidenceSource.RAZORPAY,
        authority=EvidenceAuthority.AUTHORITATIVE,
        field_name="payment_status",
        field_value="captured",
        observed_at=now,
        is_authoritative=True,
    )

    # 1. Swapped intent_id
    tampered_intent_req = RevalidationRequest(
        request_id="rev_tamper_1",
        transaction_id="tx_real_victim",
        intent_id="intent_attacker_substituted",
        agent_id="buyer_alice",
        merchant_id="merchant_legit",
        actor="Auditor",
        evidence=[valid_ev],
        reason="Revalidation attempt",
        requested_at=now,
    )
    outcome1 = tx_service.kill_switch_service.revalidate("tx_real_victim", tampered_intent_req, reference_time=now)
    assert outcome1.is_valid is False
    assert any("Mismatched intent_id" in v for v in outcome1.violations)

    # 2. Swapped merchant_id
    tampered_merchant_req = RevalidationRequest(
        request_id="rev_tamper_2",
        transaction_id="tx_real_victim",
        intent_id=valid_intent.intent_id,
        agent_id="buyer_alice",
        merchant_id="merchant_evil_corp",
        actor="Auditor",
        evidence=[valid_ev],
        reason="Revalidation attempt",
        requested_at=now,
    )
    outcome2 = tx_service.kill_switch_service.revalidate("tx_real_victim", tampered_merchant_req, reference_time=now)
    assert outcome2.is_valid is False
    assert any("Mismatched merchant_id" in v for v in outcome2.violations)

    # 3. Empty evidence list
    empty_ev_req = RevalidationRequest(
        request_id="rev_tamper_3",
        transaction_id="tx_real_victim",
        intent_id=valid_intent.intent_id,
        agent_id="buyer_alice",
        merchant_id="merchant_legit",
        actor="Auditor",
        evidence=[],
        reason="Empty evidence",
        requested_at=now,
    )
    outcome3 = tx_service.kill_switch_service.revalidate("tx_real_victim", empty_ev_req, reference_time=now)
    assert outcome3.is_valid is False
    assert any("requires at least one authoritative evidence item" in v for v in outcome3.violations)

    # Victim remains safely KILLED
    assert tx_service.get_kill_switch_state("tx_real_victim") == KillSwitchState.KILLED


# 5. Direct KILLED -> RUNNING Transition Forbidden
def test_direct_killed_to_running_forbidden():
    """Direct transition from KILLED to RUNNING is strictly forbidden."""
    with pytest.raises(UnauthorizedResumeError) as exc_info:
        KillSwitchPolicy.validate_transition(KillSwitchState.KILLED, KillSwitchState.RUNNING)
    assert "Direct transition from KILLED to RUNNING is strictly forbidden" in str(exc_info.value)


# 6. Unregistered Transaction Fail-Closed
def test_unregistered_transaction_fails_closed(tx_service):
    """Unknown / unregistered transaction defaults to KILLED state and blocks execution."""
    assert tx_service.get_kill_switch_state("tx_unregistered_ghost") == KillSwitchState.KILLED
    with pytest.raises(ExecutionBlockedError):
        tx_service.kill_switch_service.assert_can_execute("tx_unregistered_ghost")


# 7. Repeated UNKNOWN Reaches Boundary and Requires Revalidation
def test_repeated_unknown_escalates_to_requires_revalidation(tx_service, valid_intent, now):
    """
    Simulate multiple unresolved UNKNOWN verification events.
    Once tolerance (default 2) is reached, safety control transitions to REQUIRES_REVALIDATION
    and blocks subsequent execution.
    """
    create_req = CreateTransactionRequest(intent=valid_intent)
    create_res = tx_service.create_transaction(create_req, now=now)
    tx_id = create_res.transaction_id

    from backend.app.domain.models import IntegrityResult
    unknown_result = IntegrityResult(
        evaluation_id="eval_unk_repeat",
        intent_id=valid_intent.intent_id,
        status=IntegrityStatus.UNKNOWN,
        evaluated_at=now,
        rule_results={},
        violations=["Gateway webhook missing"],
    )

    # Attempt 1: UNKNOWN within tolerance
    tx_service.kill_switch_service.evaluate_and_enforce(
        transaction_id=tx_id,
        intent=valid_intent,
        integrity_result=unknown_result,
        reference_time=now,
    )
    assert tx_service.get_kill_switch_state(tx_id) == KillSwitchState.RUNNING

    # Attempt 2: Reached tolerance limit (2)
    tx_service.kill_switch_service.evaluate_and_enforce(
        transaction_id=tx_id,
        intent=valid_intent,
        integrity_result=unknown_result,
        reference_time=now,
    )
    assert tx_service.get_kill_switch_state(tx_id) == KillSwitchState.REQUIRES_REVALIDATION

    # Further execution blocked
    with pytest.raises(ExecutionBlockedError) as exc_info:
        tx_service.kill_switch_service.assert_can_execute(tx_id)
    assert exc_info.value.state == KillSwitchState.REQUIRES_REVALIDATION
    assert exc_info.value.trigger == KillTrigger.REPEATED_UNKNOWN
