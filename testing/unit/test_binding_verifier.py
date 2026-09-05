"""Unit tests for I8 TransactionBindingVerifier.

Comprehensive adversarial, retry, cross-transaction, and negative tests.
"""
from datetime import datetime, timezone, timedelta
import pytest

from backend.app.domain.binding.contracts import (
    BindingContext,
    BindingStatus,
    BindingVerificationOutcome,
    BindingViolationCode,
    PaymentBindingClaim,
)
from backend.app.domain.binding.verifier import TransactionBindingVerifier
from backend.app.domain.models.enums import IntegrityStatus
from backend.app.domain.models.money import Money
from backend.app.domain.models.payment import ProviderPayment


@pytest.fixture
def now():
    return datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def binding_context(now):
    return BindingContext(
        intent_id="intent_001",
        agent_id="agent_001",
        merchant_id="merchant_001",
        transaction_id="tx_001",
        order_id="order_001",
        attempt_id="att_1",
        created_at=now,
    )


@pytest.fixture
def valid_claim():
    return PaymentBindingClaim(
        intent_id="intent_001",
        agent_id="agent_001",
        merchant_id="merchant_001",
        transaction_id="tx_001",
        order_id="order_001",
        payment_id="pay_001",
        attempt_id="att_1",
    )


@pytest.fixture
def valid_payment(now):
    return ProviderPayment(
        payment_id="pay_001",
        order_id="order_001",
        amount=Money(amount=50000, currency="INR"),
        status="captured",
        captured=True,
        method="card",
        created_at=now,
    )


# 1. Positive baseline test
def test_valid_binding_passes(binding_context, valid_claim, valid_payment, now):
    outcome = TransactionBindingVerifier.verify(
        claim=valid_claim,
        authoritative_context=binding_context,
        authoritative_payment=valid_payment,
        reference_time=now,
    )
    assert outcome.is_valid is True
    assert outcome.status == IntegrityStatus.PASS
    assert len(outcome.violations) == 0


# 2. Retries allowed with distinct unconsumed attempt_id
def test_valid_retry_attempt_passes(binding_context, valid_payment, now):
    retry_claim = PaymentBindingClaim(
        intent_id="intent_001",
        agent_id="agent_001",
        merchant_id="merchant_001",
        transaction_id="tx_001",
        order_id="order_001",
        payment_id="pay_001",
        attempt_id="att_2",
    )
    outcome = TransactionBindingVerifier.verify(
        claim=retry_claim,
        authoritative_context=binding_context,
        authoritative_payment=valid_payment,
        consumed_attempt_ids={"att_1"},
        reference_time=now,
    )
    assert outcome.is_valid is True
    assert outcome.status == IntegrityStatus.PASS


# 3. Consumed attempt reuse rejected (Replay attack defense)
def test_consumed_attempt_reuse_rejected(binding_context, valid_claim, valid_payment, now):
    outcome = TransactionBindingVerifier.verify(
        claim=valid_claim,
        authoritative_context=binding_context,
        authoritative_payment=valid_payment,
        consumed_attempt_ids={"att_1"},  # att_1 already consumed
        reference_time=now,
    )
    assert outcome.is_valid is False
    assert outcome.status == IntegrityStatus.DRIFT
    assert BindingViolationCode.DUPLICATE_ATTEMPT_REUSED in outcome.violations


# 4. Wrong intent ID rejected
def test_wrong_intent_rejected(binding_context, valid_payment, now):
    claim = PaymentBindingClaim(
        intent_id="intent_attacker_tampered",
        agent_id="agent_001",
        merchant_id="merchant_001",
        transaction_id="tx_001",
        order_id="order_001",
        payment_id="pay_001",
        attempt_id="att_1",
    )
    outcome = TransactionBindingVerifier.verify(
        claim=claim,
        authoritative_context=binding_context,
        authoritative_payment=valid_payment,
        reference_time=now,
    )
    assert outcome.is_valid is False
    assert outcome.status == IntegrityStatus.DRIFT
    assert BindingViolationCode.INTENT_MISMATCH in outcome.violations


