"""
Unit test suite for TarkaRaksha Transaction State Machine (T05).
Covers:
- Full normal lifecycle: CREATED -> EXECUTING -> OBSERVING -> VERIFYING -> PASS
- DRIFT branching and recovery/resolution/revalidation lifecycle
- UNKNOWN branching and resolution/revalidation/abstain lifecycle
- Permitted vs. forbidden transition rejections
- State immutability on rejected transitions
- Direct consumption of T04 IntegrityResults
- Financial action invariant enforcement (UNKNOWN, DRIFT, ABSTAIN guards)
- Determinism across repeated executions
"""
from datetime import datetime, timezone, timedelta
import pytest

from backend.app.domain.models import (
     TransactionState,
     ActionType,
     IntegrityStatus,
     IntentContract,
     IntentItem,
     Money,
     IntegrityResult,
)
from backend.app.domain.states import (
    TransactionStateMachine,
    InvalidStateTransitionError,
    SafetyInvariantViolationError,
    can_transition,
    validate_transition,
)


@pytest.fixture
def base_intent() -> IntentContract:
    now = datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)
    return IntentContract(
        intent_id="intent-test-100",
        issued_by="user-bob",
        issued_at=now,
        expires_at=now + timedelta(minutes=15),
        currency="INR",
        max_total=Money(amount=500000, currency="INR"),  # ₹5,000.00
        items=[
            IntentItem(
                item_id="item-phone-1",
                sku="SKU-PHONE-1",
                name="Smartphone X",
                quantity=1,
                unit_price=Money(amount=500000, currency="INR"),
                total_price=Money(amount=500000, currency="INR"),
            )
        ],
    )


def test_normal_happy_lifecycle(base_intent: IntentContract):
    """
    Test standard progression:
    CREATED -> EXECUTING -> OBSERVING -> VERIFYING -> PASS
    """
    sm = TransactionStateMachine("tx_001", base_intent)
    assert sm.current_state == TransactionState.CREATED
    assert len(sm.history) == 0

    t0 = base_intent.issued_at
    t1 = t0 + timedelta(seconds=1)
    t2 = t0 + timedelta(seconds=2)
    t3 = t0 + timedelta(seconds=3)
    t4 = t0 + timedelta(seconds=4)

    # 1. CREATED -> EXECUTING
    rec1 = sm.transition_to(TransactionState.EXECUTING, "Execution started by agent", t1)
    assert sm.current_state == TransactionState.EXECUTING
    assert rec1.from_state == TransactionState.CREATED
    assert rec1.to_state == TransactionState.EXECUTING

    # 2. EXECUTING -> OBSERVING
    rec2 = sm.transition_to(TransactionState.OBSERVING, "Observation window opened", t2)
    assert sm.current_state == TransactionState.OBSERVING
    assert rec2.from_state == TransactionState.EXECUTING
    assert rec2.to_state == TransactionState.OBSERVING

    # 3. OBSERVING -> VERIFYING
    rec3 = sm.transition_to(TransactionState.VERIFYING, "Evidence collected, verifying", t3)
    assert sm.current_state == TransactionState.VERIFYING
    assert rec3.from_state == TransactionState.OBSERVING
    assert rec3.to_state == TransactionState.VERIFYING

    # 4. VERIFYING -> PASS (via apply_integrity_result)
    integrity_pass = IntegrityResult(
        evaluation_id="eval-001",
        intent_id=base_intent.intent_id,
        status=IntegrityStatus.PASS,
        evaluated_at=t4,
        rule_results={"economic": True, "semantic": True, "temporal": True},
        violations=[],
        evidence_ids=["ev_1"],
        confidence_score=1.0,
        explanation="All economic, semantic, and temporal invariants satisfied",
    )
    rec4 = sm.apply_integrity_result(integrity_pass, t4)
    assert sm.current_state == TransactionState.PASS
    assert rec4.from_state == TransactionState.VERIFYING
    assert rec4.to_state == TransactionState.PASS
    assert rec4.integrity_status == IntegrityStatus.PASS

    assert len(sm.history) == 4
    # In PASS state, capture within authorized limit is permitted
    sm.request_action(ActionType.CAPTURE, Money(amount=500000, currency="INR"))


