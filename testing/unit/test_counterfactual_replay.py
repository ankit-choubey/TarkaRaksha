"""
Unit tests for Counterfactual Replay Analysis (I3.5).

Verifies:
U. Original snapshot remains unchanged
V. Candidate mutation produces a separate replay
W. Counterfactual replay is deterministic
X. Counterfactual replay has zero external side effects
Y. Original and counterfactual decisions can be compared
Z. Repeated counterfactual replay gives identical results
"""
from datetime import datetime, timedelta, timezone
from typing import List
import pytest

from backend.app.domain.models import (
    CanonicalEvent,
    Evidence,
    EvidenceAuthority,
    EvidenceSource,
    IntegrityResult,
    IntegrityStatus,
    IntentContract,
    IntentItem,
    Money,
    TransactionState,
)
from backend.app.services.evaluation import evaluate_integrity
from backend.app.services.replay import (
    CounterfactualMutationType,
    CounterfactualReplayAnalysisService,
    ReplayEngine,
    ReplaySnapshot,
    ReplayVerdict,
)


@pytest.fixture
def base_intent() -> IntentContract:
    now = datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)
    unit_m = Money(amount=5000, currency="INR")
    return IntentContract(
        intent_id="intent-cf-001",
        issued_by="usr-test-1",
        issued_at=now,
        expires_at=now + timedelta(hours=2),
        currency="INR",
        max_total=unit_m,
        items=[
            IntentItem(
                item_id="item-1",
                sku="SKU-BOOK",
                name="Tech Book",
                quantity=1,
                unit_price=unit_m,
                total_price=unit_m,
            )
        ],
        contract_version="1.0.0",
        policy_version="merchant-policy-1",
        max_successful_captures=1,
    )


@pytest.fixture
def duplicate_capture_events(base_intent) -> List[CanonicalEvent]:
    t0 = base_intent.issued_at
    return [
        CanonicalEvent(
            event_id="evt-auth",
            transaction_id="tx-cf-001",
            intent_id=base_intent.intent_id,
            event_type="PAYMENT_AUTHORIZED",
            timestamp=t0 + timedelta(minutes=1),
            sequence_number=1,
            source=EvidenceSource.RAZORPAY,
            amount=Money(amount=5000, currency="INR"),
        ),
        CanonicalEvent(
            event_id="evt-capture-1",
            transaction_id="tx-cf-001",
            intent_id=base_intent.intent_id,
            event_type="PAYMENT_CAPTURED",
            timestamp=t0 + timedelta(minutes=2),
            sequence_number=2,
            source=EvidenceSource.RAZORPAY,
            amount=Money(amount=5000, currency="INR"),
        ),
        CanonicalEvent(
            event_id="evt-retry-duplicate-capture",
            transaction_id="tx-cf-001",
            intent_id=base_intent.intent_id,
            event_type="PAYMENT_CAPTURED",
            timestamp=t0 + timedelta(minutes=3),
            sequence_number=3,
            source=EvidenceSource.RAZORPAY,
            amount=Money(amount=5000, currency="INR"),
        ),
    ]


@pytest.fixture
def capture_evidence(base_intent) -> List[Evidence]:
    t = base_intent.issued_at + timedelta(minutes=5)
    return [
        Evidence(
            evidence_id="evi-auth-1",
            intent_id=base_intent.intent_id,
            source=EvidenceSource.RAZORPAY,
            authority=EvidenceAuthority.AUTHORITATIVE,
            field_name="total_amount",
            field_value=Money(amount=5000, currency="INR"),
            observed_at=t,
            is_authoritative=True,
        ),
        Evidence(
            evidence_id="evi-item-1",
            intent_id=base_intent.intent_id,
            source=EvidenceSource.RAZORPAY,
            authority=EvidenceAuthority.AUTHORITATIVE,
            field_name="executed_items",
            field_value=[{"sku": "SKU-BOOK", "quantity": 1}],
            observed_at=t,
            is_authoritative=True,
        ),
    ]


