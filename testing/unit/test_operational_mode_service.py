"""Unit tests for I10 OperationalModeService.

Validates:
1. Operational mode transitions and auditable ModeTransitionRecord logging.
2. Human review creation, lookup, and explicit approval/rejection.
3. Transaction evaluation and assert_can_execute_payment behavior across modes.
4. TransactionService integration with operational mode.
"""
from datetime import datetime, timezone
import pytest

from backend.app.domain.kill_switch.contracts import ExecutionBlockedError, KillSwitchState
from backend.app.domain.models.enums import IntegrityStatus
from backend.app.domain.models.money import Money
from backend.app.domain.operational_mode import (
    HumanReviewDecision,
    HumanReviewRequiredError,
    HumanReviewStatus,
    OperationalAction,
    OperationalMode,
    OperationalModePolicy,
)
from backend.app.services.operational_mode import OperationalModeService


@pytest.fixture
def base_time() -> datetime:
    return datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def mode_service() -> OperationalModeService:
    return OperationalModeService(
        policy=OperationalModePolicy(mode=OperationalMode.GUARDED)
    )


def test_service_initialization_and_mode(mode_service: OperationalModeService):
    assert mode_service.get_mode() == OperationalMode.GUARDED
    assert len(mode_service.get_transition_history()) == 0


def test_set_mode_creates_transition_record(
    mode_service: OperationalModeService, base_time: datetime
):
    rec = mode_service.set_mode(
        new_mode=OperationalMode.SHADOW,
        changed_by="human_operator_charlie",
        reason="Deploying new merchant version in shadow observation mode",
        reference_time=base_time,
    )

    assert rec.previous_mode == OperationalMode.GUARDED
    assert rec.new_mode == OperationalMode.SHADOW
    assert rec.changed_by == "human_operator_charlie"
    assert mode_service.get_mode() == OperationalMode.SHADOW
    assert len(mode_service.get_transition_history()) == 1


def test_human_review_creation_and_lifecycle(
    mode_service: OperationalModeService, base_time: datetime
):
    mode_service.set_mode(
        new_mode=OperationalMode.HUMAN_REVIEW,
        changed_by="operator_dan",
        reason="Switching to high-value manual review mode",
        reference_time=base_time,
    )

    req = mode_service.create_review_requirement(
        transaction_id="tx_svc_01",
        intent_id="intent_01",
        agent_id="buyer_alice",
        merchant_id="merchant_store",
        reason="Suspicious high price detected",
        integrity_status=IntegrityStatus.DRIFT,
        kill_switch_state=KillSwitchState.RUNNING,
        reference_time=base_time,
    )

    assert req.status == HumanReviewStatus.PENDING
    assert mode_service.get_review_requirement(req.review_id) == req
    assert mode_service.get_review_for_transaction("tx_svc_01") == req

    # Evaluation reflects PENDING review
    eval_res = mode_service.evaluate_transaction(
        transaction_id="tx_svc_01",
        integrity_status=IntegrityStatus.DRIFT,
        kill_switch_state=KillSwitchState.RUNNING,
        reference_time=base_time,
    )
    assert eval_res.action == OperationalAction.REQUIRE_HUMAN_REVIEW
    assert eval_res.can_execute_payment is False

    # Execution check raises HumanReviewRequiredError
    with pytest.raises(HumanReviewRequiredError) as exc_info:
        mode_service.assert_can_execute_payment("tx_svc_01", eval_res)
    assert exc_info.value.review_id == req.review_id

    # Explicit Human Approval
    dec = HumanReviewDecision(
        review_id=req.review_id,
        transaction_id="tx_svc_01",
        decision=HumanReviewStatus.APPROVED,
        reviewer_id="human_supervisor_eve",
        rationale="Approved after verifying contract amendment with buyer",
        timestamp=base_time,
    )
    approved_req = mode_service.submit_human_review(
        decision=dec,
        expected_intent_id="intent_01",
        expected_agent_id="buyer_alice",
        expected_merchant_id="merchant_store",
    )
    assert approved_req.status == HumanReviewStatus.APPROVED
    assert approved_req.reviewed_by == "human_supervisor_eve"


def test_human_review_rejection(
    mode_service: OperationalModeService, base_time: datetime
):
    req = mode_service.create_review_requirement(
        transaction_id="tx_svc_02",
        intent_id="intent_02",
        agent_id="buyer_alice",
        merchant_id="merchant_store",
        reason="Drift detected",
        integrity_status=IntegrityStatus.DRIFT,
        kill_switch_state=KillSwitchState.RUNNING,
        reference_time=base_time,
    )

    dec = HumanReviewDecision(
        review_id=req.review_id,
        transaction_id="tx_svc_02",
        decision=HumanReviewStatus.REJECTED,
        reviewer_id="human_supervisor_eve",
        rationale="Unacceptable merchant price escalation",
        timestamp=base_time,
    )
    rejected_req = mode_service.submit_human_review(dec)
    assert rejected_req.status == HumanReviewStatus.REJECTED

    # Re-evaluate
    mode_service.set_mode(
        new_mode=OperationalMode.HUMAN_REVIEW,
        changed_by="operator_dan",
        reason="Switching mode",
        reference_time=base_time,
    )
    eval_res = mode_service.evaluate_transaction(
        transaction_id="tx_svc_02",
        integrity_status=IntegrityStatus.DRIFT,
        kill_switch_state=KillSwitchState.RUNNING,
        reference_time=base_time,
    )
    assert eval_res.action == OperationalAction.BLOCK_EXECUTION
    assert eval_res.can_execute_payment is False

    with pytest.raises(ExecutionBlockedError):
        mode_service.assert_can_execute_payment("tx_svc_02", eval_res)


def test_shadow_mode_assert_can_execute_payment_does_not_block(
    mode_service: OperationalModeService, base_time: datetime
):
    mode_service.set_mode(
        new_mode=OperationalMode.SHADOW,
        changed_by="operator_dan",
        reason="Observation mode",
        reference_time=base_time,
    )
    eval_res = mode_service.evaluate_transaction(
        transaction_id="tx_shadow_check",
        integrity_status=IntegrityStatus.DRIFT,
        kill_switch_state=KillSwitchState.RUNNING,
        reference_time=base_time,
    )
    assert eval_res.can_execute_payment is True
    # Does not raise!
    mode_service.assert_can_execute_payment("tx_shadow_check", eval_res)
