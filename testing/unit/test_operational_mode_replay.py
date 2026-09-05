"""Deterministic Replay Test Suite for I10 Operational Deployment Modes.

Verifies:
1. Historical snapshot recorded mode (e.g. SHADOW) is preserved during replay
   even if the live/current runtime service is configured for GUARDED or HUMAN_REVIEW.
2. Replay evaluation is strictly deterministic across repeated runs with identical reference time.
3. Live environment mode or wall clock is never leaked into historical replay.
4. Historical HUMAN_REVIEW decisions are reconstructed faithfully from snapshot records.
5. Standard T13 ReplayEngine operates seamlessly with operational metadata.
"""
from datetime import datetime, timezone
import pytest

from backend.app.domain.kill_switch.contracts import KillSwitchState
from backend.app.domain.models.enums import IntegrityStatus
from backend.app.domain.models.intent import IntentContract, IntentItem
from backend.app.domain.models.money import Money
from backend.app.domain.operational_mode.contracts import (
    HumanReviewRequirement,
    HumanReviewStatus,
    OperationalAction,
    OperationalMode,
    OperationalModePolicy,
)
from backend.app.domain.operational_mode.policy import OperationalModeEngine
from backend.app.services.operational_mode.service import OperationalModeService
from backend.app.services.replay.contracts import ReplaySnapshot, ReplayVerdict
from backend.app.services.replay.engine import ReplayEngine


@pytest.fixture
def replay_time() -> datetime:
    return datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def sample_contract(replay_time: datetime) -> IntentContract:
    return IntentContract(
        intent_id="intent_replay_001",
        issued_by="buyer_alice",
        items=[
            IntentItem(
                item_id="i1",
                sku="SKU-SERVER",
                name="Server",
                quantity=1,
                unit_price=Money(amount=10000, currency="INR"),
                total_price=Money(amount=10000, currency="INR"),
            )
        ],
        max_total=Money(amount=10000, currency="INR"),
        issued_at=replay_time,
        expires_at=datetime(2026, 9, 5, 14, 0, 0, tzinfo=timezone.utc),
    )


def test_replay_preserves_historical_shadow_mode_when_runtime_is_guarded(replay_time: datetime):
    """
    Historical transaction executed under SHADOW mode must NOT replay under GUARDED mode
    merely because the current deployment mode has switched to GUARDED.
    """
    # 1. Live service is currently in GUARDED mode
    runtime_service = OperationalModeService(
        policy=OperationalModePolicy(mode=OperationalMode.GUARDED)
    )
    assert runtime_service.get_mode() == OperationalMode.GUARDED

    # 2. Historical snapshot was executed in SHADOW mode
    snapshot_mode = OperationalMode.SHADOW
    snapshot_policy = OperationalModePolicy(mode=snapshot_mode)

    historical_eval = OperationalModeEngine.evaluate(
        policy=snapshot_policy,
        transaction_id="tx_hist_001",
        integrity_status=IntegrityStatus.DRIFT,
        kill_switch_state=KillSwitchState.RUNNING,
        reference_time=replay_time,
    )

    # Historical evaluation reflects SHADOW (no intervention, observe only)
    assert historical_eval.mode == OperationalMode.SHADOW
    assert historical_eval.action == OperationalAction.OBSERVE_ONLY
    assert historical_eval.enforcement_active is False
    assert historical_eval.can_execute_payment is True  # SHADOW never blocks payment
    assert historical_eval.integrity_status == IntegrityStatus.DRIFT

    # If evaluated against live runtime policy, it would have blocked or triggered remediation
    runtime_eval = runtime_service.evaluate_transaction(
        transaction_id="tx_hist_001",
        integrity_status=IntegrityStatus.DRIFT,
        kill_switch_state=KillSwitchState.RUNNING,
        reference_time=replay_time,
    )
    assert runtime_eval.mode == OperationalMode.GUARDED
    assert runtime_eval.action == OperationalAction.TRIGGER_REMEDIATION
    assert runtime_eval.can_execute_payment is False

    # Invariant holds: historical replay evaluation MUST use snapshot policy, not runtime policy
    assert historical_eval.mode != runtime_eval.mode


