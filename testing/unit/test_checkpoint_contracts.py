"""Unit tests for Innovation I14 — Integrity Checkpoint contracts and chain validation."""
from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from backend.app.domain.models.enums import IntegrityStatus
from backend.app.domain.kill_switch.contracts import KillSwitchState
from backend.app.domain.trace.contracts import LifecycleStage
from backend.app.domain.checkpoint.contracts import (
    CheckpointType,
    CheckpointStatus,
    IntegrityCheckpoint,
    ChainVerificationResult,
    IntegrityCheckpointTimeline,
    compute_checkpoint_fingerprint,
    verify_checkpoint_chain,
)


def test_checkpoint_type_enum():
    """Verifies all 8 canonical checkpoint types exist and map to stages."""
    expected_types = [
        "INTENT_AUTHORIZED",
        "AGENT_ACTION_AUTHORIZED",
        "MERCHANT_OFFER_VERIFIED",
        "ORDER_CREATED",
        "PAYMENT_ATTEMPT_CREATED",
        "PAYMENT_AUTHORIZED",
        "PAYMENT_CAPTURE_VERIFIED",
        "COMPLETION_VERIFIED",
    ]
    for exp in expected_types:
        assert exp in [t.value for t in CheckpointType]
    assert len(CheckpointType) == 8


def test_checkpoint_status_enum():
    """Verifies the four explicit checkpoint status outcomes."""
    assert CheckpointStatus.VALID.value == "VALID"
    assert CheckpointStatus.INVALID.value == "INVALID"
    assert CheckpointStatus.UNKNOWN.value == "UNKNOWN"
    assert CheckpointStatus.NOT_REACHED.value == "NOT_REACHED"
    # Verify non-equivalence
    assert CheckpointStatus.UNKNOWN != CheckpointStatus.VALID
    assert CheckpointStatus.NOT_REACHED != CheckpointStatus.UNKNOWN
    assert CheckpointStatus.NOT_REACHED != CheckpointStatus.INVALID


def test_checkpoint_fingerprint_determinism():
    """Verifies SHA-256 fingerprint computation is strictly deterministic across runs."""
    args = dict(
        transaction_id="tx_test_123",
        checkpoint_type=CheckpointType.INTENT_AUTHORIZED.value,
        sequence=1,
        lifecycle_stage=LifecycleStage.INTENT.value,
        status=CheckpointStatus.VALID.value,
        verified_fields=["currency", "intent_id", "max_total"],
        evidence_refs=["ev_intent_1"],
        integrity_decision="PASS",
        binding_decision="VALID",
        execution_state="RUNNING",
        missing_evidence=[],
        findings=["Intent authorized within policy limits"],
        governance_version="gov_v1.0.0",
        previous_checkpoint_fingerprint=None,
        reproducibility_reference="replay_test_ref",
    )

    fp1 = compute_checkpoint_fingerprint(**args)
    fp2 = compute_checkpoint_fingerprint(**args)
    assert fp1 == fp2
    assert len(fp1) == 64  # SHA-256 hex


def test_checkpoint_fingerprint_sensitivity():
    """Verifies that altering any field changes the computed fingerprint."""
    base_args = dict(
        transaction_id="tx_test_123",
        checkpoint_type=CheckpointType.INTENT_AUTHORIZED.value,
        sequence=1,
        lifecycle_stage=LifecycleStage.INTENT.value,
        status=CheckpointStatus.VALID.value,
        verified_fields=["currency", "intent_id", "max_total"],
        evidence_refs=["ev_intent_1"],
        integrity_decision="PASS",
        binding_decision="VALID",
        execution_state="RUNNING",
        missing_evidence=[],
        findings=["Intent authorized within policy limits"],
        governance_version="gov_v1.0.0",
        previous_checkpoint_fingerprint=None,
        reproducibility_reference="replay_test_ref",
    )
    base_fp = compute_checkpoint_fingerprint(**base_args)

    # 1. Alter status
    args_diff_status = base_args.copy()
    args_diff_status["status"] = "INVALID"
    assert compute_checkpoint_fingerprint(**args_diff_status) != base_fp

    # 2. Alter evidence_refs
    args_diff_ev = base_args.copy()
    args_diff_ev["evidence_refs"] = ["ev_intent_2"]
    assert compute_checkpoint_fingerprint(**args_diff_ev) != base_fp

    # 3. Alter integrity_decision
    args_diff_dec = base_args.copy()
    args_diff_dec["integrity_decision"] = "DRIFT"
    assert compute_checkpoint_fingerprint(**args_diff_dec) != base_fp


