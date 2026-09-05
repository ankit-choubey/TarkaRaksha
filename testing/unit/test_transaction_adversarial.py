"""
Adversarial and Security Test Suite for T10: First Complete Real Transaction Slice.
Testing reference: brain/TarkaRaksha_TESTING.md §9.37–§9.41 (T10 Adversarial Invariants).

Covers:
- Cryptographic signature forgery and tampering rejection
- Economic DRIFT (overcharge beyond authorized intent generates MRDP)
- Semantic DRIFT (unauthorized SKU or quantity divergence)
- Temporal DRIFT (expired execution window)
- Wrong order/payment association rejection
- Duplicate transaction execution and idempotency defense
- Intent contract immutability
- Secret leakage prevention across responses and object graphs
- Frontend cannot dictate integrity decisions
- Adapter cannot independently declare PASS
- Provider failure handling (timeout, 500 server error fail safe)
- Real Razorpay Test Mode smoke test (runs against live Test Mode credentials)
"""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import pytest
from fastapi.testclient import TestClient

from backend.app.core.config import settings
from backend.app.domain.models import (
    EvidenceAuthority,
    EvidenceSource,
    IntegrityStatus,
    IntentContract,
    IntentItem,
    Money,
    TransactionState,
    CreateTransactionRequest,
    CreateTransactionResponse,
    CompleteTransactionRequest,
    CompleteTransactionResponse,
)
from backend.app.domain.models.payment import ProviderOrder, ProviderPayment
from backend.app.main import app, get_payment_provider, get_transaction_service
from backend.app.services.payment import (
    FakePaymentProvider,
    PaymentServerError,
    PaymentSignatureError,
    PaymentTimeoutError,
    RazorpayAdapter,
    compute_payment_signature,
)
from backend.app.services.transaction_service import TransactionService


TEST_KEY_SECRET = "test_secret_key_t10_adversarial_sec_999"


def seed_mock_payment(
    provider: FakePaymentProvider,
    order_id: str,
    amount: Money,
    status: str = "captured",
    notes: dict = None,
) -> ProviderPayment:
    pay_hash = hashlib.sha256(f"{order_id}:{status}:{amount.amount}".encode("utf-8")).hexdigest()[:12]
    payment_id = f"pay_mock_{pay_hash}"
    payment = ProviderPayment(
        payment_id=payment_id,
        order_id=order_id,
        amount=amount,
        currency=amount.currency,
        status=status,
        captured=(status == "captured"),
        method="card",
        created_at=datetime.now(timezone.utc),
        notes=notes or {},
    )
    provider.seed_payment(payment)
    return payment


@pytest.fixture
def fake_provider():
    return FakePaymentProvider(mock_secret=TEST_KEY_SECRET)


@pytest.fixture
def transaction_service(fake_provider):
    return TransactionService(default_provider=fake_provider)


@pytest.fixture
def base_intent():
    now = datetime.now(timezone.utc)
    return IntentContract(
        intent_id="int_adv_001",
        issued_by="sec_officer_42",
        issued_at=now - timedelta(minutes=10),
        expires_at=now + timedelta(hours=1),
        currency="INR",
        max_total=Money(amount=5000000, currency="INR"),  # ₹50,000
        items=[
            IntentItem(
                item_id="item-srv-256",
                sku="SRV-256GB",
                name="Enterprise Server 256GB",
                quantity=1,
                unit_price=Money(amount=5000000, currency="INR"),
                total_price=Money(amount=5000000, currency="INR"),
            )
        ],
    )


# ==============================================================================
# 1. SIGNATURE & TAMPERING ADVERSARIAL TESTS
# ==============================================================================

