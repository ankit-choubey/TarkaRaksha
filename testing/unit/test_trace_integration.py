"""Integration tests for Innovation I13 — Integrity Trace / Fault Localization.

Verifies:
1. Integration with TransactionService.get_integrity_trace().
2. FastAPI HTTP API endpoint GET /api/v1/transactions/{transaction_id}/integrity-trace.
3. Replay audit reproducibility (identical trace output on fixed input).
4. Seamless compatibility with Innovation I21 (Evidence-Aware AI Explanation).
"""
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.domain.models.money import Money
from backend.app.domain.models.intent import IntentContract, IntentItem
from backend.app.domain.models.slice import (
    CreateTransactionRequest,
    CompleteTransactionRequest,
)
from backend.app.domain.models.enums import IntegrityStatus
from backend.app.domain.trace.contracts import (
    IntegrityTrace,
    LifecycleStage,
    StageIntegrityStatus,
)
from backend.app.services.payment.fake_provider import FakePaymentProvider
from backend.app.services.transaction_service import TransactionService


@pytest.fixture
def fake_provider():
    return FakePaymentProvider()


@pytest.fixture
def transaction_service(fake_provider):
    return TransactionService(default_provider=fake_provider)


@pytest.fixture
def valid_intent():
    now = datetime.now(timezone.utc)
    return IntentContract(
        intent_id="int_intg_001",
        issued_by="agent_buyer_test",
        issued_at=now,
        expires_at=now + timedelta(minutes=30),
        currency="INR",
        max_total=Money(amount=10000, currency="INR"),
        items=[
            IntentItem(
                item_id="item_001",
                sku="SKU-PROD-1",
                name="Wireless Headphones",
                quantity=1,
                unit_price=Money(amount=10000, currency="INR"),
                total_price=Money(amount=10000, currency="INR"),
            )
        ],
    )


def test_transaction_service_get_integrity_trace_created_stage(transaction_service, valid_intent):
    # Create transaction
    create_req = CreateTransactionRequest(intent=valid_intent)
    create_resp = transaction_service.create_transaction(create_req)
    tx_id = create_resp.transaction_id

    # Retrieve integrity trace right after creation
    trace = transaction_service.get_integrity_trace(tx_id)

    assert isinstance(trace, IntegrityTrace)
    assert trace.transaction_id == tx_id
    assert trace.deterministic_decision == IntegrityStatus.PASS
    assert len(trace.steps) == 8

    # Intent stage should be valid
    assert trace.steps[0].stage == LifecycleStage.INTENT
    assert trace.steps[0].status == StageIntegrityStatus.CONFIRMED_VALID

    # Order stage should be valid
    assert trace.steps[3].stage == LifecycleStage.ORDER
    assert trace.steps[3].status == StageIntegrityStatus.CONFIRMED_VALID

    # Attempt stage is validly bound for checkout
    assert trace.steps[4].stage == LifecycleStage.ATTEMPT
    assert trace.steps[4].status == StageIntegrityStatus.CONFIRMED_VALID

    # Payment stage unreached before checkout execution
    assert trace.steps[5].stage == LifecycleStage.PAYMENT
    assert trace.steps[5].status == StageIntegrityStatus.UNREACHED
    assert trace.first_divergence is None


def test_fastapi_trace_endpoint_flow(valid_intent):
    client = TestClient(app)

    # 1. Unknown transaction returns 404
    resp_404 = client.get("/api/v1/transactions/tx_nonexistent/integrity-trace")
    assert resp_404.status_code == 404

    # 2. Create a live transaction via API
    create_payload = {
        "intent": valid_intent.model_dump(mode="json")
    }
    create_resp = client.post("/api/v1/transaction/create", json=create_payload)
    assert create_resp.status_code == 200
    tx_id = create_resp.json()["transaction_id"]

    # 3. Retrieve trace via API endpoint
    trace_resp = client.get(f"/api/v1/transactions/{tx_id}/integrity-trace")
    assert trace_resp.status_code == 200
    trace_data = trace_resp.json()

    assert trace_data["transaction_id"] == tx_id
    assert "deterministic_decision" in trace_data
    assert "context_bindings" in trace_data
    assert len(trace_data["steps"]) == 8
    assert trace_data["steps"][0]["stage"] == "INTENT"


def test_replay_trace_reproducibility(transaction_service, valid_intent):
    """Verifies identical deterministic trace output across repeated invocations."""
    create_req = CreateTransactionRequest(intent=valid_intent)
    create_resp = transaction_service.create_transaction(create_req)
    tx_id = create_resp.transaction_id

    now = datetime.now(timezone.utc)
    trace_run_1 = transaction_service.get_integrity_trace(tx_id, reference_time=now)
    trace_run_2 = transaction_service.get_integrity_trace(tx_id, reference_time=now)

    # All stages, findings, and statuses must match exactly
    assert trace_run_1.deterministic_decision == trace_run_2.deterministic_decision
    assert trace_run_1.first_divergence == trace_run_2.first_divergence
    assert len(trace_run_1.steps) == len(trace_run_2.steps)
    for s1, s2 in zip(trace_run_1.steps, trace_run_2.steps):
        assert s1.stage == s2.stage
        assert s1.status == s2.status
        assert s1.findings == s2.findings


def test_i21_explanation_integration_with_trace(transaction_service, valid_intent):
    """Verifies that calling explain_transaction incorporates integrity trace seamlessly."""
    create_req = CreateTransactionRequest(intent=valid_intent)
    create_resp = transaction_service.create_transaction(create_req)
    tx_id = create_resp.transaction_id

    # explain_transaction invokes ExplanationContextBuilder with integrity_trace
    explanation = transaction_service.explain_transaction(tx_id)
    assert explanation is not None
    assert explanation.transaction_id == tx_id
    assert explanation.summary is not None
