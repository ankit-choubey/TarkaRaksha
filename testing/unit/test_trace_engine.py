"""Unit tests for Innovation I13 — Deterministic Trace Engine.

Verifies:
1. Chronological progression of 8 lifecycle stages.
2. Accurate first divergence detection across different stages (INTENT, AGENT, MERCHANT, ORDER, ATTEMPT, PAYMENT, GATEWAY).
3. Multiple findings preservation (first divergence + downstream faults).
4. Strict UNKNOWN handling and early missing evidence uncertainty flags.
5. Secret redaction across trace contexts.
"""
from datetime import datetime, timezone, timedelta
import pytest

from backend.app.domain.models.enums import EvidenceSource, IntegrityStatus, TransactionState
from backend.app.domain.models.money import Money
from backend.app.domain.models.intent import IntentContract, IntentItem
from backend.app.domain.models.payment import ProviderOrder, ProviderPayment
from backend.app.domain.models.evidence import CanonicalEvent
from backend.app.domain.models.integrity import MRDP, IntegrityResult
from backend.app.domain.binding.contracts import (
    BindingContext,
    BindingVerificationOutcome,
    BindingViolationCode,
)
from backend.app.domain.kill_switch.contracts import (
    KillSwitchRecord,
    KillSwitchState,
    KillTrigger,
)
from backend.app.domain.trace.contracts import (
    IntegrityTrace,
    LifecycleStage,
    StageIntegrityStatus,
)
from backend.app.domain.trace.engine import DeterministicTraceEngine


def create_valid_intent(issued_at: datetime) -> IntentContract:
    return IntentContract(
        intent_id="int_valid_001",
        issued_by="agent_buyer_1",
        issued_at=issued_at,
        expires_at=issued_at + timedelta(minutes=30),
        currency="INR",
        max_total=Money(amount=50000, currency="INR"),
        items=[
            IntentItem(
                item_id="item_001",
                sku="SKU-BOOK-01",
                name="Physics Textbook",
                quantity=1,
                unit_price=Money(amount=50000, currency="INR"),
                total_price=Money(amount=50000, currency="INR"),
            )
        ],
    )


def test_clean_successful_lifecycle():
    now = datetime.now(timezone.utc)
    intent = create_valid_intent(now)

    order = ProviderOrder(
        order_id="order_clean_001",
        amount=Money(amount=50000, currency="INR"),
        currency="INR",
        status="created",
        notes={"merchant_id": "merchant_001"},
        created_at=now,
    )

    payment = ProviderPayment(
        payment_id="pay_clean_001",
        order_id="order_clean_001",
        amount=Money(amount=50000, currency="INR"),
        currency="INR",
        status="captured",
        method="card",
        created_at=now,
    )

    binding_ctx = BindingContext(
        intent_id=intent.intent_id,
        agent_id=intent.issued_by,
        merchant_id="merchant_001",
        transaction_id="tx_clean_001",
        order_id=order.order_id,
        attempt_id="att_1",
        created_at=now,
    )

    binding_outcome = BindingVerificationOutcome(
        is_valid=True,
        status=IntegrityStatus.PASS,
        violations=[],
        details={"payment_id": payment.payment_id},
        explanation="All bindings verified successfully",
        verified_at=now,
    )

    integrity_result = IntegrityResult(
        evaluation_id="eval_clean_001",
        intent_id=intent.intent_id,
        status=IntegrityStatus.PASS,
        violations=[],
        evaluated_at=now,
    )

    mrdp = MRDP(
        mrdp_id="mrdp_clean_001",
        intent_id=intent.intent_id,
        error_code="NONE",
        status=IntegrityStatus.PASS,
        violation="None",
        drift_source="NONE",
        expected_value="PASS",
        observed_value="PASS",
        generated_at=now,
    )

    trace = DeterministicTraceEngine.build_trace(
        transaction_id="tx_clean_001",
        intent=intent,
        order=order,
        payment=payment,
        binding_context=binding_ctx,
        binding_outcome=binding_outcome,
        integrity_result=integrity_result,
        kill_switch_state=KillSwitchState.RUNNING,
        mrdp=mrdp,
        state_machine_state=TransactionState.PASS,
        reference_time=now + timedelta(minutes=5),
    )

    assert trace.deterministic_decision == IntegrityStatus.PASS
    assert trace.execution_state == KillSwitchState.RUNNING
    assert trace.first_divergence is None
    assert len(trace.fault_locations) == 0
    assert len(trace.steps) == 8

    # All steps should be confirmed valid
    for step in trace.steps:
        assert step.status == StageIntegrityStatus.CONFIRMED_VALID


