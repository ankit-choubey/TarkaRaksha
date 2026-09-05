"""
Unit & Integration Test Suite for T10: First Complete Real Transaction Slice.
Testing reference: brain/TarkaRaksha_TESTING.md (T10 Requirements).

Covers:
- Complete successful transaction slice: Intent -> Order -> Payment -> Verification -> PASS
- Intent-to-order binding and constraint preservation
- Server-side cryptographic signature verification
- Authoritative provider evidence construction (RAZORPAY, AUTHORITATIVE)
- Deterministic integrity engine verification authority (no AI in critical path)
- State machine lifecycle progression: CREATED -> EXECUTING -> OBSERVING -> VERIFYING -> PASS
- Bounded provider polling (immediate capture, delayed resolution, UNKNOWN fallback)
- FastAPI REST endpoint integration (create, complete, retrieve, mrdp)
"""
from datetime import datetime, timedelta, timezone
import hashlib
import pytest
from fastapi.testclient import TestClient

from backend.app.domain.models import (
    EvidenceAuthority,
    EvidenceSource,
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
    PaymentSignatureError,
    compute_payment_signature,
)
from backend.app.services.transaction_service import TransactionService


# ==============================================================================
# FIXTURES & HELPERS
# ==============================================================================

TEST_KEY_SECRET = "test_secret_key_t10_slice_12345"


