"""Integration tests for I21 Evidence-Aware AI Explanation with TransactionService and API."""
from datetime import datetime, timezone, timedelta
import json
import pytest
from fastapi.testclient import TestClient

from backend.app.domain.explanation import ExplanationResult
from backend.app.domain.kill_switch import KillSwitchState
from backend.app.domain.models import (
    CompleteTransactionRequest,
    CreateTransactionRequest,
    IntegrityStatus,
    IntentContract,
    IntentItem,
    Money,
    TransactionState,
)
from backend.app.domain.models.payment import ProviderPayment
from backend.app.main import app, get_transaction_service
from backend.app.services.ai.provider import FakeAIProvider
from backend.app.services.payment import FakePaymentProvider, compute_payment_signature
from backend.app.services.transaction_service import TransactionService

TEST_KEY_SECRET = "test_secret_key_exp_integ_12345"


def seed_mock_payment(
    provider: FakePaymentProvider,
    order_id: str,
    amount: Money,
    status: str = "captured",
    created_at: datetime = None,
) -> ProviderPayment:
    payment_id = f"pay_exp_{order_id}_{amount.amount}"
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
def sample_intent(now):
    return IntentContract(
        intent_id="intent_exp_integ_1",
        issued_by="buyer_agent_alpha",
        max_total=Money(amount=100000, currency="INR"),
        currency="INR",
        items=[
            IntentItem(
                item_id="item_exp_1",
                sku="SKU-EXP-1",
                name="Integration Test Item",
                quantity=1,
                unit_price=Money(amount=100000, currency="INR"),
                total_price=Money(amount=100000, currency="INR"),
            )
        ],
        issued_at=now,
        expires_at=now + timedelta(minutes=15),
    )


def test_explain_transaction_end_to_end_pass(sample_intent, now):
    provider = FakePaymentProvider(mock_secret=TEST_KEY_SECRET)
    tx_service = TransactionService(default_provider=provider)

    # 1. Create transaction
    create_req = CreateTransactionRequest(intent=sample_intent)
    create_res = tx_service.create_transaction(create_req, now=now)
    tx_id = create_res.transaction_id
    order_id = create_res.order_id

    # 2. Seed payment matching authorized amount exactly (100000 paise)
    payment = seed_mock_payment(
        provider,
        order_id=order_id,
        amount=Money(amount=100000, currency="INR"),
        created_at=now + timedelta(seconds=1),
    )

    # 3. Complete transaction
    sig = compute_payment_signature(
        order_id=order_id,
        payment_id=payment.payment_id,
        secret=TEST_KEY_SECRET,
    )
    comp_req = CompleteTransactionRequest(
        transaction_id=tx_id,
        order_id=order_id,
        payment_id=payment.payment_id,
        signature=sig,
    )
    comp_res = tx_service.complete_transaction(comp_req, now=now + timedelta(seconds=2))
    assert comp_res.state == TransactionState.PASS

    # 4. Explain transaction via TransactionService
    explanation = tx_service.explain_transaction(tx_id)
    assert isinstance(explanation, ExplanationResult)
    assert explanation.deterministic_decision == IntegrityStatus.PASS
    assert explanation.execution_state == KillSwitchState.RUNNING
    assert "pass" in explanation.summary.lower()
    assert len(explanation.claims) >= 1
    assert explanation.validation_result.is_valid is True


def test_explain_transaction_end_to_end_drift(sample_intent, now):
    provider = FakePaymentProvider(mock_secret=TEST_KEY_SECRET)
    tx_service = TransactionService(default_provider=provider)

    # 1. Create transaction
    create_req = CreateTransactionRequest(intent=sample_intent)
    create_res = tx_service.create_transaction(create_req, now=now)
    tx_id = create_res.transaction_id
    order_id = create_res.order_id

    # 2. Seed payment exceeding authorized amount (150000 > 100000 paise)
    payment = seed_mock_payment(
        provider,
        order_id=order_id,
        amount=Money(amount=150000, currency="INR"),
        created_at=now + timedelta(seconds=1),
    )

    # 3. Complete transaction -> DRIFT
    sig = compute_payment_signature(
        order_id=order_id,
        payment_id=payment.payment_id,
        secret=TEST_KEY_SECRET,
    )
    comp_req = CompleteTransactionRequest(
        transaction_id=tx_id,
        order_id=order_id,
        payment_id=payment.payment_id,
        signature=sig,
    )
    comp_res = tx_service.complete_transaction(comp_req, now=now + timedelta(seconds=2))
    assert comp_res.state == TransactionState.DRIFT

    # 4. Explain transaction
    explanation = tx_service.explain_transaction(tx_id)
    assert explanation.deterministic_decision == IntegrityStatus.DRIFT
    assert explanation.execution_state == KillSwitchState.KILLED
    assert "drift" in explanation.summary.lower() or "diverged" in explanation.summary.lower()
    assert len(explanation.recommended_next_action) > 0
    assert any(term in explanation.recommended_next_action.lower() for term in ["revalidation", "remediation", "refund", "investigate", "kill switch", "action", "review"])


def test_api_get_transaction_explanation(sample_intent, now):
    provider = FakePaymentProvider(mock_secret=TEST_KEY_SECRET)
    tx_service = TransactionService(default_provider=provider)

    # Create transaction
    create_req = CreateTransactionRequest(intent=sample_intent)
    create_res = tx_service.create_transaction(create_req, now=now)
    tx_id = create_res.transaction_id

    # Override dependency in FastAPI app
    app.dependency_overrides[get_transaction_service] = lambda: tx_service
    client = TestClient(app)

    try:
        # Call GET /api/v1/transactions/{id}/explanation
        resp = client.get(f"/api/v1/transactions/{tx_id}/explanation")
        assert resp.status_code == 200
        data = resp.json()
        assert data["transaction_id"] == tx_id
        assert data["deterministic_decision"] in ["PASS", "UNKNOWN", "DRIFT"]
        assert "summary" in data
        assert "claims" in data

        # Non-existent transaction returns 404
        bad_resp = client.get("/api/v1/transactions/tx_non_existent/explanation")
        assert bad_resp.status_code == 404
    finally:
        app.dependency_overrides.clear()