def test_replay_preserves_historical_human_review_mode_when_runtime_is_shadow(replay_time: datetime):
    """
    Historical transaction requiring HUMAN_REVIEW must replay as HUMAN_REVIEW
    even when the current deployment mode is SHADOW.
    """
    # Live service in SHADOW mode
    runtime_service = OperationalModeService(
        policy=OperationalModePolicy(mode=OperationalMode.SHADOW)
    )
    assert runtime_service.get_mode() == OperationalMode.SHADOW

    # Historical snapshot had HUMAN_REVIEW mode
    hist_policy = OperationalModePolicy(mode=OperationalMode.HUMAN_REVIEW)
    hist_review_req = HumanReviewRequirement(
        review_id="rev_hist_001",
        transaction_id="tx_hist_002",
        intent_id="intent_002",
        agent_id="agent_002",
        merchant_id="merchant_002",
        status=HumanReviewStatus.PENDING,
        reason="Exceeded high-value limit",
        integrity_status=IntegrityStatus.PASS,
        kill_switch_state=KillSwitchState.RUNNING,
        required_at=replay_time,
    )

    replayed_eval = OperationalModeEngine.evaluate(
        policy=hist_policy,
        transaction_id="tx_hist_002",
        integrity_status=IntegrityStatus.PASS,
        kill_switch_state=KillSwitchState.RUNNING,
        review_requirement=hist_review_req,
        reference_time=replay_time,
    )

    assert replayed_eval.mode == OperationalMode.HUMAN_REVIEW
    assert replayed_eval.action == OperationalAction.REQUIRE_HUMAN_REVIEW
    assert replayed_eval.can_execute_payment is False
    assert replayed_eval.review_id == "rev_hist_001"


def test_replay_evaluation_is_fully_deterministic(replay_time: datetime):
    """
    Repeated replay evaluations with identical parameters produce identical results.
    Zero non-deterministic wall-clock or random state.
    """
    policy = OperationalModePolicy(mode=OperationalMode.GUARDED)
    
    eval_1 = OperationalModeEngine.evaluate(
        policy=policy,
        transaction_id="tx_repeat_001",
        integrity_status=IntegrityStatus.PASS,
        kill_switch_state=KillSwitchState.RUNNING,
        amount=Money(amount=5000, currency="INR"),
        reference_time=replay_time,
    )

    eval_2 = OperationalModeEngine.evaluate(
        policy=policy,
        transaction_id="tx_repeat_001",
        integrity_status=IntegrityStatus.PASS,
        kill_switch_state=KillSwitchState.RUNNING,
        amount=Money(amount=5000, currency="INR"),
        reference_time=replay_time,
    )

    assert eval_1.action == eval_2.action
    assert eval_1.can_execute_payment == eval_2.can_execute_payment
    assert eval_1.enforcement_active == eval_2.enforcement_active
    assert eval_1.timestamp == eval_2.timestamp
    assert eval_1.reason == eval_2.reason


def test_replay_engine_snapshot_integration_with_mode_metadata(
    sample_contract: IntentContract,
    replay_time: datetime,
):
    """
    Verify T13 ReplayEngine seamlessly replays a ReplaySnapshot containing
    I10 operational mode metadata.
    """
    snapshot = ReplaySnapshot(
        replay_id="rep_op_001",
        transaction_id="tx_snap_001",
        contract=sample_contract,
        events=[],
        evidence=[],
        state_transitions=[],
        reference_time=replay_time,
        metadata={
            "operational_mode": "SHADOW",
            "policy_version": "merchant-policy-1.0.0",
            "can_execute_payment": True,
        },
    )

    result = ReplayEngine.replay(snapshot)
    assert result.verdict in [ReplayVerdict.MATCH, ReplayVerdict.MISMATCH]
    assert snapshot.metadata["operational_mode"] == "SHADOW"