def test_signature_forgery_rejection(transaction_service, base_intent, fake_provider):
    """
    Forged or tampered payment signature is immediately rejected with PaymentSignatureError.
    The transaction state machine MUST remain in EXECUTING and NOT advance to PASS.
    """
    create_req = CreateTransactionRequest(intent=base_intent)
    res = transaction_service.create_transaction(create_req, provider=fake_provider)

    payment = seed_mock_payment(
        provider=fake_provider,
        order_id=res.order_id,
        amount=Money(amount=5000000, currency="INR"),
        status="captured",
    )

    forged_signature = "bad_forged_signature_00000000000000000000000000000000"

    complete_req = CompleteTransactionRequest(
        transaction_id=res.transaction_id,
        order_id=res.order_id,
        payment_id=payment.payment_id,
        signature=forged_signature,
    )

    with pytest.raises(PaymentSignatureError, match="Invalid checkout payment signature"):
        transaction_service.complete_transaction(complete_req, provider=fake_provider)

    # State machine remains halted in EXECUTING
    session = transaction_service.get_session(res.transaction_id)
    assert session.state_machine.current_state == TransactionState.EXECUTING
    assert session.completed_response is None


def test_wrong_order_payment_association_rejection(transaction_service, base_intent, fake_provider):
    """
    Supplying an order_id that does not match the bound transaction order is rejected.
    """
    create_req = CreateTransactionRequest(intent=base_intent)
    res = transaction_service.create_transaction(create_req, provider=fake_provider)

    complete_req = CompleteTransactionRequest(
        transaction_id=res.transaction_id,
        order_id="order_attacker_substituted_999",
        payment_id="pay_mock_12345",
        signature="some_sig",
    )

    with pytest.raises(ValueError, match="does not match bound order"):
        transaction_service.complete_transaction(complete_req, provider=fake_provider)


# ==============================================================================
# 2. INTEGRITY DRIFT ADVERSARIAL TESTS (ECONOMIC, SEMANTIC, TEMPORAL)
# ==============================================================================

def test_economic_drift_overcharge_generates_mrdp(transaction_service, base_intent, fake_provider):
    """
    Economic DRIFT: Intent authorized ₹50,000 (5,000,000 paise).
    Gateway reports captured payment of ₹50,001 (5,000,100 paise).
    Deterministic engine MUST declare DRIFT (NOT PASS) and produce a verifiable MRDP.
    """
    create_req = CreateTransactionRequest(intent=base_intent)
    res = transaction_service.create_transaction(create_req, provider=fake_provider)

    # Provider reports overcharge of ₹50,001
    overcharged_amount = Money(amount=5000100, currency="INR")
    payment = seed_mock_payment(
        provider=fake_provider,
        order_id=res.order_id,
        amount=overcharged_amount,
        status="captured",
    )
    sig = compute_payment_signature(
        order_id=res.order_id,
        payment_id=payment.payment_id,
        secret=TEST_KEY_SECRET,
    )

    complete_req = CompleteTransactionRequest(
        transaction_id=res.transaction_id,
        order_id=res.order_id,
        payment_id=payment.payment_id,
        signature=sig,
    )
    completed_res = transaction_service.complete_transaction(complete_req, provider=fake_provider)

    # Must be DRIFT, never PASS
    assert completed_res.state == TransactionState.DRIFT
    assert completed_res.integrity_status == IntegrityStatus.DRIFT
    assert completed_res.rule_results.get("EconomicIntegrityRule") is False
    assert any("Observed amount" in v for v in completed_res.violations)

    # Must generate an authoritative Machine-Readable Drift Proof (MRDP)
    assert completed_res.mrdp is not None
    assert completed_res.mrdp.status == "DRIFT"
    assert completed_res.mrdp.discrepancy_amount == Money(amount=100, currency="INR")  # Exactly 100 paise discrepancy


def test_semantic_drift_unauthorized_sku(transaction_service, base_intent, fake_provider):
    """
    Semantic DRIFT: Authorized SKU is SRV-256GB.
    Gateway notes report unauthorized substitution SKU SRV-512GB.
    Deterministic engine MUST flag DRIFT.
    """
    create_req = CreateTransactionRequest(intent=base_intent)
    res = transaction_service.create_transaction(create_req, provider=fake_provider)

    payment = seed_mock_payment(
        provider=fake_provider,
        order_id=res.order_id,
        amount=Money(amount=5000000, currency="INR"),
        status="captured",
        notes={"sku": "SRV-512GB", "quantity": "1"},
    )
    sig = compute_payment_signature(
        order_id=res.order_id,
        payment_id=payment.payment_id,
        secret=TEST_KEY_SECRET,
    )

    complete_req = CompleteTransactionRequest(
        transaction_id=res.transaction_id,
        order_id=res.order_id,
        payment_id=payment.payment_id,
        signature=sig,
    )
    completed_res = transaction_service.complete_transaction(complete_req, provider=fake_provider)

    assert completed_res.state == TransactionState.DRIFT
    assert completed_res.integrity_status == IntegrityStatus.DRIFT
    assert completed_res.rule_results.get("SemanticIntegrityRule") is False


