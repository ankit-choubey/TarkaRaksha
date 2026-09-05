"""Unit tests for I9 Kill Switch domain contracts."""
from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from backend.app.domain.kill_switch.contracts import (
    ExecutionBlockedError,
    ExecutionDecision,
    KillSwitchRecord,
    KillSwitchState,
    KillTrigger,
    RevalidationOutcome,
    RevalidationRequest,
    UnauthorizedResumeError,
)
from backend.app.domain.models.enums import EvidenceAuthority, EvidenceSource
from backend.app.domain.models.evidence import Evidence


def test_kill_switch_state_enum_values():
    assert KillSwitchState.RUNNING.value == "RUNNING"
    assert KillSwitchState.PAUSED.value == "PAUSED"
    assert KillSwitchState.REQUIRES_REVALIDATION.value == "REQUIRES_REVALIDATION"
    assert KillSwitchState.KILLED.value == "KILLED"


def test_kill_trigger_enum_values():
    assert KillTrigger.CRITICAL_DRIFT.value == "CRITICAL_DRIFT"
    assert KillTrigger.REPEATED_UNKNOWN.value == "REPEATED_UNKNOWN"
    assert KillTrigger.BINDING_VIOLATION.value == "BINDING_VIOLATION"
    assert KillTrigger.POLICY_VIOLATION.value == "POLICY_VIOLATION"
    assert KillTrigger.CAPABILITY_VIOLATION.value == "CAPABILITY_VIOLATION"
    assert KillTrigger.EXPIRED_AUTHORIZATION.value == "EXPIRED_AUTHORIZATION"
    assert KillTrigger.ATTEMPT_LIMIT_EXCEEDED.value == "ATTEMPT_LIMIT_EXCEEDED"
    assert KillTrigger.ADMINISTRATIVE_KILL.value == "ADMINISTRATIVE_KILL"


def test_kill_switch_record_validation():
    now = datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)
    rec = KillSwitchRecord(
        record_id="rec_1",
        transaction_id="tx_1",
        prior_state=KillSwitchState.RUNNING,
        resulting_state=KillSwitchState.KILLED,
        decision=ExecutionDecision.BLOCK,
        trigger=KillTrigger.CRITICAL_DRIFT,
        reason="Detected tampered payment evidence",
        triggered_by="CONTROL_PLANE",
        authority=EvidenceAuthority.AUTHORITATIVE,
        timestamp=now,
        details={"diff": 5000},
    )

    assert rec.record_id == "rec_1"
    assert rec.transaction_id == "tx_1"
    assert rec.prior_state == KillSwitchState.RUNNING
    assert rec.resulting_state == KillSwitchState.KILLED
    assert rec.decision == ExecutionDecision.BLOCK
    assert rec.trigger == KillTrigger.CRITICAL_DRIFT
    assert rec.timestamp == now

    # Immutability check
    with pytest.raises(ValidationError):
        rec.resulting_state = KillSwitchState.RUNNING  # type: ignore


def test_kill_switch_record_rejects_empty_fields():
    now = datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)
    with pytest.raises(ValidationError):
        KillSwitchRecord(
            record_id="",
            transaction_id="tx_1",
            prior_state=KillSwitchState.RUNNING,
            resulting_state=KillSwitchState.KILLED,
            decision=ExecutionDecision.BLOCK,
            reason="Some reason",
            timestamp=now,
        )


def test_kill_switch_record_rejects_naive_timestamp():
    naive = datetime(2026, 9, 5, 12, 0, 0)
    with pytest.raises(ValidationError):
        KillSwitchRecord(
            record_id="rec_1",
            transaction_id="tx_1",
            prior_state=KillSwitchState.RUNNING,
            resulting_state=KillSwitchState.KILLED,
            decision=ExecutionDecision.BLOCK,
            reason="Some reason",
            timestamp=naive,
        )


def test_revalidation_request_validation():
    now = datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)
    ev = Evidence(
        evidence_id="ev_rev_1",
        intent_id="intent_1",
        transaction_id="tx_1",
        source=EvidenceSource.RAZORPAY,
        authority=EvidenceAuthority.AUTHORITATIVE,
        field_name="payment_status",
        field_value="captured",
        observed_at=now,
        is_authoritative=True,
    )
    req = RevalidationRequest(
        request_id="req_1",
        transaction_id="tx_1",
        intent_id="intent_1",
        agent_id="agent_1",
        merchant_id="merch_1",
        actor="admin_alice",
        evidence=[ev],
        reason="Manual operator review with verified bank receipt",
        requested_at=now,
    )
    assert req.transaction_id == "tx_1"
    assert len(req.evidence) == 1

    # Disallow extra fields
    with pytest.raises(ValidationError):
        RevalidationRequest(
            request_id="req_1",
            transaction_id="tx_1",
            intent_id="intent_1",
            agent_id="agent_1",
            merchant_id="merch_1",
            actor="admin_alice",
            reason="reason",
            requested_at=now,
            unauthorized_field="malicious",  # type: ignore
        )


def test_execution_blocked_error_attributes():
    err = ExecutionBlockedError("Action blocked", state=KillSwitchState.KILLED, trigger=KillTrigger.CRITICAL_DRIFT)
    assert err.state == KillSwitchState.KILLED
    assert err.trigger == KillTrigger.CRITICAL_DRIFT
    assert str(err) == "Action blocked"
