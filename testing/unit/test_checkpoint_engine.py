"""Unit tests for DeterministicCheckpointEngine (Innovation I14)."""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import pytest

from backend.app.domain.models.enums import IntegrityStatus, TransactionState
from backend.app.domain.models.intent import IntentContract, IntentItem
from backend.app.domain.models.money import Money
from backend.app.domain.models.payment import ProviderOrder, ProviderPayment
from backend.app.domain.models.integrity import IntegrityResult
from backend.app.domain.binding.contracts import (
    BindingContext,
    BindingVerificationOutcome,
)
from backend.app.domain.kill_switch.contracts import KillSwitchState
from backend.app.domain.checkpoint.contracts import (
    CheckpointType,
    CheckpointStatus,
    IntegrityCheckpointTimeline,
)
from backend.app.domain.checkpoint.engine import DeterministicCheckpointEngine


@pytest.fixture
def base_intent() -> IntentContract:
    ref_time = datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)
    return IntentContract(
        intent_id="int_chk_001",
        issued_by="agent_buyer_001",
        issued_at=ref_time,
        expires_at=datetime(2027, 1, 1, tzinfo=timezone.utc),
        currency="INR",
        max_total=Money(amount=10000, currency="INR"),
        items=[
            IntentItem(
                item_id="prod_coffee_100",
                sku="SKU_COFFEE_100",
                name="Coffee 100g",
                quantity=1,
                unit_price=Money(amount=10000, currency="INR"),
                total_price=Money(amount=10000, currency="INR"),
            )
        ],
    )


@pytest.fixture
def base_order() -> ProviderOrder:
    ref_time = datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)
    return ProviderOrder(
        order_id="order_chk_001",
        amount=Money(amount=10000, currency="INR"),
        receipt="rcpt_001",
        status="created",
        created_at=ref_time,
        notes={"merchant_id": "merch_acme_corp"},
    )


@pytest.fixture
def base_payment() -> ProviderPayment:
    ref_time = datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)
    return ProviderPayment(
        payment_id="pay_chk_001",
        order_id="order_chk_001",
        amount=Money(amount=10000, currency="INR"),
        status="captured",
        method="upi",
        created_at=ref_time,
    )


def make_integrity_result(intent_id: str, status: IntegrityStatus, violations: list, ref_time: datetime, explanation: str = "") -> IntegrityResult:
    return IntegrityResult(
        evaluation_id=f"eval_{intent_id}",
        intent_id=intent_id,
        status=status,
        explanation=explanation or f"Integrity result: {status.value}",
        violations=violations,
        evaluated_at=ref_time,
    )


def make_binding_outcome(is_valid: bool = True, ref_time: Optional[datetime] = None) -> BindingVerificationOutcome:
    return BindingVerificationOutcome(
        is_valid=is_valid,
        status=IntegrityStatus.PASS if is_valid else IntegrityStatus.DRIFT,
        violations=[],
        details={},
        explanation="Bindings verified",
        verified_at=ref_time or datetime.now(timezone.utc),
    )


def test_full_valid_lifecycle_timeline(base_intent, base_order, base_payment):
    """Verifies that an end-to-end clean transaction produces 8 valid chained checkpoints."""
    ref_time = datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)
    integrity_result = make_integrity_result(
        intent_id=base_intent.intent_id,
        status=IntegrityStatus.PASS,
        violations=[],
        ref_time=ref_time,
        explanation="All deterministic rules passed",
    )
    binding_outcome = make_binding_outcome(is_valid=True, ref_time=ref_time)

    timeline = DeterministicCheckpointEngine.generate_timeline(
        transaction_id="tx_chk_full_valid",
        intent=base_intent,
        order=base_order,
        payment=base_payment,
        integrity_result=integrity_result,
        binding_outcome=binding_outcome,
        kill_switch_state=KillSwitchState.RUNNING,
        state_machine_state="COMPLETED",
        reference_time=ref_time,
    )

    assert timeline.transaction_id == "tx_chk_full_valid"
    assert len(timeline.checkpoints) == 8
    assert timeline.chain_verification.is_valid is True
    assert timeline.has_unknown_checkpoints is False
    assert timeline.first_invalid_checkpoint is None
    assert timeline.last_valid_checkpoint is not None
    assert timeline.last_valid_checkpoint.checkpoint_type == CheckpointType.COMPLETION_VERIFIED
    assert timeline.last_valid_checkpoint.sequence == 8

    # Check that sequence numbers are strictly 1..8
    for idx, cp in enumerate(timeline.checkpoints):
        assert cp.sequence == idx + 1
        assert cp.status == CheckpointStatus.VALID
        assert cp.verify_fingerprint() is True