def test_first_divergence_at_intent_stage():
    now = datetime.now(timezone.utc)
    intent = create_valid_intent(now)

    # Reference time is past intent expiration
    eval_time = now + timedelta(hours=2)

    trace = DeterministicTraceEngine.build_trace(
        transaction_id="tx_expired_001",
        intent=intent,
        reference_time=eval_time,
    )

    assert trace.first_divergence is not None
    assert trace.first_divergence.stage == LifecycleStage.INTENT
    assert trace.first_divergence.step_sequence == 1
    assert "INTENT_EXPIRED" in trace.first_divergence.finding
    assert any(f.finding_code == "INTENT_EXPIRED" for f in trace.fault_locations)


def test_first_divergence_at_agent_stage():
    now = datetime.now(timezone.utc)
    intent = create_valid_intent(now)

    binding_ctx = BindingContext(
        intent_id=intent.intent_id,
        agent_id="authorized_agent_42",
        merchant_id="merchant_001",
        transaction_id="tx_agent_drift",
        order_id="order_001",
        attempt_id="att_1",
        created_at=now,
    )

    binding_outcome = BindingVerificationOutcome(
        is_valid=False,
        status=IntegrityStatus.DRIFT,
        violations=[BindingViolationCode.AGENT_MISMATCH],
        details={"claimed_agent_id": "malicious_agent_99"},
        explanation="Executing agent mismatch",
        verified_at=now,
    )

    trace = DeterministicTraceEngine.build_trace(
        transaction_id="tx_agent_drift",
        intent=intent,
        binding_context=binding_ctx,
        binding_outcome=binding_outcome,
        reference_time=now,
    )

    assert trace.first_divergence is not None
    assert trace.first_divergence.stage == LifecycleStage.AGENT
    assert trace.first_divergence.step_sequence == 2
    assert trace.first_divergence.finding == BindingViolationCode.AGENT_MISMATCH.value


def test_first_divergence_at_order_stage():
    now = datetime.now(timezone.utc)
    intent = create_valid_intent(now)

    # Order amount exceeds authorized amount
    order = ProviderOrder(
        order_id="order_exorbitant",
        amount=Money(amount=999999, currency="INR"),  # 9999.99 INR > authorized 500.00 INR
        currency="INR",
        status="created",
        notes={"merchant_id": "merchant_001"},
        created_at=now,
    )

    binding_ctx = BindingContext(
        intent_id=intent.intent_id,
        agent_id=intent.issued_by,
        merchant_id="merchant_001",
        transaction_id="tx_order_exceeded",
        order_id=order.order_id,
        attempt_id="att_1",
        created_at=now,
    )

    trace = DeterministicTraceEngine.build_trace(
        transaction_id="tx_order_exceeded",
        intent=intent,
        order=order,
        binding_context=binding_ctx,
        reference_time=now,
    )

    assert trace.first_divergence is not None
    assert trace.first_divergence.stage == LifecycleStage.ORDER
    assert trace.first_divergence.step_sequence == 4
    assert trace.first_divergence.finding == "ORDER_AMOUNT_EXCEEDED"


