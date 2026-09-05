"""Unit tests for Innovation I15 — Deterministic SLA Engine."""
from datetime import datetime, timezone, timedelta
import pytest

from backend.app.domain.models.enums import IntegrityStatus
from backend.app.domain.models.intent import IntentContract, IntentItem
from backend.app.domain.models.money import Money
from backend.app.domain.models.payment import ProviderOrder, ProviderPayment
from backend.app.domain.models.integrity import IntegrityResult
from backend.app.domain.models.evidence import CanonicalEvent
from backend.app.domain.binding.contracts import BindingVerificationOutcome
from backend.app.domain.kill_switch.contracts import KillSwitchRecord, KillSwitchState, KillTrigger, ExecutionDecision
from backend.app.domain.trace.contracts import (
    IntegrityTrace,
    LifecycleStage,
    StageIntegrityStatus,
    LifecycleStep,
    FirstDivergence,
    ContextBindingSnapshot,
)
from backend.app.domain.checkpoint.contracts import (
    CheckpointType,
    CheckpointStatus,
    IntegrityCheckpoint,
    IntegrityCheckpointTimeline,
    ChainVerificationResult,
    compute_checkpoint_fingerprint,
    verify_checkpoint_chain,
)
from backend.app.domain.sla.contracts import (
    MetricStatus,
    MetricUnit,
    MetricName,
    SLAPolicy,
)
from backend.app.domain.sla.engine import DeterministicSLAEngine


def make_intent(ref_time: datetime, amount: int = 1000) -> IntentContract:
    return IntentContract(
        intent_id="int_sla",
        issued_by="agent_buyer_01",
        issued_at=ref_time,
        expires_at=ref_time + timedelta(hours=1),
        currency="INR",
        max_total=Money(amount=amount, currency="INR"),
        items=[
            IntentItem(
                item_id="item_1",
                sku="SKU-1",
                name="Widget",
                quantity=1,
                unit_price=Money(amount=amount, currency="INR"),
                total_price=Money(amount=amount, currency="INR"),
            )
        ],
    )


def test_sla_engine_clean_pass_transaction():
    """Validates that a clean PASS transaction marks drift-specific metrics as NOT_APPLICABLE and coverage as compliant."""
    ref_time = datetime(2026, 9, 6, 10, 0, 0, tzinfo=timezone.utc)
    intent = make_intent(ref_time)
    order = ProviderOrder(
        order_id="order_1",
        amount=Money(amount=1000, currency="INR"),
        receipt="rec_1",
        status="created",
        created_at=ref_time + timedelta(milliseconds=200),
        notes={"merchant_id": "merch_1"},
    )
    payment = ProviderPayment(
        payment_id="pay_1",
        order_id="order_1",
        amount=Money(amount=1000, currency="INR"),
        status="captured",
        method="card",
        created_at=ref_time + timedelta(milliseconds=800),
    )
    integrity_res = IntegrityResult(
        evaluation_id="eval_1",
        intent_id="int_sla",
        status=IntegrityStatus.PASS,
        explanation="All invariants passed",
        violations=[],
        evaluated_at=ref_time + timedelta(milliseconds=900),
    )

    report = DeterministicSLAEngine.compute_report(
        transaction_id="tx_clean",
        intent=intent,
        order=order,
        payment=payment,
        integrity_result=integrity_res,
        created_at=ref_time,
        completed_at=ref_time + timedelta(milliseconds=950),
        reference_time=ref_time + timedelta(milliseconds=1000),
    )

    metrics_map = {m.metric_name: m for m in report.metrics}

    # TIME_TO_DETECT should be NOT_APPLICABLE
    assert metrics_map[MetricName.TIME_TO_DETECT].status == MetricStatus.NOT_APPLICABLE
    assert metrics_map[MetricName.TIME_TO_PROVE].status == MetricStatus.NOT_APPLICABLE
    assert metrics_map[MetricName.TIME_TO_INTERVENE].status == MetricStatus.NOT_APPLICABLE
    assert metrics_map[MetricName.UNKNOWN_EXPOSURE_DURATION].status == MetricStatus.NOT_APPLICABLE

    # TIME_TO_FINAL_DECISION should be MEASURABLE
    m_final = metrics_map[MetricName.TIME_TO_FINAL_DECISION]
    assert m_final.status == MetricStatus.MEASURABLE
    assert m_final.value == 950.0
    assert m_final.is_compliant is True