def test_divergence_in_payment_timeline(base_intent, base_order, base_payment):
    """Verifies that payment amount mismatch correctly bounds last_valid and first_invalid."""
    ref_time = datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)
    tampered_payment = ProviderPayment(
        payment_id="pay_chk_tampered",
        order_id="order_chk_001",
        amount=Money(amount=15000, currency="INR"),  # Exceeds max_total 10000
        status="captured",
        method="card",
        created_at=ref_time,
    )
    integrity_result = make_integrity_result(
        intent_id=base_intent.intent_id,
        status=IntegrityStatus.DRIFT,
        violations=["AMOUNT_MISMATCH: Payment amount exceeds maximum authorized limit"],
        ref_time=ref_time,
        explanation="Payment amount 15000 exceeds intent limit 10000",
    )
    binding_outcome = make_binding_outcome(is_valid=True, ref_time=ref_time)

    timeline = DeterministicCheckpointEngine.generate_timeline(
        transaction_id="tx_chk_payment_drift",
        intent=base_intent,
        order=base_order,
        payment=tampered_payment,
        integrity_result=integrity_result,
        binding_outcome=binding_outcome,
        kill_switch_state=KillSwitchState.KILLED,
        reference_time=ref_time,
    )

    assert len(timeline.checkpoints) == 8
    assert timeline.chain_verification.is_valid is True

    # First invalid must be PAYMENT_AUTHORIZED (stage 6)
    assert timeline.first_invalid_checkpoint is not None
    assert timeline.first_invalid_checkpoint.checkpoint_type == CheckpointType.PAYMENT_AUTHORIZED
    assert timeline.first_invalid_checkpoint.sequence == 6
    assert timeline.first_invalid_checkpoint.status == CheckpointStatus.INVALID

    # Last valid must be PAYMENT_ATTEMPT_CREATED (stage 5)
    assert timeline.last_valid_checkpoint is not None
    assert timeline.last_valid_checkpoint.checkpoint_type == CheckpointType.PAYMENT_ATTEMPT_CREATED
    assert timeline.last_valid_checkpoint.sequence == 5
    assert timeline.last_valid_checkpoint.status == CheckpointStatus.VALID


def test_unknown_evidence_does_not_falsely_mark_invalid(base_intent, base_order):
    """Verifies that missing evidence causes UNKNOWN checkpoint without false invalid attribution."""
    ref_time = datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)
    integrity_result = make_integrity_result(
        intent_id=base_intent.intent_id,
        status=IntegrityStatus.UNKNOWN,
        violations=[],
        ref_time=ref_time,
        explanation="Payment confirmation delayed from provider",
    )
    binding_outcome = make_binding_outcome(is_valid=True, ref_time=ref_time)

    timeline = DeterministicCheckpointEngine.generate_timeline(
        transaction_id="tx_chk_unknown",
        intent=base_intent,
        order=base_order,
        payment=None,  # missing payment confirmation
        integrity_result=integrity_result,
        binding_outcome=binding_outcome,
        kill_switch_state=KillSwitchState.PAUSED,
        reference_time=ref_time,
    )

    assert timeline.has_unknown_checkpoints is True
    # Crucial invariant: no false invalid attribution!
    assert timeline.first_invalid_checkpoint is None
    # Last valid is PAYMENT_ATTEMPT_CREATED (stage 5)
    assert timeline.last_valid_checkpoint is not None
    assert timeline.last_valid_checkpoint.sequence == 5
    assert timeline.last_valid_checkpoint.checkpoint_type == CheckpointType.PAYMENT_ATTEMPT_CREATED


def test_stopped_early_not_reached_boundaries(base_intent, base_order):
    """Verifies that transactions not reaching later stages mark them NOT_REACHED."""
    ref_time = datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)
    integrity_result = make_integrity_result(
        intent_id=base_intent.intent_id,
        status=IntegrityStatus.PASS,
        violations=[],
        ref_time=ref_time,
        explanation="Order created",
    )

    timeline = DeterministicCheckpointEngine.generate_timeline(
        transaction_id="tx_chk_early_stop",
        intent=base_intent,
        order=base_order,
        payment=None,
        integrity_result=integrity_result,
        binding_outcome=make_binding_outcome(is_valid=True, ref_time=ref_time),
        reference_time=ref_time,
    )

    # Checkpoints 1..4 are valid; 5..8 are unreached or unknown
    cp1 = timeline.checkpoints[0]
    cp4 = timeline.checkpoints[3]
    assert cp1.status == CheckpointStatus.VALID
    assert cp4.status == CheckpointStatus.VALID

    # Checkpoints 5..8 are NOT_REACHED or UNKNOWN
    later_statuses = [cp.status for cp in timeline.checkpoints[4:]]
    assert CheckpointStatus.INVALID not in later_statuses


def test_replay_determinism_identical_fingerprints(base_intent, base_order, base_payment):
    """Verifies that two independent runs on identical inputs yield bit-for-bit identical fingerprints."""
    ref_time = datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)
    integrity_result = make_integrity_result(
        intent_id=base_intent.intent_id,
        status=IntegrityStatus.PASS,
        violations=[],
        ref_time=ref_time,
        explanation="Valid",
    )
    binding_outcome = make_binding_outcome(is_valid=True, ref_time=ref_time)

    timeline1 = DeterministicCheckpointEngine.generate_timeline(
        transaction_id="tx_chk_replay",
        intent=base_intent,
        order=base_order,
        payment=base_payment,
        integrity_result=integrity_result,
        binding_outcome=binding_outcome,
        reference_time=ref_time,
    )

    timeline2 = DeterministicCheckpointEngine.generate_timeline(
        transaction_id="tx_chk_replay",
        intent=base_intent,
        order=base_order,
        payment=base_payment,
        integrity_result=integrity_result,
        binding_outcome=binding_outcome,
        reference_time=ref_time,
    )

    for cp1, cp2 in zip(timeline1.checkpoints, timeline2.checkpoints):
        assert cp1.fingerprint == cp2.fingerprint
        assert cp1.status == cp2.status
        assert cp1.verified_fields == cp2.verified_fields
        assert cp1.evidence_refs == cp2.evidence_refs


def test_secret_sanitization_in_findings():
    """Verifies that credentials and secrets in findings are redacted."""
    raw_finding = "Gateway returned secret=super_secret_token_xyz for payment_id"
    sanitized = DeterministicCheckpointEngine._sanitize_text(raw_finding)
    assert "super_secret_token_xyz" not in sanitized
    assert "[REDACTED]" in sanitized
