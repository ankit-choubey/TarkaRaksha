"""Unit tests for Innovation I13 — Domain Trace Contracts.

Verifies:
1. Immutability (frozen models reject mutations).
2. Timezone awareness requirements (UTC required).
3. Sequence validation (1 to 8 inclusive, ascending order in trace).
4. Field validation (empty strings forbidden).
5. Serialization and deserialization roundtrip.
"""
from datetime import datetime, timezone, timedelta
import pytest
from pydantic import ValidationError

from backend.app.domain.models.enums import IntegrityStatus
from backend.app.domain.kill_switch.contracts import KillSwitchState
from backend.app.domain.trace.contracts import (
    ContextBindingSnapshot,
    FaultLocation,
    FieldDiscrepancy,
    FirstDivergence,
    IntegrityTrace,
    LifecycleStage,
    LifecycleStep,
    StageIntegrityStatus,
)


def test_context_binding_snapshot_immutability():
    snapshot = ContextBindingSnapshot(
        transaction_id="tx_123",
        intent_id="int_123",
        agent_id="agent_123",
        merchant_id="mer_123",
        order_id="order_123",
        payment_id="pay_123",
        attempt_id="att_1",
    )
    assert snapshot.transaction_id == "tx_123"
    with pytest.raises(ValidationError):
        snapshot.transaction_id = "tx_modified"


def test_context_binding_snapshot_empty_tx_rejected():
    with pytest.raises(ValidationError):
        ContextBindingSnapshot(transaction_id="   ")


def test_field_discrepancy_validation():
    disc = FieldDiscrepancy(
        field_name="amount",
        expected_value=1000,
        observed_value=1500,
        evidence_ref="ev_pay_1",
        description="Amount exceeded",
    )
    assert disc.field_name == "amount"
    with pytest.raises(ValidationError):
        FieldDiscrepancy(field_name="", expected_value=1, observed_value=2, description="test")


def test_lifecycle_step_sequence_validation():
    now = datetime.now(timezone.utc)
    step = LifecycleStep(
        sequence=1,
        stage=LifecycleStage.INTENT,
        status=StageIntegrityStatus.CONFIRMED_VALID,
        expected_context={"intent": "valid"},
        observed_context={"intent": "valid"},
        timestamp=now,
    )
    assert step.sequence == 1

    # Invalid sequence: 0
    with pytest.raises(ValidationError):
        LifecycleStep(
            sequence=0,
            stage=LifecycleStage.INTENT,
            status=StageIntegrityStatus.CONFIRMED_VALID,
            timestamp=now,
        )

    # Invalid sequence: 9
    with pytest.raises(ValidationError):
        LifecycleStep(
            sequence=9,
            stage=LifecycleStage.COMPLETION,
            status=StageIntegrityStatus.CONFIRMED_VALID,
            timestamp=now,
        )


def test_lifecycle_step_naive_datetime_rejected():
    naive_dt = datetime(2026, 9, 6, 12, 0, 0)
    with pytest.raises(ValidationError):
        LifecycleStep(
            sequence=1,
            stage=LifecycleStage.INTENT,
            status=StageIntegrityStatus.CONFIRMED_VALID,
            timestamp=naive_dt,
        )


def test_integrity_trace_order_validation():
    now = datetime.now(timezone.utc)
    snapshot = ContextBindingSnapshot(transaction_id="tx_test")
    step1 = LifecycleStep(
        sequence=1,
        stage=LifecycleStage.INTENT,
        status=StageIntegrityStatus.CONFIRMED_VALID,
        timestamp=now,
    )
    step2 = LifecycleStep(
        sequence=2,
        stage=LifecycleStage.AGENT,
        status=StageIntegrityStatus.CONFIRMED_VALID,
        timestamp=now,
    )

    # Valid ascending order
    trace = IntegrityTrace(
        trace_id="trc_001",
        transaction_id="tx_test",
        deterministic_decision=IntegrityStatus.PASS,
        execution_state=KillSwitchState.RUNNING,
        context_bindings=snapshot,
        steps=[step1, step2],
        generated_at=now,
    )
    assert len(trace.steps) == 2

    # Out of order steps rejected
    with pytest.raises(ValidationError):
        IntegrityTrace(
            trace_id="trc_002",
            transaction_id="tx_test",
            deterministic_decision=IntegrityStatus.PASS,
            execution_state=KillSwitchState.RUNNING,
            context_bindings=snapshot,
            steps=[step2, step1],
            generated_at=now,
        )


def test_integrity_trace_json_roundtrip():
    now = datetime.now(timezone.utc)
    snapshot = ContextBindingSnapshot(
        transaction_id="tx_rt",
        intent_id="int_rt",
        order_id="order_rt",
    )
    step1 = LifecycleStep(
        sequence=1,
        stage=LifecycleStage.INTENT,
        status=StageIntegrityStatus.CONFIRMED_VALID,
        expected_context={"val": 1},
        observed_context={"val": 1},
        timestamp=now,
    )
    trace = IntegrityTrace(
        trace_id="trc_rt",
        transaction_id="tx_rt",
        deterministic_decision=IntegrityStatus.PASS,
        execution_state=KillSwitchState.RUNNING,
        context_bindings=snapshot,
        steps=[step1],
        fault_locations=[],
        missing_evidence=[],
        uncertainties=[],
        generated_at=now,
    )

    json_data = trace.model_dump_json()
    reconstituted = IntegrityTrace.model_validate_json(json_data)
    assert reconstituted.trace_id == trace.trace_id
    assert reconstituted.steps[0].sequence == 1
    assert reconstituted.steps[0].stage == LifecycleStage.INTENT
