"""Integration tests for Innovation I14 — Integrity Checkpoint Service & API."""
from datetime import datetime, timezone
from fastapi.testclient import TestClient
import pytest

from backend.app.main import app
from backend.app.domain.models.enums import IntegrityStatus, TransactionState
from backend.app.domain.models.intent import IntentContract
from backend.app.domain.models.money import Money
from backend.app.domain.models.payment import ProviderOrder, ProviderPayment
from backend.app.domain.models.integrity import IntegrityResult
from backend.app.domain.binding.contracts import BindingContext, BindingVerificationOutcome
from backend.app.domain.kill_switch.contracts import KillSwitchState
from backend.app.domain.checkpoint.contracts import (
    CheckpointType,
    CheckpointStatus,
    IntegrityCheckpointTimeline,
)
from backend.app.services.transaction_service import TransactionService, TransactionSession
from backend.app.services.checkpoint.service import IntegrityCheckpointService
from backend.app.domain.states import TransactionStateMachine


from backend.app.domain.models.intent import IntentContract, IntentItem

@pytest.fixture
def clean_transaction_service():
    service = TransactionService()
    ref_time = datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)
    intent = IntentContract(
        intent_id="int_chk_integ_1",
        issued_by="agent_buyer_01",
        issued_at=ref_time,
        expires_at=datetime(2027, 1, 1, tzinfo=timezone.utc),
        currency="INR",
        max_total=Money(amount=5000, currency="INR"),
        items=[
            IntentItem(
                item_id="item_chk_1",
                sku="SKU_CHK_1",
                name="Check Item",
                quantity=1,
                unit_price=Money(amount=5000, currency="INR"),
                total_price=Money(amount=5000, currency="INR"),
            )
        ],
    )
    order = ProviderOrder(
        order_id="order_chk_integ_1",
        amount=Money(amount=5000, currency="INR"),
        receipt="rcpt_1",
        status="created",
        created_at=ref_time,
        notes={"merchant_id": "merch_acme"},
    )
    sm = TransactionStateMachine(transaction_id="tx_chk_integ_1", intent=intent, initial_state=TransactionState.PASS)
    session = TransactionSession(
        transaction_id="tx_chk_integ_1",
        intent=intent,
        state_machine=sm,
        order=order,
        created_at=ref_time,
    )
    session.payment = ProviderPayment(
        payment_id="pay_chk_integ_1",
        order_id="order_chk_integ_1",
        amount=Money(amount=5000, currency="INR"),
        status="captured",
        method="card",
        created_at=ref_time,
    )
    session.integrity_result = IntegrityResult(
        evaluation_id="eval_chk_integ_1",
        intent_id="int_chk_integ_1",
        status=IntegrityStatus.PASS,
        explanation="Transaction verified",
        violations=[],
        evaluated_at=ref_time,
    )
    session.binding_outcome = BindingVerificationOutcome(
        is_valid=True,
        status=IntegrityStatus.PASS,
        violations=[],
        details={},
        explanation="All bindings verified",
        verified_at=ref_time,
    )
    session.binding_context = BindingContext(
        intent_id=intent.intent_id,
        agent_id=intent.issued_by,
        merchant_id="merch_acme",
        transaction_id="tx_chk_integ_1",
        order_id=order.order_id,
        attempt_id="att_1",
        created_at=ref_time,
    )
    service._sessions[session.transaction_id] = session
    return service


def test_checkpoint_service_build_timeline_from_session(clean_transaction_service):
    """Verifies that IntegrityCheckpointService builds a complete timeline from a TransactionSession."""
    chk_service = clean_transaction_service.checkpoint_service
    session = clean_transaction_service.get_session("tx_chk_integ_1")

    timeline = chk_service.build_timeline_from_session(session)
    assert timeline.transaction_id == "tx_chk_integ_1"
    assert len(timeline.checkpoints) == 8
    assert timeline.chain_verification.is_valid is True
    assert timeline.last_valid_checkpoint is not None
    assert timeline.first_invalid_checkpoint is None


def test_transaction_service_get_integrity_checkpoints(clean_transaction_service):
    """Verifies TransactionService.get_integrity_checkpoints() returns valid timeline."""
    timeline = clean_transaction_service.get_integrity_checkpoints("tx_chk_integ_1")
    assert timeline.transaction_id == "tx_chk_integ_1"
    assert timeline.chain_verification.is_valid is True
    assert timeline.last_valid_checkpoint.sequence == 8


def test_fastapi_checkpoint_endpoint(clean_transaction_service):
    """Verifies read-only GET /api/v1/transactions/{id}/integrity-checkpoints endpoint."""
    from backend.app.main import get_transaction_service
    app.dependency_overrides[get_transaction_service] = lambda: clean_transaction_service

    client = TestClient(app)

    # 1. Existing transaction
    response = client.get("/api/v1/transactions/tx_chk_integ_1/integrity-checkpoints")
    assert response.status_code == 200
    data = response.json()
    assert data["transaction_id"] == "tx_chk_integ_1"
    assert len(data["checkpoints"]) == 8
    assert data["chain_verification"]["is_valid"] is True
    assert data["last_valid_checkpoint"]["checkpoint_type"] == "COMPLETION_VERIFIED"
    assert data["first_invalid_checkpoint"] is None

    # 2. Non-existent transaction
    res_404 = client.get("/api/v1/transactions/tx_non_existent/integrity-checkpoints")
    assert res_404.status_code == 404

    app.dependency_overrides.clear()


def test_explain_transaction_includes_checkpoints(clean_transaction_service):
    """Verifies that explain_transaction integrates checkpoint references."""
    explanation = clean_transaction_service.explain_transaction("tx_chk_integ_1")
    assert explanation is not None
    assert explanation.transaction_id == "tx_chk_integ_1"
    assert explanation.validation_result.is_valid is True
