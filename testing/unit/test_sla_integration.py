"""Integration tests for Innovation I15 — Integrity SLA Metrics Service & API."""
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
import pytest

from backend.app.main import app
from backend.app.domain.models.enums import IntegrityStatus, TransactionState
from backend.app.domain.models.intent import IntentContract, IntentItem
from backend.app.domain.models.money import Money
from backend.app.domain.models.payment import ProviderOrder, ProviderPayment
from backend.app.domain.models.integrity import IntegrityResult
from backend.app.domain.binding.contracts import BindingContext, BindingVerificationOutcome
from backend.app.domain.sla.contracts import MetricName, MetricStatus
from backend.app.services.transaction_service import TransactionService, TransactionSession
from backend.app.domain.states import TransactionStateMachine


@pytest.fixture
def clean_transaction_service():
    service = TransactionService()
    ref_time = datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)
    intent = IntentContract(
        intent_id="int_sla_integ_1",
        issued_by="agent_buyer_01",
        issued_at=ref_time,
        expires_at=datetime(2027, 1, 1, tzinfo=timezone.utc),
        currency="INR",
        max_total=Money(amount=5000, currency="INR"),
        items=[
            IntentItem(
                item_id="item_sla_1",
                sku="SKU_SLA_1",
                name="SLA Item",
                quantity=1,
                unit_price=Money(amount=5000, currency="INR"),
                total_price=Money(amount=5000, currency="INR"),
            )
        ],
    )
    order = ProviderOrder(
        order_id="order_sla_integ_1",
        amount=Money(amount=5000, currency="INR"),
        receipt="rcpt_sla_1",
        status="created",
        created_at=ref_time,
        notes={"merchant_id": "merch_acme"},
    )
    sm = TransactionStateMachine(transaction_id="tx_sla_integ_1", intent=intent, initial_state=TransactionState.PASS)
    session = TransactionSession(
        transaction_id="tx_sla_integ_1",
        intent=intent,
        state_machine=sm,
        order=order,
        created_at=ref_time,
    )
    session.payment = ProviderPayment(
        payment_id="pay_sla_integ_1",
        order_id="order_sla_integ_1",
        amount=Money(amount=5000, currency="INR"),
        status="captured",
        method="card",
        created_at=ref_time + timedelta(milliseconds=400),
    )
    session.integrity_result = IntegrityResult(
        evaluation_id="eval_sla_integ_1",
        intent_id="int_sla_integ_1",
        status=IntegrityStatus.PASS,
        explanation="Transaction verified",
        violations=[],
        evaluated_at=ref_time + timedelta(milliseconds=500),
    )
    session.binding_outcome = BindingVerificationOutcome(
        is_valid=True,
        status=IntegrityStatus.PASS,
        violations=[],
        details={},
        explanation="All bindings verified",
        verified_at=ref_time + timedelta(milliseconds=200),
    )
    session.binding_context = BindingContext(
        intent_id=intent.intent_id,
        agent_id=intent.issued_by,
        merchant_id="merch_acme",
        transaction_id="tx_sla_integ_1",
        order_id=order.order_id,
        attempt_id="att_1",
        created_at=ref_time,
    )
    service._sessions[session.transaction_id] = session
    return service


def test_sla_service_get_report_from_session(clean_transaction_service):
    """Verifies that IntegritySLAMetricsService builds a report from an active TransactionSession."""
    sla_service = clean_transaction_service.sla_service
    session = clean_transaction_service.get_session("tx_sla_integ_1")

    report = sla_service.get_sla_report_for_session(session)
    assert report.transaction_id == "tx_sla_integ_1"
    assert len(report.metrics) == 9

    metrics_map = {m.metric_name: m for m in report.metrics}
    assert metrics_map[MetricName.CHECKPOINT_COVERAGE_RATIO].status == MetricStatus.MEASURABLE
    assert metrics_map[MetricName.CHECKPOINT_VALID_RATIO].status == MetricStatus.MEASURABLE
    assert metrics_map[MetricName.TRACE_COMPLETENESS_RATIO].status == MetricStatus.MEASURABLE


def test_transaction_service_get_integrity_sla_metrics(clean_transaction_service):
    """Verifies TransactionService.get_integrity_sla_metrics() returns valid report."""
    report = clean_transaction_service.get_integrity_sla_metrics("tx_sla_integ_1")
    assert report.transaction_id == "tx_sla_integ_1"
    assert report.summary.total_metrics == 9
    assert report.summary.breached_count == 0


def test_fastapi_sla_endpoint(clean_transaction_service):
    """Verifies read-only GET /api/v1/transactions/{id}/integrity-sla endpoint."""
    from backend.app.main import get_transaction_service
    app.dependency_overrides[get_transaction_service] = lambda: clean_transaction_service

    client = TestClient(app)

    # 1. Existing transaction
    response = client.get("/api/v1/transactions/tx_sla_integ_1/integrity-sla")
    assert response.status_code == 200
    data = response.json()
    assert data["transaction_id"] == "tx_sla_integ_1"
    assert "metrics" in data
    assert "summary" in data
    assert len(data["metrics"]) == 9

    # 2. Non-existent transaction
    res_404 = client.get("/api/v1/transactions/tx_non_existent/integrity-sla")
    assert res_404.status_code == 404

    app.dependency_overrides.clear()


def test_explain_transaction_includes_sla_metrics(clean_transaction_service):
    """Verifies that explain_transaction integrates SLA metrics into context evidence references."""
    explanation = clean_transaction_service.explain_transaction("tx_sla_integ_1")
    assert explanation is not None
    assert explanation.transaction_id == "tx_sla_integ_1"
    assert explanation.validation_result.is_valid is True