# 5. Wrong agent ID rejected
def test_wrong_agent_rejected(binding_context, valid_payment, now):
    claim = PaymentBindingClaim(
        intent_id="intent_001",
        agent_id="rogue_agent_999",
        merchant_id="merchant_001",
        transaction_id="tx_001",
        order_id="order_001",
        payment_id="pay_001",
        attempt_id="att_1",
    )
    outcome = TransactionBindingVerifier.verify(
        claim=claim,
        authoritative_context=binding_context,
        authoritative_payment=valid_payment,
        reference_time=now,
    )
    assert outcome.is_valid is False
    assert outcome.status == IntegrityStatus.DRIFT
    assert BindingViolationCode.AGENT_MISMATCH in outcome.violations


# 6. Wrong merchant ID rejected
def test_wrong_merchant_rejected(binding_context, valid_payment, now):
    claim = PaymentBindingClaim(
        intent_id="intent_001",
        agent_id="agent_001",
        merchant_id="merchant_attacker_account",
        transaction_id="tx_001",
        order_id="order_001",
        payment_id="pay_001",
        attempt_id="att_1",
    )
    outcome = TransactionBindingVerifier.verify(
        claim=claim,
        authoritative_context=binding_context,
        authoritative_payment=valid_payment,
        reference_time=now,
    )
    assert outcome.is_valid is False
    assert outcome.status == IntegrityStatus.DRIFT
    assert BindingViolationCode.MERCHANT_MISMATCH in outcome.violations


# 7. Wrong transaction ID rejected
def test_wrong_transaction_rejected(binding_context, valid_payment, now):
    claim = PaymentBindingClaim(
        intent_id="intent_001",
        agent_id="agent_001",
        merchant_id="merchant_001",
        transaction_id="tx_attacker_substituted",
        order_id="order_001",
        payment_id="pay_001",
        attempt_id="att_1",
    )
    outcome = TransactionBindingVerifier.verify(
        claim=claim,
        authoritative_context=binding_context,
        authoritative_payment=valid_payment,
        reference_time=now,
    )
    assert outcome.is_valid is False
    assert outcome.status == IntegrityStatus.DRIFT
    assert BindingViolationCode.TRANSACTION_MISMATCH in outcome.violations


# 8. Wrong order ID rejected
def test_wrong_order_rejected(binding_context, valid_payment, now):
    claim = PaymentBindingClaim(
        intent_id="intent_001",
        agent_id="agent_001",
        merchant_id="merchant_001",
        transaction_id="tx_001",
        order_id="order_attacker_replaced",
        payment_id="pay_001",
        attempt_id="att_1",
    )
    outcome = TransactionBindingVerifier.verify(
        claim=claim,
        authoritative_context=binding_context,
        authoritative_payment=valid_payment,
        reference_time=now,
    )
    assert outcome.is_valid is False
    assert outcome.status == IntegrityStatus.DRIFT
    assert BindingViolationCode.ORDER_MISMATCH in outcome.violations


# 9. Provider payment ID mismatch rejected
def test_provider_payment_id_mismatch(binding_context, valid_claim, now):
    mismatched_payment = ProviderPayment(
        payment_id="pay_different_from_claim",
        order_id="order_001",
        amount=Money(amount=50000, currency="INR"),
        status="captured",
        captured=True,
        method="card",
        created_at=now,
    )
    outcome = TransactionBindingVerifier.verify(
        claim=valid_claim,
        authoritative_context=binding_context,
        authoritative_payment=mismatched_payment,
        reference_time=now,
    )
    assert outcome.is_valid is False
    assert outcome.status == IntegrityStatus.DRIFT
    assert BindingViolationCode.PAYMENT_MISMATCH in outcome.violations