def test_multiple_findings_preservation():
    now = datetime.now(timezone.utc)
    intent = create_valid_intent(now)

    # Order has mismatch (stage 4)
    binding_outcome = BindingVerificationOutcome(
        is_valid=False,
        status=IntegrityStatus.DRIFT,
        violations=[BindingViolationCode.ORDER_MISMATCH, BindingViolationCode.PAYMENT_MISMATCH],
        details={"expected_order_id": "order_exp", "claimed_order_id": "order_bad"},
        explanation="Multiple binding violations detected",
        verified_at=now,
    )

    trace = DeterministicTraceEngine.build_trace(
        transaction_id="tx_multi_drift",
        intent=intent,
        binding_outcome=binding_outcome,
        reference_time=now,
    )

    # Earliest divergence must be ORDER (stage 4)
    assert trace.first_divergence is not None
    assert trace.first_divergence.stage == LifecycleStage.ORDER
    assert trace.first_divergence.step_sequence == 4

    # Both ORDER and PAYMENT faults must be preserved in fault_locations
    stages_in_faults = {f.stage for f in trace.fault_locations}
    assert LifecycleStage.ORDER in stages_in_faults
    assert LifecycleStage.PAYMENT in stages_in_faults


def test_strict_unknown_and_early_missing_evidence():
    now = datetime.now(timezone.utc)

    # Intent is missing -> Stage 1 (INTENT) becomes UNKNOWN
    order = ProviderOrder(
        order_id="order_anon",
        amount=Money(amount=50000, currency="INR"),
        currency="INR",
        status="created",
        notes={"merchant_id": "merchant_001"},
        created_at=now,
    )

    # Stage 7 has signature failure
    events = [
        CanonicalEvent(
            event_id="ev_sig_fail",
            transaction_id="tx_unknown_early",
            intent_id="int_none",
            event_type="SIGNATURE_VERIFICATION_FAILED",
            source=EvidenceSource.RAZORPAY,
            payload_summary={"error": "Signature mismatch"},
            timestamp=now,
        )
    ]

    trace = DeterministicTraceEngine.build_trace(
        transaction_id="tx_unknown_early",
        intent=None,  # Missing intent
        order=order,
        events=events,
        reference_time=now,
    )

    # Stage 1 is UNKNOWN
    assert trace.steps[0].stage == LifecycleStage.INTENT
    assert trace.steps[0].status == StageIntegrityStatus.UNKNOWN
    assert "intent_contract" in trace.missing_evidence

    # Gateway stage detects divergence
    gateway_step = next(s for s in trace.steps if s.stage == LifecycleStage.GATEWAY)
    assert gateway_step.status == StageIntegrityStatus.DIVERGENCE_DETECTED

    # First divergence is at GATEWAY
    assert trace.first_divergence is not None
    assert trace.first_divergence.stage == LifecycleStage.GATEWAY

    # Must have uncertainty warning about earlier UNKNOWN stage
    assert len(trace.uncertainties) > 0
    assert any("INTENT" in u and "UNKNOWN" in u for u in trace.uncertainties)


def test_secret_redaction_in_trace_contexts():
    now = datetime.now(timezone.utc)
    intent = create_valid_intent(now)

    order = ProviderOrder(
        order_id="order_sec",
        amount=Money(amount=50000, currency="INR"),
        currency="INR",
        status="created",
        notes={"merchant_id": "merchant_001"},
        created_at=now,
    )

    events = [
        CanonicalEvent(
            event_id="ev_webhook_leak",
            transaction_id="tx_secret_redact",
            intent_id=intent.intent_id,
            event_type="SIGNATURE_VERIFICATION_FAILED",
            source=EvidenceSource.RAZORPAY,
            payload_summary={"webhook_secret": "whsec_super_secret_key_12345", "error": "invalid_signature"},
            timestamp=now,
        )
    ]

    trace = DeterministicTraceEngine.build_trace(
        transaction_id="tx_secret_redact",
        intent=intent,
        order=order,
        events=events,
        reference_time=now,
    )

    # Dump trace to JSON string and verify secrets are never leaked
    trace_json = trace.model_dump_json()
    assert "whsec_super_secret_key_12345" not in trace_json
    assert "[REDACTED" in trace_json
