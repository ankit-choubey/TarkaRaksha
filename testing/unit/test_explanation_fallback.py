"""Unit tests for I21 Deterministic Explanation Fallback Generator."""
from datetime import datetime, timezone
import pytest

from backend.app.domain.explanation.contracts import (
    EvidenceReference,
    ExplanationContext,
)
from backend.app.domain.explanation.fallback import build_deterministic_fallback
from backend.app.domain.kill_switch.contracts import KillSwitchState, KillTrigger
from backend.app.domain.models.enums import EvidenceAuthority, EvidenceSource, IntegrityStatus


def test_fallback_generates_grounded_pass_explanation():
    now = datetime.now(timezone.utc)
    ev_amt = EvidenceReference(
        evidence_id="ev_amt_01",
        field_name="amount",
        source=EvidenceSource.RAZORPAY,
        authority=EvidenceAuthority.AUTHORITATIVE,
        observed_value=50000,
        expected_value=50000,
        is_authoritative=True,
    )
    ctx = ExplanationContext(
        context_id="ctx_p1",
        transaction_id="tx_p1",
        intent_id="intent_p1",
        deterministic_decision=IntegrityStatus.PASS,
        decision_reason="All rules passed",
        kill_switch_state=KillSwitchState.RUNNING,
        evidence_references=[ev_amt],
        created_at=now,
    )

    res = build_deterministic_fallback(ctx, fallback_reason="LLM timeout")
    assert res.is_fallback is True
    assert res.deterministic_decision == IntegrityStatus.PASS
    assert res.execution_state == KillSwitchState.RUNNING
    assert "PASSED" in res.summary
    assert len(res.claims) == 1
    assert res.claims[0].evidence_refs == ["ev_amt_01"]
    assert res.validation_result.is_valid is True
    assert res.model_metadata["engine"] == "deterministic_fallback"
    assert res.model_metadata["reason"] == "LLM timeout"


def test_fallback_generates_drift_and_killed_explanation():
    now = datetime.now(timezone.utc)
    ev_amt = EvidenceReference(
        evidence_id="ev_amt_drift",
        field_name="amount",
        source=EvidenceSource.RAZORPAY,
        authority=EvidenceAuthority.AUTHORITATIVE,
        observed_value=75000,
        expected_value=50000,
        is_authoritative=True,
    )
    ctx = ExplanationContext(
        context_id="ctx_d1",
        transaction_id="tx_d1",
        intent_id="intent_d1",
        deterministic_decision=IntegrityStatus.DRIFT,
        decision_reason="Amount exceeded authorized cap",
        kill_switch_state=KillSwitchState.KILLED,
        kill_switch_trigger=KillTrigger.CRITICAL_DRIFT,
        integrity_violations=["Observed 75000 exceeds cap 50000"],
        evidence_references=[ev_amt],
        created_at=now,
    )

    res = build_deterministic_fallback(ctx, fallback_reason="Rate limit exceeded")
    assert res.is_fallback is True
    assert res.deterministic_decision == IntegrityStatus.DRIFT
    assert res.execution_state == KillSwitchState.KILLED
    assert "diverged from authorized intent" in res.summary
    assert "Execution is terminated by the Kill Switch" in res.recommended_next_action
    assert len(res.mismatches) == 1
    assert res.claims[0].evidence_refs == ["ev_amt_drift"]
    assert res.validation_result.is_valid is True


def test_fallback_generates_unknown_and_revalidation_explanation():
    now = datetime.now(timezone.utc)
    ctx = ExplanationContext(
        context_id="ctx_u1",
        transaction_id="tx_u1",
        intent_id="intent_u1",
        deterministic_decision=IntegrityStatus.UNKNOWN,
        decision_reason="Payment capture missing",
        kill_switch_state=KillSwitchState.REQUIRES_REVALIDATION,
        kill_switch_trigger=KillTrigger.REPEATED_UNKNOWN,
        missing_evidence_fields=["authoritative_payment_capture_confirmation"],
        uncertainty_notes=["Payment status pending from Razorpay webhook"],
        created_at=now,
    )

    res = build_deterministic_fallback(ctx, fallback_reason="AI returned 503")
    assert res.is_fallback is True
    assert res.deterministic_decision == IntegrityStatus.UNKNOWN
    assert res.execution_state == KillSwitchState.REQUIRES_REVALIDATION
    assert "cannot be deterministically verified" in res.summary
    assert "authoritative_payment_capture_confirmation" in res.missing_evidence
    assert "Payment status pending from Razorpay webhook" in res.uncertainties
    assert "Execution is held pending revalidation" in res.recommended_next_action
    assert res.validation_result.is_valid is True