def test_checkpoint_model_validation_and_immutability():
    """Verifies IntegrityCheckpoint immutability, field validation, and fingerprint verification."""
    dt = datetime.now(timezone.utc)
    fp = compute_checkpoint_fingerprint(
        transaction_id="tx_123",
        checkpoint_type=CheckpointType.INTENT_AUTHORIZED.value,
        sequence=1,
        lifecycle_stage=LifecycleStage.INTENT.value,
        status=CheckpointStatus.VALID.value,
        verified_fields=["intent_id"],
        evidence_refs=["ev_1"],
        integrity_decision="PASS",
        binding_decision="VALID",
        execution_state="RUNNING",
        missing_evidence=[],
        findings=["Valid"],
        governance_version="gov_v1.0.0",
    )

    cp = IntegrityCheckpoint(
        checkpoint_id="cp_1",
        transaction_id="tx_123",
        checkpoint_type=CheckpointType.INTENT_AUTHORIZED,
        sequence=1,
        lifecycle_stage=LifecycleStage.INTENT,
        status=CheckpointStatus.VALID,
        verified_fields=["intent_id"],
        evidence_refs=["ev_1"],
        integrity_decision=IntegrityStatus.PASS,
        binding_decision="VALID",
        execution_state=KillSwitchState.RUNNING,
        missing_evidence=[],
        findings=["Valid"],
        governance_version="gov_v1.0.0",
        fingerprint=fp,
        created_at=dt,
    )

    assert cp.verify_fingerprint() is True

    # Immutability: frozen model
    with pytest.raises(ValidationError):
        cp.status = CheckpointStatus.INVALID  # type: ignore

    # Sequence out of bounds
    with pytest.raises(ValidationError):
        IntegrityCheckpoint(
            checkpoint_id="cp_bad",
            transaction_id="tx_123",
            checkpoint_type=CheckpointType.INTENT_AUTHORIZED,
            sequence=9,  # invalid sequence > 8
            lifecycle_stage=LifecycleStage.INTENT,
            status=CheckpointStatus.VALID,
            integrity_decision=IntegrityStatus.PASS,
            execution_state=KillSwitchState.RUNNING,
            fingerprint="fake",
            created_at=dt,
        )


def test_verify_checkpoint_chain_valid():
    """Verifies a correctly chained sequence of checkpoints passes validation."""
    dt = datetime.now(timezone.utc)

    # Checkpoint 1
    fp1 = compute_checkpoint_fingerprint(
        transaction_id="tx_1",
        checkpoint_type=CheckpointType.INTENT_AUTHORIZED.value,
        sequence=1,
        lifecycle_stage=LifecycleStage.INTENT.value,
        status=CheckpointStatus.VALID.value,
        verified_fields=["intent_id"],
        evidence_refs=["ev_1"],
        integrity_decision="PASS",
        binding_decision="VALID",
        execution_state="RUNNING",
        missing_evidence=[],
        findings=["Intent valid"],
        governance_version="gov_v1.0.0",
    )
    cp1 = IntegrityCheckpoint(
        checkpoint_id="cp_1",
        transaction_id="tx_1",
        checkpoint_type=CheckpointType.INTENT_AUTHORIZED,
        sequence=1,
        lifecycle_stage=LifecycleStage.INTENT,
        status=CheckpointStatus.VALID,
        verified_fields=["intent_id"],
        evidence_refs=["ev_1"],
        integrity_decision=IntegrityStatus.PASS,
        binding_decision="VALID",
        execution_state=KillSwitchState.RUNNING,
        findings=["Intent valid"],
        fingerprint=fp1,
        created_at=dt,
    )

    # Checkpoint 2 (links to Checkpoint 1)
    fp2 = compute_checkpoint_fingerprint(
        transaction_id="tx_1",
        checkpoint_type=CheckpointType.AGENT_ACTION_AUTHORIZED.value,
        sequence=2,
        lifecycle_stage=LifecycleStage.AGENT.value,
        status=CheckpointStatus.VALID.value,
        verified_fields=["agent_id"],
        evidence_refs=["ev_2"],
        integrity_decision="PASS",
        binding_decision="VALID",
        execution_state="RUNNING",
        missing_evidence=[],
        findings=["Agent valid"],
        governance_version="gov_v1.0.0",
        previous_checkpoint_fingerprint=fp1,
    )
    cp2 = IntegrityCheckpoint(
        checkpoint_id="cp_2",
        transaction_id="tx_1",
        checkpoint_type=CheckpointType.AGENT_ACTION_AUTHORIZED,
        sequence=2,
        lifecycle_stage=LifecycleStage.AGENT,
        status=CheckpointStatus.VALID,
        verified_fields=["agent_id"],
        evidence_refs=["ev_2"],
        integrity_decision=IntegrityStatus.PASS,
        binding_decision="VALID",
        execution_state=KillSwitchState.RUNNING,
        findings=["Agent valid"],
        previous_checkpoint_id="cp_1",
        previous_checkpoint_fingerprint=fp1,
        fingerprint=fp2,
        created_at=dt,
    )

    result = verify_checkpoint_chain([cp1, cp2])
    assert result.is_valid is True
    assert len(result.violations) == 0
    assert result.verified_count == 2


