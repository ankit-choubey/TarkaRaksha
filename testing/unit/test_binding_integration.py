"""Integration tests for I8 Transaction Binding Service and TransactionService orchestration."""
from datetime import datetime, timezone, timedelta
import pytest

from backend.app.domain.binding import (
    BindingContext,
    BindingStatus,
    BindingViolationCode,
    PaymentBindingClaim,
)
from backend.app.domain.models.enums import IntegrityStatus, TransactionState
from backend.app.domain.models.intent import IntentContract, IntentItem
from backend.app.domain.models.money import Money
from backend.app.domain.models.payment import ProviderPayment, ProviderOrder
from backend.app.domain.models.slice import (
    CreateTransactionRequest,
    CompleteTransactionRequest,
)
from backend.app.services.binding import (
    TransactionBindingService,
    DuplicateOrderBindingError,
    DuplicatePaymentBindingError,
    AttemptLimitExceededError,
)
from backend.app.services.payment.fake_provider import FakePaymentProvider
from backend.app.services.payment.signatures import compute_payment_signature
from backend.app.services.transaction_service import TransactionService


@pytest.fixture
def now():
    return datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def sample_intent(now):
    return IntentContract(
        intent_id="intent_integ_1",
        issued_by="user_alice",
        issued_at=now,
        expires_at=now + timedelta(hours=2),
        currency="INR",
        max_total=Money(amount=100000, currency="INR"),
        items=[
            IntentItem(
                item_id="item_1",
                sku="SKU-BOOK-1",
                name="Security Handbook",
                quantity=1,
                unit_price=Money(amount=100000, currency="INR"),
                total_price=Money(amount=100000, currency="INR"),
            )
        ],
    )


def test_binding_service_order_uniqueness(now):
    """Test that an order ID cannot be bound to two different transactions."""
    service = TransactionBindingService()

    # Register order-1 to tx-1
    service.register_binding(
        intent_id="intent-1",
        agent_id="agent-1",
        merchant_id="merchant-1",
        transaction_id="tx-1",
        order_id="order-unique-123",
        created_at=now,
    )

    # Attempt to register the same order-1 to tx-2 must fail
    with pytest.raises(DuplicateOrderBindingError) as exc_info:
        service.register_binding(
            intent_id="intent-2",
            agent_id="agent-2",
            merchant_id="merchant-1",
            transaction_id="tx-2",
            order_id="order-unique-123",
            created_at=now,
        )
    assert "already bound to transaction tx-1" in str(exc_info.value)


def test_binding_service_payment_uniqueness(now):
    """Test that a payment ID cannot be consumed by two different transactions."""
    service = TransactionBindingService()

    service.register_binding(
        intent_id="intent-1",
        agent_id="agent-1",
        merchant_id="merchant-1",
        transaction_id="tx-1",
        order_id="order-1",
        attempt_id="att_1",
        created_at=now,
    )
    service.register_binding(
        intent_id="intent-2",
        agent_id="agent-2",
        merchant_id="merchant-1",
        transaction_id="tx-2",
        order_id="order-2",
        attempt_id="att_1",
        created_at=now,
    )

    # Consume pay-1 for tx-1
    service.consume_attempt(
        transaction_id="tx-1",
        attempt_id="att_1",
        payment_id="pay-reused-999",
        now=now,
    )

    # Attempting to consume pay-1 for tx-2 must raise DuplicatePaymentBindingError
    with pytest.raises(DuplicatePaymentBindingError) as exc_info:
        service.consume_attempt(
            transaction_id="tx-2",
            attempt_id="att_1",
            payment_id="pay-reused-999",
            now=now,
        )
    assert "already consumed by transaction tx-1" in str(exc_info.value)


def test_binding_service_attempt_limits(now):
    """Test that attempt registration obeys strict max limits."""
    service = TransactionBindingService(max_attempts_per_transaction=2)

    service.register_binding(
        intent_id="intent-1",
        agent_id="agent-1",
        merchant_id="merchant-1",
        transaction_id="tx-1",
        order_id="order-1",
        attempt_id="att_1",
        created_at=now,
    )

    # Register 2nd attempt
    service.register_attempt(
        transaction_id="tx-1",
        attempt_id="att_2",
        agent_id="agent-1",
        merchant_id="merchant-1",
        now=now,
    )

    # 3rd attempt exceeds max_attempts=2
    with pytest.raises(AttemptLimitExceededError) as exc_info:
        service.register_attempt(
            transaction_id="tx-1",
            attempt_id="att_3",
            agent_id="agent-1",
            merchant_id="merchant-1",
            now=now,
        )
    assert "exceeds maximum allowed attempts (2)" in str(exc_info.value)