def test_sla_engine_drift_detection_and_intervention():
    """Validates detection latency and intervention timing when drift occurs."""
    ref_time = datetime(2026, 9, 6, 10, 0, 0, tzinfo=timezone.utc)
    trigger_time = ref_time + timedelta(milliseconds=100)
    detect_time = ref_time + timedelta(milliseconds=350)
    intervene_time = ref_time + timedelta(milliseconds=450)

    trace = IntegrityTrace(
        trace_id="tr_1",
        transaction_id="tx_drift",
        deterministic_decision=IntegrityStatus.DRIFT,
        execution_state=KillSwitchState.KILLED,
        context_bindings=ContextBindingSnapshot(transaction_id="tx_drift"),
        steps=[
            LifecycleStep(
                sequence=1,
                stage=LifecycleStage.INTENT,
                status=StageIntegrityStatus.CONFIRMED_VALID,
                timestamp=ref_time,
            ),
            LifecycleStep(
                sequence=2,
                stage=LifecycleStage.AGENT,
                status=StageIntegrityStatus.DIVERGENCE_DETECTED,
                findings=["Price drifted"],
                timestamp=trigger_time,
            ),
        ],
        first_divergence=FirstDivergence(
            stage=LifecycleStage.AGENT,
            step_sequence=2,
            finding="Price drifted",
            detected_at=detect_time,
        ),
        generated_at=detect_time,
    )

    ks_rec = KillSwitchRecord(
        record_id="ks_1",
        transaction_id="tx_drift",
        prior_state=KillSwitchState.RUNNING,
        resulting_state=KillSwitchState.KILLED,
        decision=ExecutionDecision.BLOCK,
        trigger=KillTrigger.CRITICAL_DRIFT,
        reason="Drift detected",
        timestamp=intervene_time,
    )

    report = DeterministicSLAEngine.compute_report(
        transaction_id="tx_drift",
        integrity_trace=trace,
        kill_switch_record=ks_rec,
        created_at=ref_time,
        reference_time=intervene_time + timedelta(seconds=1),
    )

    metrics_map = {m.metric_name: m for m in report.metrics}

    # Detection latency: 350 - 100 = 250 ms
    m_detect = metrics_map[MetricName.TIME_TO_DETECT]
    assert m_detect.status == MetricStatus.MEASURABLE
    assert m_detect.value == 250.0
    assert m_detect.is_compliant is True

    # Intervention latency: 450 - 350 = 100 ms
    m_intervene = metrics_map[MetricName.TIME_TO_INTERVENE]
    assert m_intervene.status == MetricStatus.MEASURABLE
    assert m_intervene.value == 100.0
    assert m_intervene.is_compliant is True


def test_sla_engine_checkpoint_and_trace_coverage():
    """Validates checkpoint coverage and trace completeness calculations."""
    ref_time = datetime(2026, 9, 6, 10, 0, 0, tzinfo=timezone.utc)

    # Build 4 checkpoints: 3 valid, 1 invalid (out of 8 canonical)
    checkpoints = []
    types = [
        CheckpointType.INTENT_AUTHORIZED,
        CheckpointType.AGENT_ACTION_AUTHORIZED,
        CheckpointType.MERCHANT_OFFER_VERIFIED,
        CheckpointType.ORDER_CREATED,
    ]
    prev_fp = None
    for idx, cp_t in enumerate(types, start=1):
        status = CheckpointStatus.VALID if idx < 4 else CheckpointStatus.INVALID
        fp = compute_checkpoint_fingerprint(
            transaction_id="tx_cov",
            checkpoint_type=cp_t.value,
            sequence=idx,
            lifecycle_stage=cp_t.value.split("_")[0],
            status=status.value,
            verified_fields=["field_1"],
            evidence_refs=["ev_1"],
            integrity_decision="PASS" if status == CheckpointStatus.VALID else "DRIFT",
            binding_decision="VALID",
            execution_state="RUNNING",
            missing_evidence=[],
            findings=[],
            governance_version="gov_v1.0.0",
            previous_checkpoint_fingerprint=prev_fp,
        )
        stage = LifecycleStage.INTENT if idx == 1 else (LifecycleStage.AGENT if idx == 2 else (LifecycleStage.MERCHANT if idx == 3 else LifecycleStage.ORDER))
        cp = IntegrityCheckpoint(
            checkpoint_id=f"cp_{idx}",
            transaction_id="tx_cov",
            checkpoint_type=cp_t,
            sequence=idx,
            lifecycle_stage=stage,
            status=status,
            integrity_decision=IntegrityStatus.PASS if status == CheckpointStatus.VALID else IntegrityStatus.DRIFT,
            execution_state=KillSwitchState.RUNNING,
            fingerprint=fp,
            previous_checkpoint_fingerprint=prev_fp,
            created_at=ref_time + timedelta(milliseconds=idx * 50),
        )
        checkpoints.append(cp)
        prev_fp = fp

    timeline = IntegrityCheckpointTimeline(
        transaction_id="tx_cov",
        checkpoints=checkpoints,
        chain_verification=verify_checkpoint_chain(checkpoints),
        last_valid_checkpoint=checkpoints[2],
        first_invalid_checkpoint=checkpoints[3],
        has_unknown_checkpoints=False,
        generated_at=ref_time + timedelta(milliseconds=300),
    )

    report = DeterministicSLAEngine.compute_report(
        transaction_id="tx_cov",
        checkpoint_timeline=timeline,
        created_at=ref_time,
    )

    metrics_map = {m.metric_name: m for m in report.metrics}

    # Checkpoint coverage: 4 / 8 = 0.5
    m_cov = metrics_map[MetricName.CHECKPOINT_COVERAGE_RATIO]
    assert m_cov.status == MetricStatus.MEASURABLE
    assert m_cov.value == 0.5
    # threshold is 0.75, so 0.5 is breached
    assert m_cov.is_compliant is False

    # Checkpoint valid ratio: 3 / 8 = 0.375
    m_val = metrics_map[MetricName.CHECKPOINT_VALID_RATIO]
    assert m_val.status == MetricStatus.MEASURABLE
    assert m_val.value == 0.375
    # threshold is 0.5, so breached
    assert m_val.is_compliant is False