def test_drift_and_recovery_revalidation_lifecycle(base_intent: IntentContract):
    """
    Test DRIFT progression:
    CREATED -> EXECUTING -> OBSERVING -> VERIFYING -> DRIFT -> RECOVERING -> REVALIDATING -> PASS
    """
    sm = TransactionStateMachine("tx_002", base_intent)
    t0 = base_intent.issued_at

    sm.transition_to(TransactionState.EXECUTING, "Agent executing", t0 + timedelta(seconds=1))
    sm.transition_to(TransactionState.OBSERVING, "Observing events", t0 + timedelta(seconds=2))
    sm.transition_to(TransactionState.VERIFYING, "Verifying bundle", t0 + timedelta(seconds=3))

    integrity_drift = IntegrityResult(
        evaluation_id="eval-drift-001",
        intent_id=base_intent.intent_id,
        status=IntegrityStatus.DRIFT,
        evaluated_at=t0 + timedelta(seconds=4),
        rule_results={"economic": False, "semantic": True, "temporal": True},
        violations=["Amount observed ₹50,001 exceeded authorized limit ₹50,000"],
        evidence_ids=["ev_razorpay_1"],
        confidence_score=1.0,
        explanation="Economic boundary drift detected",
    )
    sm.apply_integrity_result(integrity_drift, t0 + timedelta(seconds=4))
    assert sm.current_state == TransactionState.DRIFT

    # In DRIFT state, financial CAPTURE is strictly forbidden
    with pytest.raises(SafetyInvariantViolationError, match="strictly forbidden in DRIFT state"):
        sm.request_action(ActionType.CAPTURE, Money(amount=500000, currency="INR"))

    # Transition to RECOVERING
    sm.transition_to(TransactionState.RECOVERING, "Compensatory plan generated", t0 + timedelta(seconds=5))
    assert sm.current_state == TransactionState.RECOVERING

    # Transition to REVALIDATING
    sm.transition_to(TransactionState.REVALIDATING, "Revalidating compensatory plan", t0 + timedelta(seconds=6))
    assert sm.current_state == TransactionState.REVALIDATING

    # Revalidation succeeds -> PASS
    reval_pass = IntegrityResult(
        evaluation_id="eval-reval-001",
        intent_id=base_intent.intent_id,
        status=IntegrityStatus.PASS,
        evaluated_at=t0 + timedelta(seconds=7),
        rule_results={"economic": True, "semantic": True, "temporal": True},
        violations=[],
        evidence_ids=["ev_refund_1"],
        confidence_score=1.0,
        explanation="Compensatory refund verified, economic balance restored",
    )
    sm.apply_integrity_result(reval_pass, t0 + timedelta(seconds=7))
    assert sm.current_state == TransactionState.PASS


def test_unknown_and_resolution_lifecycle(base_intent: IntentContract):
    """
    Test UNKNOWN progression:
    VERIFYING -> UNKNOWN -> RESOLVING -> REVALIDATING -> PASS
    """
    sm = TransactionStateMachine("tx_003", base_intent)
    t0 = base_intent.issued_at

    sm.transition_to(TransactionState.EXECUTING, "Executing", t0 + timedelta(seconds=1))
    sm.transition_to(TransactionState.OBSERVING, "Observing", t0 + timedelta(seconds=2))
    sm.transition_to(TransactionState.VERIFYING, "Verifying", t0 + timedelta(seconds=3))

    integrity_unknown = IntegrityResult(
        evaluation_id="eval-unk-001",
        intent_id=base_intent.intent_id,
        status=IntegrityStatus.UNKNOWN,
        evaluated_at=t0 + timedelta(seconds=4),
        rule_results={"economic": True, "semantic": True, "temporal": False},
        violations=["Razorpay payment event delayed, gateway status missing"],
        evidence_ids=[],
        confidence_score=0.5,
        explanation="Missing gateway capture record",
    )
    sm.apply_integrity_result(integrity_unknown, t0 + timedelta(seconds=4))
    assert sm.current_state == TransactionState.UNKNOWN

    # Invariant A: In UNKNOWN state, no financial action is allowed
    with pytest.raises(SafetyInvariantViolationError, match="strictly forbidden while in UNKNOWN state"):
        sm.request_action(ActionType.CAPTURE, Money(amount=500000, currency="INR"))

    # Transition to RESOLVING
    sm.transition_to(TransactionState.RESOLVING, "Polling gateway for authoritative status", t0 + timedelta(seconds=5))
    assert sm.current_state == TransactionState.RESOLVING

    # Transition to REVALIDATING
    sm.transition_to(TransactionState.REVALIDATING, "Re-verifying with polled gateway evidence", t0 + timedelta(seconds=6))
    assert sm.current_state == TransactionState.REVALIDATING

    # Successfully revalidated
    reval_pass = IntegrityResult(
        evaluation_id="eval-reval-002",
        intent_id=base_intent.intent_id,
        status=IntegrityStatus.PASS,
        evaluated_at=t0 + timedelta(seconds=7),
        rule_results={"economic": True, "semantic": True, "temporal": True},
        violations=[],
        evidence_ids=["ev_polled_1"],
        confidence_score=1.0,
        explanation="Gateway confirmed captured payment exactly matching intent",
    )
    sm.apply_integrity_result(reval_pass, t0 + timedelta(seconds=7))
    assert sm.current_state == TransactionState.PASS