def test_transaction_service_lifecycle_with_binding(sample_intent, now):
    """Test end-to-end TransactionService lifecycle properly creates and verifies bindings."""
    secret = "mock_secret"
    provider = FakePaymentProvider(mock_secret=secret)
    tx_service = TransactionService(default_provider=provider)

    # 1. Create Transaction
    create_req = CreateTransactionRequest(
        intent=sample_intent,
    )
    create_resp = tx_service.create_transaction(create_req, now=now)
    tx_id = create_resp.transaction_id
    order_id = create_resp.order_id

    # Verify authoritative binding context exists in session
    session = tx_service.get_session(tx_id)
    assert session is not None
    assert session.binding_context is not None
    assert session.binding_context.transaction_id == tx_id
    assert session.binding_context.order_id == order_id
    assert session.binding_context.intent_id == sample_intent.intent_id

    # 2. Complete Transaction with legitimate payment & signature
    payment_id = "pay_legit_001"
    signature = compute_payment_signature(order_id, payment_id, secret)

    # Seed fake provider payment
    provider.seed_payment(
        ProviderPayment(
            payment_id=payment_id,
            order_id=order_id,
            amount=sample_intent.max_total,
            status="captured",
            captured=True,
            method="upi",
            created_at=now,
        )
    )

    complete_req = CompleteTransactionRequest(
        transaction_id=tx_id,
        order_id=order_id,
        payment_id=payment_id,
        signature=signature,
    )

    comp_resp = tx_service.complete_transaction(
        request=complete_req,
        now=now + timedelta(seconds=30),
    )

    assert comp_resp.state == TransactionState.PASS
    assert session.binding_outcome is not None
    assert session.binding_outcome.is_valid is True
    assert session.binding_outcome.status == IntegrityStatus.PASS


def test_transaction_service_rejects_mismatched_order_in_completion(sample_intent, now):
    """Test that TransactionService raises ValueError when completion request uses mismatched order."""
    secret = "mock_secret"
    provider = FakePaymentProvider(mock_secret=secret)
    tx_service = TransactionService(default_provider=provider)

    resp1 = tx_service.create_transaction(
        CreateTransactionRequest(intent=sample_intent),
        now=now,
    )
    tx1_id = resp1.transaction_id

    complete_req = CompleteTransactionRequest(
        transaction_id=tx1_id,
        order_id="order_attacker_substituted_999",
        payment_id="pay_mismatched_001",
        signature="dummy_sig",
    )

    with pytest.raises(ValueError) as exc_info:
        tx_service.complete_transaction(request=complete_req, now=now)
    assert "does not match bound order" in str(exc_info.value)


def test_transaction_service_detects_cross_transaction_payment_replay(sample_intent, now):
    """Test that TransactionService flags DRIFT when a payment ID is replayed across transactions."""
    secret = "mock_secret"
    provider = FakePaymentProvider(mock_secret=secret)
    tx_service = TransactionService(default_provider=provider)

    # 1. Transaction 1 settles legitimate payment
    resp1 = tx_service.create_transaction(
        CreateTransactionRequest(intent=sample_intent),
        now=now,
    )
    tx1_id = resp1.transaction_id
    order1_id = resp1.order_id

    pay_shared = "pay_replayed_shared_123"
    sig1 = compute_payment_signature(order1_id, pay_shared, secret)
    provider.seed_payment(
        ProviderPayment(
            payment_id=pay_shared,
            order_id=order1_id,
            amount=sample_intent.max_total,
            status="captured",
            captured=True,
            method="upi",
            created_at=now,
        )
    )
    tx_service.complete_transaction(
        CompleteTransactionRequest(
            transaction_id=tx1_id,
            order_id=order1_id,
            payment_id=pay_shared,
            signature=sig1,
        ),
        now=now + timedelta(seconds=5),
    )

    # 2. Transaction 2 attempts to claim the exact same payment_id
    intent2 = sample_intent.model_copy(update={"intent_id": "intent_integ_2"})
    resp2 = tx_service.create_transaction(
        CreateTransactionRequest(intent=intent2),
        now=now + timedelta(seconds=10),
    )
    tx2_id = resp2.transaction_id
    order2_id = resp2.order_id

    sig2 = compute_payment_signature(order2_id, pay_shared, secret)
    # Even if provider or attacker claims pay_shared belongs to order2
    provider.seed_payment(
        ProviderPayment(
            payment_id=pay_shared,
            order_id=order2_id,
            amount=sample_intent.max_total,
            status="captured",
            captured=True,
            method="upi",
            created_at=now,
        )
    )
    comp2 = tx_service.complete_transaction(
        CompleteTransactionRequest(
            transaction_id=tx2_id,
            order_id=order2_id,
            payment_id=pay_shared,
            signature=sig2,
        ),
        now=now + timedelta(seconds=15),
    )

    assert comp2.state == TransactionState.DRIFT
    assert comp2.integrity_status == IntegrityStatus.DRIFT
    assert any("CROSS_TRANSACTION_REUSE" in v or "Binding" in v for v in comp2.violations)