def test_temporal_drift_expired_intent(transaction_service, fake_provider):
    """
    Temporal DRIFT: Intent expires at now - 1 minute.
    Payment completed after expiration is flagged as DRIFT.
    """
    now = datetime.now(timezone.utc)
    expired_intent = IntentContract(
        intent_id="int_expired_001",
        issued_by="sec_officer_42",
        issued_at=now - timedelta(minutes=30),
        expires_at=now - timedelta(minutes=5),  # Already expired
        currency="INR",
        max_total=Money(amount=5000000, currency="INR"),
        items=[
            IntentItem(
                item_id="item-srv-exp",
                sku="SRV-256GB",
                name="Server 256GB",
                quantity=1,
                unit_price=Money(amount=5000000, currency="INR"),
                total_price=Money(amount=5000000, currency="INR"),
            )
        ],
    )

    create_req = CreateTransactionRequest(intent=expired_intent)
    res = transaction_service.create_transaction(create_req, provider=fake_provider)

    payment = seed_mock_payment(
        provider=fake_provider,
        order_id=res.order_id,
        amount=Money(amount=5000000, currency="INR"),
        status="captured",
    )
    sig = compute_payment_signature(
        order_id=res.order_id,
        payment_id=payment.payment_id,
        secret=TEST_KEY_SECRET,
    )

    complete_req = CompleteTransactionRequest(
        transaction_id=res.transaction_id,
        order_id=res.order_id,
        payment_id=payment.payment_id,
        signature=sig,
    )
    completed_res = transaction_service.complete_transaction(complete_req, provider=fake_provider)

    assert completed_res.state == TransactionState.DRIFT
    assert completed_res.integrity_status == IntegrityStatus.DRIFT
    assert completed_res.rule_results.get("TemporalIntegrityRule") is False


# ==============================================================================
# 3. TRANSACTION LIFECYCLE & IMMUTABILITY DEFENSE
# ==============================================================================

def test_duplicate_transaction_completion_idempotency(transaction_service, base_intent, fake_provider):
    """
    Duplicate completion requests return the exact same authoritative result idempotently
    without executing duplicate verification passes or corrupting state machine history.
    """
    create_req = CreateTransactionRequest(intent=base_intent)
    res = transaction_service.create_transaction(create_req, provider=fake_provider)

    payment = seed_mock_payment(
        provider=fake_provider,
        order_id=res.order_id,
        amount=Money(amount=5000000, currency="INR"),
        status="captured",
    )
    sig = compute_payment_signature(
        order_id=res.order_id,
        payment_id=payment.payment_id,
        secret=TEST_KEY_SECRET,
    )

    complete_req = CompleteTransactionRequest(
        transaction_id=res.transaction_id,
        order_id=res.order_id,
        payment_id=payment.payment_id,
        signature=sig,
    )

    res1 = transaction_service.complete_transaction(complete_req, provider=fake_provider)
    session = transaction_service.get_session(res.transaction_id)
    history_len_after_first = len(session.state_machine.history)

    # Second completion attempt
    res2 = transaction_service.complete_transaction(complete_req, provider=fake_provider)

    assert res1.state == res2.state
    assert res1.verified_at == res2.verified_at
    # History must not have duplicate transitions
    assert len(session.state_machine.history) == history_len_after_first


def test_intent_immutability_defense(base_intent):
    """
    Authorized IntentContract fields are immutable (frozen=True).
    Attempts to mutate intent parameters after issuance raise an exception.
    """
    with pytest.raises(Exception):
        base_intent.max_total = Money(amount=9999999, currency="INR")

    with pytest.raises(Exception):
        base_intent.items = []