def test_unknown_to_abstain_lifecycle(base_intent: IntentContract):
    """
    Test UNKNOWN resolution failure leading to ABSTAIN:
    UNKNOWN -> RESOLVING -> ABSTAIN
    """
    sm = TransactionStateMachine("tx_004", base_intent)
    t0 = base_intent.issued_at

    sm.transition_to(TransactionState.EXECUTING, "Executing", t0 + timedelta(seconds=1))
    sm.transition_to(TransactionState.OBSERVING, "Observing", t0 + timedelta(seconds=2))
    sm.transition_to(TransactionState.VERIFYING, "Verifying", t0 + timedelta(seconds=3))
    sm.transition_to(TransactionState.UNKNOWN, "Gateway timed out", t0 + timedelta(seconds=4))

    # UNKNOWN can also transition directly to ABSTAIN if resolution is unviable
    assert sm.can_transition_to(TransactionState.ABSTAIN)
    assert sm.can_transition_to(TransactionState.RESOLVING)

    sm.transition_to(TransactionState.RESOLVING, "Investigation started", t0 + timedelta(seconds=5))
    sm.transition_to(TransactionState.ABSTAIN, "Gateway unreachable, abstaining", t0 + timedelta(seconds=6))
    assert sm.current_state == TransactionState.ABSTAIN

    # In ABSTAIN state, financial actions are permanently blocked
    with pytest.raises(SafetyInvariantViolationError, match="permanently blocked in ABSTAIN state"):
        sm.request_action(ActionType.CAPTURE, Money(amount=500000, currency="INR"))

    # ABSTAIN is terminal; cannot transition anywhere
    assert not sm.can_transition_to(TransactionState.PASS)
    assert not sm.can_transition_to(TransactionState.EXECUTING)
    with pytest.raises(InvalidStateTransitionError):
        sm.transition_to(TransactionState.PASS, "Forced pass", t0 + timedelta(seconds=7))


def test_invalid_forbidden_transitions(base_intent: IntentContract):
    """
    Test specific forbidden transitions identified in architecture:
    - PASS -> EXECUTING
    - ABSTAIN -> CAPTURE
    - CREATED -> PASS
    - VERIFYING -> EXECUTING
    - Self-transitions
    """
    sm = TransactionStateMachine("tx_005", base_intent)
    t0 = base_intent.issued_at

    # Cannot jump CREATED -> PASS
    assert not sm.can_transition_to(TransactionState.PASS)
    with pytest.raises(InvalidStateTransitionError):
        sm.transition_to(TransactionState.PASS, "Illegal shortcut", t0 + timedelta(seconds=1))

    # Cannot self-transition CREATED -> CREATED
    with pytest.raises(InvalidStateTransitionError, match="Self-transitions are disallowed"):
        sm.transition_to(TransactionState.CREATED, "Self transition", t0 + timedelta(seconds=1))

    # Normal advance to PASS
    sm.transition_to(TransactionState.EXECUTING, "Executing", t0 + timedelta(seconds=1))
    sm.transition_to(TransactionState.OBSERVING, "Observing", t0 + timedelta(seconds=2))
    sm.transition_to(TransactionState.VERIFYING, "Verifying", t0 + timedelta(seconds=3))
    sm.transition_to(TransactionState.PASS, "Passed", t0 + timedelta(seconds=4))

    # PASS -> EXECUTING is forbidden
    assert not sm.can_transition_to(TransactionState.EXECUTING)
    with pytest.raises(InvalidStateTransitionError):
        sm.transition_to(TransactionState.EXECUTING, "Re-executing after PASS", t0 + timedelta(seconds=5))