def seed_mock_payment(
    provider: FakePaymentProvider,
    order_id: str,
    amount: Money,
    status: str = "captured",
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
def sample_intent():
    now = datetime.now(timezone.utc)
    return IntentContract(
        intent_id="int_test_slice_001",
        issued_by="auth_user_sec_ops",
        issued_at=now - timedelta(minutes=5),
        expires_at=now + timedelta(hours=1),
        currency="INR",
        max_total=Money(amount=5000000, currency="INR"),
        items=[
            IntentItem(
                item_id="item-srv-01",
                sku="SRV-256GB",
                name="Dell PowerEdge 256GB Node",
                quantity=1,
                unit_price=Money(amount=5000000, currency="INR"),
                total_price=Money(amount=5000000, currency="INR"),
            )
        ],
    )


# ==============================================================================
# 1. CORE SERVICE SLICE TESTS
# ==============================================================================

def test_complete_transaction_slice_happy_path(transaction_service, sample_intent, fake_provider):
    """
    Verifies the full end-to-end transaction slice:
    Authorized Intent -> Create Order -> Register Payment -> Complete -> Deterministic PASS.
    """
    # 1. Initialize transaction
    create_req = CreateTransactionRequest(intent=sample_intent)
    res = transaction_service.create_transaction(create_req, provider=fake_provider)
    assert res.state == TransactionState.EXECUTING
    assert res.order_id.startswith("order_mock_")
    assert res.intent_id == "int_test_slice_001"

    # 2. Simulate user completing payment on provider
    payment = seed_mock_payment(
        provider=fake_provider,
        order_id=res.order_id,
        amount=Money(amount=5000000, currency="INR"),
        status="captured",
    )

    # 3. Compute client signature matching provider credentials
    signature = compute_payment_signature(
        order_id=res.order_id,
        payment_id=payment.payment_id,
        secret=TEST_KEY_SECRET,
    )

    # 4. Server-side payment completion & verification
    complete_req = CompleteTransactionRequest(
        transaction_id=res.transaction_id,
        order_id=res.order_id,
        payment_id=payment.payment_id,
        signature=signature,
    )
    completed_res = transaction_service.complete_transaction(complete_req, provider=fake_provider)

    # 5. Assert authoritative deterministic PASS
    assert completed_res.state == TransactionState.PASS
    assert completed_res.integrity_status == "PASS"
    assert completed_res.violations == []

    # 6. Verify evidence bundle stored in session
    session = transaction_service.get_session(res.transaction_id)
    assert session is not None
    assert session.completed_response is not None
    assert session.payment is not None
    assert session.payment.payment_id == payment.payment_id
    assert session.integrity_result is not None
    assert session.integrity_result.status == "PASS"
    assert session.evidence_bundle is not None
    assert len(session.evidence_bundle.records) >= 1
    first_ev = session.evidence_bundle.records[0]
    assert first_ev.source == EvidenceSource.RAZORPAY
    assert first_ev.authority == EvidenceAuthority.AUTHORITATIVE


def test_intent_to_order_binding_preserves_constraints(transaction_service, sample_intent, fake_provider):
    """
    Verifies that intent constraints (amount, currency, items, authorization)
    are bound into the provider order and preserved immutably.
    """
    create_req = CreateTransactionRequest(intent=sample_intent)
    res = transaction_service.create_transaction(create_req, provider=fake_provider)

    session = transaction_service.get_session(res.transaction_id)
    assert session is not None

    # Intent is immutably stored
    assert session.intent.calculate_items_total() == Money(amount=5000000, currency="INR")
    assert session.intent.items[0].sku == "SRV-256GB"
    assert session.intent.items[0].quantity == 1

    # Provider order matches intent total
    provider_order = fake_provider.orders[res.order_id]
    assert provider_order.amount == sample_intent.max_total
    assert provider_order.currency == "INR"
    assert provider_order.receipt == "int_test_slice_001"
    assert provider_order.notes.get("intent_id") == "int_test_slice_001"
    assert provider_order.notes.get("sku") == "SRV-256GB"


def test_server_signature_verification_success(transaction_service, sample_intent, fake_provider):
    """
    Valid HMAC-SHA256 payment signature passes server verification seamlessly.
    """
    create_req = CreateTransactionRequest(intent=sample_intent)
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
    assert completed_res.state == TransactionState.PASS
    assert completed_res.integrity_status == "PASS"


def test_state_machine_lifecycle_progression(transaction_service, sample_intent, fake_provider):
    """
    Verifies that the transaction state machine strictly advances through:
    CREATED -> EXECUTING -> OBSERVING -> VERIFYING -> PASS.
    """
    create_req = CreateTransactionRequest(intent=sample_intent)
    res = transaction_service.create_transaction(create_req, provider=fake_provider)

    session = transaction_service.get_session(res.transaction_id)
    assert session.state_machine.current_state == TransactionState.EXECUTING

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
    assert completed_res.state == TransactionState.PASS

    history = [h.to_state for h in session.state_machine.history]
    assert history == [
        TransactionState.EXECUTING,
        TransactionState.OBSERVING,
        TransactionState.VERIFYING,
        TransactionState.PASS,
    ]


def test_polling_unresolved_payment_reaches_unknown_state(transaction_service, sample_intent, fake_provider):
    """
    When payment remains in pending/authorized status beyond max polling attempts,
    it must safely resolve to UNKNOWN rather than failing ungracefully or assuming PASS.
    """
    create_req = CreateTransactionRequest(intent=sample_intent)
    res = transaction_service.create_transaction(create_req, provider=fake_provider)

    unresolved_pay_id = "pay_mock_unresolved_123"
    sig = compute_payment_signature(
        order_id=res.order_id,
        payment_id=unresolved_pay_id,
        secret=TEST_KEY_SECRET,
    )

    # Complete transaction with unrecorded payment -> bounded polling exhausts and returns UNKNOWN
    complete_req = CompleteTransactionRequest(
        transaction_id=res.transaction_id,
        order_id=res.order_id,
        payment_id=unresolved_pay_id,
        signature=sig,
    )
    completed_res = transaction_service.complete_transaction(
        complete_req,
        provider=fake_provider,
        poll_delay_seconds=0.0,
    )

    assert completed_res.state == TransactionState.UNKNOWN
    assert completed_res.integrity_status == "UNKNOWN"
    assert completed_res.mrdp is not None
    assert completed_res.mrdp.status == "UNKNOWN"


# ==============================================================================
# 2. FASTAPI API ENDPOINT INTEGRATION TESTS
# ==============================================================================

@pytest.fixture
def test_client(fake_provider, transaction_service):
    app.dependency_overrides[get_payment_provider] = lambda: fake_provider
    app.dependency_overrides[get_transaction_service] = lambda: transaction_service
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def test_api_create_and_complete_transaction(test_client, fake_provider):
    """
    Verifies full transaction creation and completion via FastAPI REST endpoints.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "intent": {
            "intent_id": "int_api_001",
            "issued_by": "api_tester",
            "issued_at": now.isoformat(),
            "expires_at": (now + timedelta(hours=2)).isoformat(),
            "currency": "INR",
            "max_total": {"amount": 250000, "currency": "INR"},
            "items": [
                {
                    "item_id": "item-api-01",
                    "sku": "ITEM-101",
                    "name": "Cloud Storage 1TB",
                    "quantity": 1,
                    "unit_price": {"amount": 250000, "currency": "INR"},
                    "total_price": {"amount": 250000, "currency": "INR"},
                }
            ],
        }
    }

    create_res = test_client.post("/api/v1/transaction/create", json=payload)
    assert create_res.status_code == 200, f"Response: {create_res.text}"
    create_data = create_res.json()
    assert create_data["transaction_id"].startswith("tx_")
    assert create_data["order_id"].startswith("order_mock_")
    assert create_data["state"] == "EXECUTING"
    assert create_data["amount"]["amount"] == 250000
    assert create_data["currency"] == "INR"

    tx_id = create_data["transaction_id"]
    order_id = create_data["order_id"]

    # 2. Simulate payment completion on provider
    payment = seed_mock_payment(
        provider=fake_provider,
        order_id=order_id,
        amount=Money(amount=250000, currency="INR"),
        status="captured",
    )
    signature = compute_payment_signature(
        order_id=order_id,
        payment_id=payment.payment_id,
        secret=TEST_KEY_SECRET,
    )

    # 3. Complete transaction via POST /api/v1/transaction/complete
    complete_payload = {
        "transaction_id": tx_id,
        "order_id": order_id,
        "payment_id": payment.payment_id,
        "signature": signature,
    }
    complete_res = test_client.post("/api/v1/transaction/complete", json=complete_payload)
    assert complete_res.status_code == 200
    complete_data = complete_res.json()
    assert complete_data["state"] == "PASS"
    assert complete_data["integrity_status"] == "PASS"

    # 4. Fetch transaction record via GET /api/v1/transaction/{id}
    get_res = test_client.get(f"/api/v1/transaction/{tx_id}")
    assert get_res.status_code == 200
    get_data = get_res.json()
    assert get_data["transaction_id"] == tx_id
    assert get_data["state"] == "PASS"


def test_api_get_mrdp_for_clean_pass_returns_404(test_client, fake_provider):
    """
    Clean PASS transactions do not have drift, so /mrdp returns 404 Not Found.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "intent": {
            "intent_id": "int_api_mrdp_clean",
            "issued_by": "tester",
            "issued_at": now.isoformat(),
            "expires_at": (now + timedelta(hours=1)).isoformat(),
            "currency": "INR",
            "max_total": {"amount": 100000, "currency": "INR"},
            "items": [
                {
                    "item_id": "item-clean-01",
                    "sku": "SKU-CLEAN",
                    "name": "Clean Product",
                    "quantity": 1,
                    "unit_price": {"amount": 100000, "currency": "INR"},
                    "total_price": {"amount": 100000, "currency": "INR"},
                }
            ],
        }
    }
    create_res = test_client.post("/api/v1/transaction/create", json=payload)
    tx_id = create_res.json()["transaction_id"]
    order_id = create_res.json()["order_id"]

    payment = seed_mock_payment(
        provider=fake_provider,
        order_id=order_id,
        amount=Money(amount=100000, currency="INR"),
        status="captured",
    )
    sig = compute_payment_signature(
        order_id=order_id,
        payment_id=payment.payment_id,
        secret=TEST_KEY_SECRET,
    )
    test_client.post(
        "/api/v1/transaction/complete",
        json={
            "transaction_id": tx_id,
            "order_id": order_id,
            "payment_id": payment.payment_id,
            "signature": sig,
        },
    )

    mrdp_res = test_client.get(f"/api/v1/transaction/{tx_id}/mrdp")
    assert mrdp_res.status_code == 404
    assert "No MRDP generated for PASS transaction" in mrdp_res.json()["detail"]