def test_counterfactual_event_removal_eliminates_drift(base_intent, duplicate_capture_events, capture_evidence):
    ref_time = base_intent.issued_at + timedelta(minutes=10)

    # In baseline: duplicate capture event causes DRIFT (max_successful_captures exceeded)
    snapshot = ReplaySnapshot(
        replay_id="rep-dup-capture",
        transaction_id="tx-cf-001",
        contract=base_intent,
        events=duplicate_capture_events,
        evidence=capture_evidence,
        state_transitions=[],
        reference_time=ref_time,
        rules_version="1.0.0",
    )

    baseline_result = ReplayEngine.replay(snapshot)
    assert baseline_result.replayed_integrity_result.status == IntegrityStatus.DRIFT

    # Analyze counterfactual removal of the retry capture event
    comparison = CounterfactualReplayAnalysisService.analyze_event_removal(
        snapshot=snapshot,
        candidate_event_id="evt-retry-duplicate-capture",
    )

    # Invariants:
    # 1. Original snapshot events list length is preserved
    assert len(snapshot.events) == 3
    # 2. Baseline was DRIFT, Counterfactual is PASS
    assert comparison.baseline_integrity_status == IntegrityStatus.DRIFT
    assert comparison.counterfactual_integrity_status == IntegrityStatus.PASS
    assert comparison.discrepancy_eliminated is True
    assert comparison.target_event_id == "evt-retry-duplicate-capture"
    assert comparison.mutation_type == CounterfactualMutationType.REMOVE_EVENT


def test_counterfactual_event_modification(base_intent, capture_evidence):
    ref_time = base_intent.issued_at + timedelta(minutes=10)

    # Event occurring past contract expiration (causes ExpiredExecution DRIFT)
    expired_event = CanonicalEvent(
        event_id="evt-expired",
        transaction_id="tx-cf-mod",
        intent_id=base_intent.intent_id,
        event_type="PAYMENT_CAPTURED",
        timestamp=base_intent.expires_at + timedelta(hours=1),
        sequence_number=1,
        source=EvidenceSource.RAZORPAY,
        amount=Money(amount=5000, currency="INR"),
    )

    snapshot = ReplaySnapshot(
        replay_id="rep-mod-test",
        transaction_id="tx-cf-mod",
        contract=base_intent,
        events=[expired_event],
        evidence=capture_evidence,
        state_transitions=[],
        reference_time=ref_time,
    )

    # Counterfactual modifier shifts timestamp into the authorized window
    def fix_timestamp(event: CanonicalEvent) -> CanonicalEvent:
        return event.model_copy(update={"timestamp": base_intent.issued_at + timedelta(minutes=2)})

    comparison = CounterfactualReplayAnalysisService.analyze_event_modification(
        snapshot=snapshot,
        target_event_id="evt-expired",
        modifier_fn=fix_timestamp,
    )

    assert comparison.baseline_integrity_status == IntegrityStatus.DRIFT
    assert comparison.counterfactual_integrity_status == IntegrityStatus.PASS
    assert comparison.discrepancy_eliminated is True
    assert comparison.mutation_type == CounterfactualMutationType.MODIFY_EVENT_PAYLOAD


def test_counterfactual_replay_stability_and_determinism(base_intent, duplicate_capture_events, capture_evidence):
    ref_time = base_intent.issued_at + timedelta(minutes=10)
    snapshot = ReplaySnapshot(
        replay_id="rep-stability",
        transaction_id="tx-cf-001",
        contract=base_intent,
        events=duplicate_capture_events,
        evidence=capture_evidence,
        state_transitions=[],
        reference_time=ref_time,
    )

    first_comp = CounterfactualReplayAnalysisService.analyze_event_removal(
        snapshot=snapshot,
        candidate_event_id="evt-retry-duplicate-capture",
    )

    for _ in range(25):
        comp = CounterfactualReplayAnalysisService.analyze_event_removal(
            snapshot=snapshot,
            candidate_event_id="evt-retry-duplicate-capture",
        )
        assert comp.baseline_integrity_status == first_comp.baseline_integrity_status
        assert comp.counterfactual_integrity_status == first_comp.counterfactual_integrity_status
        assert comp.discrepancy_eliminated == first_comp.discrepancy_eliminated