# 10. Provider order ID mismatch rejected
def test_provider_order_id_mismatch(binding_context, valid_claim, now):
    mismatched_payment = ProviderPayment(
        payment_id="pay_001",
        order_id="order_different_from_context",
        amount=Money(amount=50000, currency="INR"),
        status="captured",
        captured=True,
        method="card",
        created_at=now,
    )
    outcome = TransactionBindingVerifier.verify(
        claim=valid_claim,
        authoritative_context=binding_context,
        authoritative_payment=mismatched_payment,
        reference_time=now,
    )
    assert outcome.is_valid is False
    assert outcome.status == IntegrityStatus.DRIFT
    assert BindingViolationCode.ORDER_MISMATCH in outcome.violations


# 11. Amount matching across disparate contexts is NOT sufficient (Anti-collision test)
def test_amount_matching_is_insufficient(binding_context, now):
    # Same amount (50000 INR) but mismatched order_id and agent_id
    claim = PaymentBindingClaim(
        intent_id="intent_001",
        agent_id="rogue_agent",
        merchant_id="merchant_001",
        transaction_id="tx_001",
        order_id="order_different",
        payment_id="pay_colliding_amount",
        attempt_id="att_1",
    )
    payment = ProviderPayment(
        payment_id="pay_colliding_amount",
        order_id="order_different",
        amount=Money(amount=50000, currency="INR"),  # Exactly identical amount!
        status="captured",
        captured=True,
        method="upi",
        created_at=now,
    )
    outcome = TransactionBindingVerifier.verify(
        claim=claim,
        authoritative_context=binding_context,
        authoritative_payment=payment,
        reference_time=now,
    )
    assert outcome.is_valid is False
    assert outcome.status == IntegrityStatus.DRIFT
    assert BindingViolationCode.AGENT_MISMATCH in outcome.violations
    assert BindingViolationCode.ORDER_MISMATCH in outcome.violations


# 12. Multiple simultaneous mismatches are captured cumulatively
def test_cumulative_violations(binding_context, valid_payment, now):
    tampered_claim = PaymentBindingClaim(
        intent_id="intent_tampered",
        agent_id="agent_tampered",
        merchant_id="merchant_tampered",
        transaction_id="tx_tampered",
        order_id="order_tampered",
        payment_id="pay_001",
        attempt_id="att_1",
    )
    outcome = TransactionBindingVerifier.verify(
        claim=tampered_claim,
        authoritative_context=binding_context,
        authoritative_payment=valid_payment,
        reference_time=now,
    )
    assert outcome.is_valid is False
    assert outcome.status == IntegrityStatus.DRIFT
    assert len(outcome.violations) >= 5
    assert BindingViolationCode.INTENT_MISMATCH in outcome.violations
    assert BindingViolationCode.AGENT_MISMATCH in outcome.violations
    assert BindingViolationCode.MERCHANT_MISMATCH in outcome.violations
    assert BindingViolationCode.TRANSACTION_MISMATCH in outcome.violations
    assert BindingViolationCode.ORDER_MISMATCH in outcome.violations


# 13. Missing authoritative provider payment with require_authoritative_payment=True results in UNKNOWN
def test_unresolved_provider_payment_yields_unknown(binding_context, valid_claim, now):
    outcome = TransactionBindingVerifier.verify(
        claim=valid_claim,
        authoritative_context=binding_context,
        authoritative_payment=None,
        require_authoritative_payment=True,
        reference_time=now,
    )
    assert outcome.is_valid is False
    assert outcome.status == IntegrityStatus.UNKNOWN
    assert BindingViolationCode.UNRESOLVED_PROVIDER_STATE in outcome.violations


# 14. Verification is purely deterministic and reproducible
def test_verification_is_deterministic(binding_context, valid_claim, valid_payment, now):
    res1 = TransactionBindingVerifier.verify(valid_claim, binding_context, valid_payment, reference_time=now)
    res2 = TransactionBindingVerifier.verify(valid_claim, binding_context, valid_payment, reference_time=now)
    assert res1.model_dump() == res2.model_dump()