def test_state_immutability_on_rejected_transition(base_intent: IntentContract):
    """
    Verify that when a transition is rejected, the current state and transition history
    remain completely unchanged (atomic).
    """
    sm = TransactionStateMachine("tx_006", base_intent)
    t0 = base_intent.issued_at

    sm.transition_to(TransactionState.EXECUTING, "Valid start", t0 + timedelta(seconds=1))
    assert sm.current_state == TransactionState.EXECUTING
    assert len(sm.history) == 1

    # Attempt illegal jump EXECUTING -> PASS
    with pytest.raises(InvalidStateTransitionError):
        sm.transition_to(TransactionState.PASS, "Illegal jump", t0 + timedelta(seconds=2))

    # State and history MUST remain untouched
    assert sm.current_state == TransactionState.EXECUTING
    assert len(sm.history) == 1
    assert sm.history[0].to_state == TransactionState.EXECUTING


def test_intent_immutability_preservation(base_intent: IntentContract):
    """
    Invariant C: Verify that state machine transitions do not mutate original IntentContract.
    """
    sm = TransactionStateMachine("tx_007", base_intent)
    t0 = base_intent.issued_at

    sm.transition_to(TransactionState.EXECUTING, "Executing", t0 + timedelta(seconds=1))
    sm.transition_to(TransactionState.OBSERVING, "Observing", t0 + timedelta(seconds=2))
    sm.transition_to(TransactionState.VERIFYING, "Verifying", t0 + timedelta(seconds=3))
    sm.transition_to(TransactionState.DRIFT, "Drift detected", t0 + timedelta(seconds=4))
    sm.transition_to(TransactionState.RECOVERING, "Recovering", t0 + timedelta(seconds=5))

    # Original intent contract constraints must remain exactly identical
    sm.verify_intent_immutability(base_intent)
    assert sm.intent.max_total.amount == 500000
    assert sm.intent.items[0].sku == "SKU-PHONE-1"


def test_excessive_financial_action_rejected(base_intent: IntentContract):
    """
    Verify that even in PASS state, financial actions exceeding authorized limits
    or currency mismatch are rejected.
    """
    sm = TransactionStateMachine("tx_008", base_intent)
    t0 = base_intent.issued_at

    sm.transition_to(TransactionState.EXECUTING, "Executing", t0 + timedelta(seconds=1))
    sm.transition_to(TransactionState.OBSERVING, "Observing", t0 + timedelta(seconds=2))
    sm.transition_to(TransactionState.VERIFYING, "Verifying", t0 + timedelta(seconds=3))
    sm.transition_to(TransactionState.PASS, "Passed", t0 + timedelta(seconds=4))

    # Action amount 500001 exceeds authorized 500000
    with pytest.raises(SafetyInvariantViolationError, match="exceeds authorized intent maximum"):
        sm.request_action(ActionType.CAPTURE, Money(amount=500001, currency="INR"))

    # Currency mismatch
    with pytest.raises(SafetyInvariantViolationError, match="Currency mismatch"):
        sm.request_action(ActionType.CAPTURE, Money(amount=500000, currency="USD"))


def test_apply_integrity_result_from_invalid_state_rejected(base_intent: IntentContract):
    """
    apply_integrity_result can only be invoked from VERIFYING or REVALIDATING.
    """
    sm = TransactionStateMachine("tx_009", base_intent)
    t0 = base_intent.issued_at

    # Currently in CREATED
    result = IntegrityResult(
        evaluation_id="eval-invalid-state",
        intent_id=base_intent.intent_id,
        status=IntegrityStatus.PASS,
        evaluated_at=t0 + timedelta(seconds=1),
        rule_results={"economic": True},
        violations=[],
        evidence_ids=[],
        confidence_score=1.0,
        explanation="Premature check",
    )
    with pytest.raises(InvalidStateTransitionError, match="Must be in VERIFYING or REVALIDATING"):
        sm.apply_integrity_result(result, t0 + timedelta(seconds=1))


def test_state_machine_determinism(base_intent: IntentContract):
    """
    Assert that identical transition steps yield identical states and history structures.
    """
    t0 = base_intent.issued_at

    def run_sequence():
        sm = TransactionStateMachine("tx_det", base_intent)
        sm.transition_to(TransactionState.EXECUTING, "Step 1", t0 + timedelta(seconds=1))
        sm.transition_to(TransactionState.OBSERVING, "Step 2", t0 + timedelta(seconds=2))
        sm.transition_to(TransactionState.VERIFYING, "Step 3", t0 + timedelta(seconds=3))
        sm.transition_to(TransactionState.PASS, "Step 4", t0 + timedelta(seconds=4))
        return [(h.from_state.value, h.to_state.value, h.reason) for h in sm.history]

    res1 = run_sequence()
    for _ in range(50):
        res_i = run_sequence()
        assert res_i == res1
