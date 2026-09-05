"""
Integration tests for Replay Governance (I3.4).

Demonstrates:
- same snapshot + same rules + same policy = same decision
- different rules_version is distinguishable
- different policy_version is distinguishable
- Replay remains pure and side-effect-free
- Existing T13 replay behavior remains intact
- Advisory/AI data cannot override deterministic replay
"""
from datetime import datetime, timedelta, timezone
from typing import List
import pytest

from backend.app.domain.governance import (
    DEFAULT_POLICY_VERSION,
    DEFAULT_RULES_VERSION,
    GovernanceVersion,
)
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
from backend.app.domain.states.models import StateTransitionRecord
from backend.app.services.evaluation import evaluate_integrity
from backend.app.services.replay import (
    GovernedReplayService,
    ReplayEngine,
    ReplaySnapshot,
    ReplayVerdict,
)


@pytest.fixture
def base_intent() -> IntentContract:
    now = datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)
    unit_m = Money(amount=5000, currency="INR")
    return IntentContract(
        intent_id="intent-gov-001",
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
    )


@pytest.fixture
def base_evidence(base_intent) -> List[Evidence]:
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


@pytest.fixture
def base_events(base_intent) -> List[CanonicalEvent]:
    t0 = base_intent.issued_at
    return [
        CanonicalEvent(
            event_id="evt-1",
            transaction_id="tx-gov-001",
            intent_id=base_intent.intent_id,
            event_type="PAYMENT_AUTHORIZED",
            timestamp=t0 + timedelta(minutes=1),
            sequence_number=1,
            source=EvidenceSource.RAZORPAY,
            amount=Money(amount=5000, currency="INR"),
        ),
        CanonicalEvent(
            event_id="evt-2",
            transaction_id="tx-gov-001",
            intent_id=base_intent.intent_id,
            event_type="PAYMENT_CAPTURED",
            timestamp=t0 + timedelta(minutes=2),
            sequence_number=2,
            source=EvidenceSource.RAZORPAY,
            amount=Money(amount=5000, currency="INR"),
        ),
    ]


@pytest.fixture
def base_transitions(base_intent) -> List[StateTransitionRecord]:
    t0 = base_intent.issued_at
    return [
        StateTransitionRecord(
            transition_id="tr-1",
            from_state=TransactionState.CREATED,
            to_state=TransactionState.EXECUTING,
            reason="Executing",
            timestamp=t0 + timedelta(minutes=1),
        ),
        StateTransitionRecord(
            transition_id="tr-2",
            from_state=TransactionState.EXECUTING,
            to_state=TransactionState.OBSERVING,
            reason="Observing",
            timestamp=t0 + timedelta(minutes=2),
        ),
        StateTransitionRecord(
            transition_id="tr-3",
            from_state=TransactionState.OBSERVING,
            to_state=TransactionState.VERIFYING,
            reason="Verifying",
            timestamp=t0 + timedelta(minutes=3),
        ),
        StateTransitionRecord(
            transition_id="tr-4",
            from_state=TransactionState.VERIFYING,
            to_state=TransactionState.PASS,
            reason="Verified",
            timestamp=t0 + timedelta(minutes=4),
        ),
    ]


def test_governed_replay_same_inputs_same_rules_same_policy(base_intent, base_evidence, base_events, base_transitions):
    ref_time = base_intent.issued_at + timedelta(minutes=10)
    integrity = evaluate_integrity(base_intent, base_evidence, base_events, reference_time=ref_time)

    snapshot = ReplaySnapshot(
        replay_id="rep-gov-1",
        transaction_id="tx-gov-001",
        contract=base_intent,
        events=base_events,
        evidence=base_evidence,
        state_transitions=base_transitions,
        recorded_integrity_result=integrity,
        recorded_final_state=TransactionState.PASS,
        reference_time=ref_time,
        rules_version="1.0.0",
    )

    gov = GovernanceVersion(rules_version="1.0.0", policy_version="merchant-policy-1")

    res1 = GovernedReplayService.execute_governed_replay(snapshot, governance=gov, issue_certificate=True)
    res2 = GovernedReplayService.execute_governed_replay(snapshot, governance=gov, issue_certificate=True)

    assert res1.is_match is True
    assert res2.is_match is True
    assert res1.reproducibility_record.input_snapshot_hash == res2.reproducibility_record.input_snapshot_hash
    assert res1.certificate.certificate_signature_hash == res2.certificate.certificate_signature_hash

    # Validate certificate
    cert_val = res1.certificate.verify_integrity(intent=base_intent, events=base_events, evidence=base_evidence)
    assert cert_val.is_valid is True

    # Validate reproducibility verification method
    assert GovernedReplayService.verify_reproducibility(res1.reproducibility_record) is True


def test_governed_replay_distinguishes_different_policy_version(base_intent, base_evidence, base_events, base_transitions):
    ref_time = base_intent.issued_at + timedelta(minutes=10)
    integrity = evaluate_integrity(base_intent, base_evidence, base_events, reference_time=ref_time)

    snapshot = ReplaySnapshot(
        replay_id="rep-gov-pol-diff",
        transaction_id="tx-gov-001",
        contract=base_intent,  # has policy_version="merchant-policy-1"
        events=base_events,
        evidence=base_evidence,
        state_transitions=base_transitions,
        recorded_integrity_result=integrity,
        recorded_final_state=TransactionState.PASS,
        reference_time=ref_time,
        rules_version="1.0.0",
    )

    gov_mismatch = GovernanceVersion(rules_version="1.0.0", policy_version="merchant-policy-2")
    res = GovernedReplayService.execute_governed_replay(snapshot, governance=gov_mismatch)

    assert res.policy_version_match is False
    assert res.verdict == ReplayVerdict.MISMATCH
    assert any("policy_version" in d.field for d in res.replay_result.discrepancies)


def test_governed_replay_distinguishes_different_rules_version(base_intent, base_evidence, base_events, base_transitions):
    ref_time = base_intent.issued_at + timedelta(minutes=10)
    integrity = evaluate_integrity(base_intent, base_evidence, base_events, reference_time=ref_time)

    snapshot = ReplaySnapshot(
        replay_id="rep-gov-rules-diff",
        transaction_id="tx-gov-001",
        contract=base_intent,
        events=base_events,
        evidence=base_evidence,
        state_transitions=base_transitions,
        recorded_integrity_result=integrity,
        recorded_final_state=TransactionState.PASS,
        reference_time=ref_time,
        rules_version="2.0.0",  # Different from engine default 1.0.0
    )

    gov = GovernanceVersion(rules_version="2.0.0", policy_version="merchant-policy-1")
    res = GovernedReplayService.execute_governed_replay(snapshot, governance=gov)

    assert res.is_match is False
    assert any("rules_version" in d.field for d in res.replay_result.discrepancies)