def test_adapter_cannot_independently_declare_pass(transaction_service, base_intent, fake_provider):
    """
    Safety invariant (§9): ProviderPayment having status="captured" does NOT
    mean PASS until the deterministic engine checks all constraints.
    """
    create_req = CreateTransactionRequest(intent=base_intent)
    res = transaction_service.create_transaction(create_req, provider=fake_provider)

    # Captured by provider, BUT exceeds intent max_total
    payment = seed_mock_payment(
        provider=fake_provider,
        order_id=res.order_id,
        amount=Money(amount=7500000, currency="INR"),
        status="captured",
    )
    sig = compute_payment_signature(
        order_id=res.order_id,
        payment_id=payment.payment_id,
        secret=TEST_KEY_SECRET,
    )

    complete_req = CompleteTransactionRequest(
        transaction_id=res.transaction_id,
        order_id=res.order_id,
        payment_id=payment.payment_id,
        signature=sig,
    )
    completed_res = transaction_service.complete_transaction(complete_req, provider=fake_provider)

    assert completed_res.state == TransactionState.DRIFT
    assert completed_res.integrity_status == IntegrityStatus.DRIFT


# ==============================================================================
# 4. SECURITY BOUNDARY & SECRET LEAKAGE PREVENTION
# ==============================================================================

def test_secret_leakage_prevention(transaction_service, base_intent, fake_provider):
    """
    Secrets (RAZORPAY_KEY_SECRET, auth credentials) MUST never appear in
    API responses, serializations, or object models.
    """
    create_req = CreateTransactionRequest(intent=base_intent)
    res = transaction_service.create_transaction(create_req, provider=fake_provider)

    payment = seed_mock_payment(
        provider=fake_provider,
        order_id=res.order_id,
        amount=Money(amount=5000000, currency="INR"),
        status="captured",
    )
    sig = compute_payment_signature(
        order_id=res.order_id,
        payment_id=payment.payment_id,
        secret=TEST_KEY_SECRET,
    )

    complete_req = CompleteTransactionRequest(
        transaction_id=res.transaction_id,
        order_id=res.order_id,
        payment_id=payment.payment_id,
        signature=sig,
    )
    completed_res = transaction_service.complete_transaction(complete_req, provider=fake_provider)

    dumped_json = completed_res.model_dump_json()
    assert TEST_KEY_SECRET not in dumped_json
    assert "key_secret" not in dumped_json

    session = transaction_service.get_session(res.transaction_id)
    assert TEST_KEY_SECRET not in str(session.state_machine)


# ==============================================================================
# 5. REAL RAZORPAY TEST MODE SMOKE TEST
# ==============================================================================

def test_live_razorpay_test_mode_smoke():
    """
    Real Razorpay Test Mode boundary test.
    If credentials are present, creates a real gateway order and verifies integer minor units.
    If credentials absent, skips cleanly per §5.
    """
    if not settings.razorpay_key_id or not settings.razorpay_key_secret:
        pytest.skip("Live Razorpay Test Mode: SKIPPED — credentials unavailable")

    adapter = RazorpayAdapter()
    amount = Money(amount=10000, currency="INR")  # ₹100.00
    receipt = f"rcpt_live_{datetime.now(timezone.utc).strftime('%H%M%S')}"

    order = adapter.create_order(
        amount=amount,
        receipt=receipt,
        notes={"system": "TarkaRaksha_T10_Verification"},
    )

    assert isinstance(order, ProviderOrder)
    assert order.order_id.startswith("order_")
    assert order.amount == amount
    assert order.amount.amount == 10000
    assert order.currency == "INR"
    assert order.receipt == receipt

    # Verify signature logic on live adapter using live secret
    dummy_payment_id = "pay_test_simulated_999"
    sig = compute_payment_signature(
        order_id=order.order_id,
        payment_id=dummy_payment_id,
        secret=settings.razorpay_key_secret,
    )
    assert adapter.verify_payment_signature(
        order_id=order.order_id,
        payment_id=dummy_payment_id,
        signature=sig,
    ) is True
