"""Unit tests for I10 Operational Deployment Mode Contracts.

Validates:
1. OperationalMode enums (SHADOW, GUARDED, HUMAN_REVIEW).
2. OperationalModePolicy schema, defaults, immutability, and validation.
3. ModeTransitionRecord audit validation.
4. HumanReviewRequirement and HumanReviewDecision schemas and constraints.
5. OperationalEvaluationResult structure.
"""
from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from backend.app.domain.kill_switch.contracts import KillSwitchState
from backend.app.domain.models.enums import IntegrityStatus
from backend.app.domain.models.money import Money
from backend.app.domain.operational_mode import (
    HumanReviewDecision,
    HumanReviewRequirement,
    HumanReviewStatus,
    ModeTransitionRecord,
    OperationalAction,
    OperationalEvaluationResult,
    OperationalMode,
    OperationalModePolicy,
)


@pytest.fixture
def base_time() -> datetime:
    return datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)


def test_operational_modes_enum():
    assert OperationalMode.SHADOW == "SHADOW"
    assert OperationalMode.GUARDED == "GUARDED"
    assert OperationalMode.HUMAN_REVIEW == "HUMAN_REVIEW"
    assert len(OperationalMode) == 3


def test_operational_actions_enum():
    expected = {
        "ALLOW_EXECUTION",
        "BLOCK_EXECUTION",
        "OBSERVE_ONLY",
        "TRIGGER_REMEDIATION",
        "REQUIRE_HUMAN_REVIEW",
        "TRIGGER_SAFETY_CONTROL",
    }
    assert {a.value for a in OperationalAction} == expected


def test_human_review_status_enum():
    expected = {"NOT_REQUIRED", "PENDING", "APPROVED", "REJECTED"}
    assert {s.value for s in HumanReviewStatus} == expected


def test_policy_defaults_and_immutability():
    policy = OperationalModePolicy()
    assert policy.mode == OperationalMode.GUARDED
    assert policy.allow_shadow_remediation is False
    assert policy.guarded_auto_remediation is True
    assert policy.require_review_on_drift is True
    assert policy.require_review_on_unknown is True
    assert policy.require_review_on_kill is True

    # Immutability
    with pytest.raises(ValidationError):
        policy.mode = OperationalMode.SHADOW  # type: ignore

    # Extra fields forbidden
    with pytest.raises(ValidationError):
        OperationalModePolicy(mode=OperationalMode.SHADOW, extra_key="invalid")  # type: ignore


def test_policy_empty_version_rejected():
    with pytest.raises(ValidationError):
        OperationalModePolicy(rules_version="   ")

    with pytest.raises(ValidationError):
        OperationalModePolicy(policy_version="")


def test_mode_transition_record(base_time: datetime):
    rec = ModeTransitionRecord(
        record_id="rec_001",
        previous_mode=OperationalMode.SHADOW,
        new_mode=OperationalMode.GUARDED,
        reason="Promoting from shadow observation to guarded enforcement",
        changed_by="admin_operator",
        timestamp=base_time,
        policy_version="merchant-policy-1.0.0",
    )

    assert rec.record_id == "rec_001"
    assert rec.previous_mode == OperationalMode.SHADOW
    assert rec.new_mode == OperationalMode.GUARDED

    # Immutability
    with pytest.raises(ValidationError):
        rec.new_mode = OperationalMode.HUMAN_REVIEW  # type: ignore

    # Naive timestamp rejected
    with pytest.raises(ValidationError):
        ModeTransitionRecord(
            record_id="rec_002",
            previous_mode=OperationalMode.SHADOW,
            new_mode=OperationalMode.GUARDED,
            reason="test",
            changed_by="admin",
            timestamp=datetime(2026, 9, 5, 12, 0, 0),  # naive
            policy_version="1.0.0",
        )


def test_human_review_requirement_schema(base_time: datetime):
    req = HumanReviewRequirement(
        review_id="rev_001",
        transaction_id="tx_001",
        intent_id="intent_001",
        agent_id="buyer_alice",
        merchant_id="merchant_store",
        status=HumanReviewStatus.PENDING,
        reason="Drift detected on unit price",
        integrity_status=IntegrityStatus.DRIFT,
        kill_switch_state=KillSwitchState.RUNNING,
        required_at=base_time,
        revalidation_required=True,
    )

    assert req.review_id == "rev_001"
    assert req.status == HumanReviewStatus.PENDING
    assert req.revalidation_required is True

    # Empty IDs rejected
    with pytest.raises(ValidationError):
        HumanReviewRequirement(
            review_id="",
            transaction_id="tx_001",
            intent_id="intent_001",
            agent_id="buyer_alice",
            merchant_id="merchant_store",
            reason="reason",
            integrity_status=IntegrityStatus.DRIFT,
            kill_switch_state=KillSwitchState.RUNNING,
            required_at=base_time,
        )


def test_human_review_decision_schema(base_time: datetime):
    dec = HumanReviewDecision(
        review_id="rev_001",
        transaction_id="tx_001",
        decision=HumanReviewStatus.APPROVED,
        reviewer_id="human_operator_1",
        rationale="Price increase authorized by senior risk manager",
        timestamp=base_time,
    )

    assert dec.decision == HumanReviewStatus.APPROVED
    assert dec.reviewer_id == "human_operator_1"

    # Invalid decision status (e.g. PENDING or NOT_REQUIRED) rejected
    with pytest.raises(ValidationError):
        HumanReviewDecision(
            review_id="rev_001",
            transaction_id="tx_001",
            decision=HumanReviewStatus.PENDING,  # not an approval or rejection
            reviewer_id="human_1",
            rationale="waiting",
            timestamp=base_time,
        )


def test_operational_evaluation_result(base_time: datetime):
    res = OperationalEvaluationResult(
        evaluation_id="eval_001",
        transaction_id="tx_001",
        mode=OperationalMode.GUARDED,
        action=OperationalAction.ALLOW_EXECUTION,
        integrity_status=IntegrityStatus.PASS,
        kill_switch_state=KillSwitchState.RUNNING,
        human_review_status=HumanReviewStatus.NOT_REQUIRED,
        enforcement_active=True,
        can_execute_payment=True,
        remediation_permitted=False,
        reason="Clean PASS",
        policy_version="merchant-policy-1.0.0",
        timestamp=base_time,
    )

    assert res.can_execute_payment is True
    assert res.enforcement_active is True
    assert res.action == OperationalAction.ALLOW_EXECUTION
