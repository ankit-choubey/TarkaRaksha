"""Unit tests for I8 Transaction Binding domain contracts."""
from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from backend.app.domain.binding.contracts import (
    AttemptRecord,
    AttemptStatus,
    BindingContext,
    BindingStatus,
    BindingVerificationOutcome,
    BindingViolationCode,
    PaymentBindingClaim,
)
from backend.app.domain.models.enums import IntegrityStatus


def test_binding_context_creation_and_immutability():
    """Verify BindingContext validates fields and is frozen."""
    now = datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc)
    ctx = BindingContext(
        intent_id="intent_123",
        agent_id="agent_buyer_1",
        merchant_id="merchant_456",
        transaction_id="tx_789",
        order_id="order_abc",
        attempt_id="att_1",
        created_at=now,
    )
    assert ctx.intent_id == "intent_123"
    assert ctx.agent_id == "agent_buyer_1"
    assert ctx.merchant_id == "merchant_456"
    assert ctx.transaction_id == "tx_789"
    assert ctx.order_id == "order_abc"
    assert ctx.attempt_id == "att_1"
    assert ctx.created_at == now

    with pytest.raises(ValidationError):
        ctx.agent_id = "agent_tampered"  # type: ignore


def test_binding_context_rejects_empty_identifiers():
    """Verify BindingContext rejects empty strings or whitespace."""
    now = datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc)
    with pytest.raises(ValidationError):
        BindingContext(
            intent_id="",
            agent_id="agent_buyer_1",
            merchant_id="merchant_456",
            transaction_id="tx_789",
            order_id="order_abc",
            created_at=now,
        )


def test_binding_context_rejects_naive_datetime():
    """Verify BindingContext strictly enforces timezone-aware datetime."""
    naive = datetime(2026, 9, 5, 12, 0)
    with pytest.raises(ValidationError):
        BindingContext(
            intent_id="intent_123",
            agent_id="agent_buyer_1",
            merchant_id="merchant_456",
            transaction_id="tx_789",
            order_id="order_abc",
            created_at=naive,
        )


def test_payment_binding_claim_validation():
    """Verify PaymentBindingClaim requires all identifiers and disallows extra fields."""
    claim = PaymentBindingClaim(
        intent_id="intent_123",
        agent_id="agent_buyer_1",
        merchant_id="merchant_456",
        transaction_id="tx_789",
        order_id="order_abc",
        payment_id="pay_xyz",
        attempt_id="att_1",
    )
    assert claim.payment_id == "pay_xyz"

    # Disallow extra fields
    with pytest.raises(ValidationError):
        PaymentBindingClaim(
            intent_id="intent_123",
            agent_id="agent_buyer_1",
            merchant_id="merchant_456",
            transaction_id="tx_789",
            order_id="order_abc",
            payment_id="pay_xyz",
            attempt_id="att_1",
            malicious_override=True,  # type: ignore
        )


def test_attempt_record_immutability():
    """Verify AttemptRecord creation and freeze."""
    now = datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc)
    rec = AttemptRecord(
        attempt_id="att_1",
        transaction_id="tx_789",
        agent_id="agent_buyer_1",
        merchant_id="merchant_456",
        status=AttemptStatus.INITIATED,
        initiated_at=now,
    )
    assert rec.status == AttemptStatus.INITIATED
    with pytest.raises(ValidationError):
        rec.status = AttemptStatus.CONSUMED  # type: ignore


def test_binding_verification_outcome_to_evidence():
    """Verify BindingVerificationOutcome converts into canonical Evidence."""
    now = datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc)
    outcome = BindingVerificationOutcome(
        is_valid=False,
        status=IntegrityStatus.DRIFT,
        violations=[BindingViolationCode.ORDER_MISMATCH],
        details={"order_id": "Mismatch"},
        explanation="Order binding mismatch detected",
        verified_at=now,
    )
    evidence = outcome.to_evidence(intent_id="intent_123", transaction_id="tx_789")
    assert evidence.intent_id == "intent_123"
    assert evidence.transaction_id == "tx_789"
    assert evidence.source.value == "SYSTEM"
    assert evidence.effective_authority.value == "SYSTEM_DERIVED"
    assert evidence.field_name == "transaction_binding"
    assert evidence.field_value["is_valid"] is False
    assert evidence.field_value["status"] == "DRIFT"
    assert "ORDER_MISMATCH" in evidence.field_value["violations"]
    assert evidence.observed_at == now