def test_verify_checkpoint_chain_detects_violations():
    """Verifies detection of gap, duplicate sequence, and tampered previous hash."""
    dt = datetime.now(timezone.utc)

    fp1 = compute_checkpoint_fingerprint(
        transaction_id="tx_1",
        checkpoint_type=CheckpointType.INTENT_AUTHORIZED.value,
        sequence=1,
        lifecycle_stage=LifecycleStage.INTENT.value,
        status=CheckpointStatus.VALID.value,
        verified_fields=["intent_id"],
        evidence_refs=[],
        integrity_decision="PASS",
        binding_decision="VALID",
        execution_state="RUNNING",
        missing_evidence=[],
        findings=[],
        governance_version="gov_v1.0.0",
    )
    cp1 = IntegrityCheckpoint(
        checkpoint_id="cp_1",
        transaction_id="tx_1",
        checkpoint_type=CheckpointType.INTENT_AUTHORIZED,
        sequence=1,
        lifecycle_stage=LifecycleStage.INTENT,
        status=CheckpointStatus.VALID,
        integrity_decision=IntegrityStatus.PASS,
        execution_state=KillSwitchState.RUNNING,
        fingerprint=fp1,
        created_at=dt,
    )

    # Gap: sequence 3 without sequence 2
    fp3 = compute_checkpoint_fingerprint(
        transaction_id="tx_1",
        checkpoint_type=CheckpointType.MERCHANT_OFFER_VERIFIED.value,
        sequence=3,
        lifecycle_stage=LifecycleStage.MERCHANT.value,
        status=CheckpointStatus.VALID.value,
        verified_fields=["merchant_id"],
        evidence_refs=[],
        integrity_decision="PASS",
        binding_decision="VALID",
        execution_state="RUNNING",
        missing_evidence=[],
        findings=[],
        governance_version="gov_v1.0.0",
        previous_checkpoint_fingerprint=fp1,
    )
    cp3_gap = IntegrityCheckpoint(
        checkpoint_id="cp_3",
        transaction_id="tx_1",
        checkpoint_type=CheckpointType.MERCHANT_OFFER_VERIFIED,
        sequence=3,
        lifecycle_stage=LifecycleStage.MERCHANT,
        status=CheckpointStatus.VALID,
        integrity_decision=IntegrityStatus.PASS,
        execution_state=KillSwitchState.RUNNING,
        previous_checkpoint_id="cp_1",
        previous_checkpoint_fingerprint=fp1,
        fingerprint=fp3,
        created_at=dt,
    )

    result_gap = verify_checkpoint_chain([cp1, cp3_gap])
    assert result_gap.is_valid is False
    assert any("gap or reordering" in v for v in result_gap.violations)