def test_sla_engine_unknown_exposure_duration():
    """Validates measurement of time spent in UNKNOWN state."""
    ref_time = datetime(2026, 9, 6, 10, 0, 0, tzinfo=timezone.utc)
    unknown_start = ref_time + timedelta(milliseconds=200)
    resolved_time = ref_time + timedelta(milliseconds=1200)

    integrity_unknown = IntegrityResult(
        evaluation_id="eval_unk",
        intent_id="int_sla",
        status=IntegrityStatus.UNKNOWN,
        explanation="Payment status pending from gateway",
        violations=[],
        evaluated_at=unknown_start,
    )

    resolve_event = CanonicalEvent(
        event_id="ev_res",
        transaction_id="tx_unk",
        intent_id="int_sla",
        event_type="transaction_resolved",
        timestamp=resolved_time,
    )

    report = DeterministicSLAEngine.compute_report(
        transaction_id="tx_unk",
        integrity_result=integrity_unknown,
        events=[resolve_event],
        created_at=ref_time,
    )

    metrics_map = {m.metric_name: m for m in report.metrics}
    m_unk = metrics_map[MetricName.UNKNOWN_EXPOSURE_DURATION]
    assert m_unk.status == MetricStatus.MEASURABLE
    assert m_unk.value == 1000.0  # 1200 - 200 = 1000 ms
    assert m_unk.is_compliant is True


def test_sla_engine_clock_anomaly_reversed_timestamps():
    """Validates that reversed timestamps yield INVALID instead of negative or coerced latency."""
    ref_time = datetime(2026, 9, 6, 10, 0, 0, tzinfo=timezone.utc)

    # Detection happens BEFORE trigger timestamp
    trace = IntegrityTrace(
        trace_id="tr_rev",
        transaction_id="tx_rev",
        deterministic_decision=IntegrityStatus.DRIFT,
        execution_state=KillSwitchState.RUNNING,
        context_bindings=ContextBindingSnapshot(transaction_id="tx_rev"),
        steps=[
            LifecycleStep(
                sequence=1,
                stage=LifecycleStage.INTENT,
                status=StageIntegrityStatus.CONFIRMED_VALID,
                timestamp=ref_time + timedelta(seconds=10),  # Future trigger
            ),
        ],
        first_divergence=FirstDivergence(
            stage=LifecycleStage.INTENT,
            step_sequence=1,
            finding="Drift",
            detected_at=ref_time,  # Past detection
        ),
        generated_at=ref_time,
    )

    report = DeterministicSLAEngine.compute_report(
        transaction_id="tx_rev",
        integrity_trace=trace,
    )

    metrics_map = {m.metric_name: m for m in report.metrics}
    m_detect = metrics_map[MetricName.TIME_TO_DETECT]
    assert m_detect.status == MetricStatus.INVALID
    assert m_detect.value is None
    assert m_detect.is_compliant is False
    assert "Clock anomaly" in m_detect.calculation_reason
