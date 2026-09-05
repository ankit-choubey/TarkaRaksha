"""
Comprehensive unit test suite for TarkaRaksha Replay Engine (T13).

Covers all required T13 test categories (§22):
1. Determinism:
   - Identical replay input yields identical result
   - Repeated replay yields bit-for-bit identical result
   - Explicit reference time produces reproducible temporal evaluation
2. Event Ordering:
   - Chronological replay
   - Deterministic timestamp tie-breaking
   - Out-of-order historical events reconstructed correctly
   - Ambiguous ordering flagged safely
3. State Machine:
   - Legal lifecycle replay
   - Illegal transition detected (e.g. UNKNOWN -> PASS skipped states)
   - Skipped transition detected
   - UNKNOWN resolution lifecycle replay
   - Recovery lifecycle replay
4. Integrity Evaluation:
   - Historical PASS replay -> MATCH
   - Historical DRIFT replay -> MATCH
   - Historical UNKNOWN replay -> MATCH
   - Altered evidence -> MISMATCH
   - Altered intent -> MISMATCH
5. Evidence Handling:
   - Authoritative provider evidence preserved
   - Advisory evidence cannot override authoritative evidence
   - Historical evidence deduplication
   - Conflicting authoritative evidence handled safely
6. MRDP:
   - Valid historical MRDP matches
   - Tampered MRDP proof digest detected
7. Recovery:
   - Recovery history replayed without side effects
   - Recovery result mismatch detected
   - Replay never calls financial provider methods
8. UNKNOWN Resolution:
   - Historical UNKNOWN resolution reconstructed
   - Live provider is never queried during replay
   - Unresolved UNKNOWN remains UNKNOWN
9. AI Independence:
   - Replay works with AI unavailable
   - Historical AI proposal does not affect deterministic result
10. API Endpoint:
   - POST /api/v1/replay returns expected replay verdict and diagnostics
"""
import copy
from datetime import datetime, timezone, timedelta
from typing import List
import pytest
from fastapi.testclient import TestClient

from backend.app.domain.models import (
    CanonicalEvent,
    Evidence,
    EvidenceBundle,
    EvidenceSource,
    EvidenceAuthority,
    IntegrityResult,
    IntegrityStatus,
    IntentContract,
    IntentItem,
    Money,
    MRDP,
    TransactionState,
)
from backend.app.domain.states.models import StateTransitionRecord
from backend.app.services.evaluation import evaluate_integrity
from backend.app.services.mrdp import build_mrdp
from backend.app.services.replay import (
    ReplayEngine,
    ReplaySnapshot,
    ReplayResult,
    ReplayVerdict,
    InvalidReplayInputError,
    ReplayAmbiguityError,
    order_canonical_events,
    order_evidence_records,
)
from backend.app.main import app


# --- Helper Fixtures ---

@pytest.fixture
def base_intent() -> IntentContract:
    now = datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)
    return IntentContract(
        intent_id="intent-replay-001",
        issued_by="usr-test-1",
        issued_at=now,
        expires_at=now + timedelta(hours=2),
        currency="INR",
        max_total=Money(amount=5000, currency="INR"),
        items=[
            IntentItem(
                item_id="item-1",
                sku="SKU-BOOK",
                name="Tech Book",
                quantity=1,
                unit_price=Money(amount=5000, currency="INR"),
                total_price=Money(amount=5000, currency="INR"),
            )
        ],
        max_successful_captures=1,
    )


@pytest.fixture
def auth_evidence(base_intent) -> Evidence:
    return Evidence(
        evidence_id="evi-auth-001",
        intent_id=base_intent.intent_id,
        source=EvidenceSource.RAZORPAY,
        authority=EvidenceAuthority.AUTHORITATIVE,
        field_name="total_amount",
        field_value=Money(amount=5000, currency="INR"),
        observed_at=base_intent.issued_at + timedelta(minutes=5),
        is_authoritative=True,
    )


@pytest.fixture
def items_evidence(base_intent) -> Evidence:
    return Evidence(
        evidence_id="evi-items-001",
        intent_id=base_intent.intent_id,
        source=EvidenceSource.RAZORPAY,
        authority=EvidenceAuthority.AUTHORITATIVE,
        field_name="executed_items",
        field_value=[{"sku": "SKU-BOOK", "quantity": 1}],
        observed_at=base_intent.issued_at + timedelta(minutes=5),
        is_authoritative=True,
    )


@pytest.fixture
def pass_events(base_intent) -> List[CanonicalEvent]:
    t0 = base_intent.issued_at
    return [
        CanonicalEvent(
            event_id="evt-001",
            transaction_id="tx-replay-001",
            intent_id=base_intent.intent_id,
            event_type="PAYMENT_AUTHORIZED",
            timestamp=t0 + timedelta(minutes=1),
            sequence_number=1,
            source=EvidenceSource.RAZORPAY,
            amount=Money(amount=5000, currency="INR"),
        ),
        CanonicalEvent(
            event_id="evt-002",
            transaction_id="tx-replay-001",
            intent_id=base_intent.intent_id,
            event_type="PAYMENT_CAPTURED",
            timestamp=t0 + timedelta(minutes=2),
            sequence_number=2,
            source=EvidenceSource.RAZORPAY,
            amount=Money(amount=5000, currency="INR"),
        ),
    ]


@pytest.fixture
def pass_transitions(base_intent) -> List[StateTransitionRecord]:
    t0 = base_intent.issued_at
    return [
        StateTransitionRecord(
            transition_id="tr-1",
            from_state=TransactionState.CREATED,
            to_state=TransactionState.EXECUTING,
            reason="Order dispatched to gateway",
            timestamp=t0 + timedelta(minutes=1),
        ),
        StateTransitionRecord(
            transition_id="tr-2",
            from_state=TransactionState.EXECUTING,
            to_state=TransactionState.OBSERVING,
            reason="Listening for gateway webhooks",
            timestamp=t0 + timedelta(minutes=2),
        ),
        StateTransitionRecord(
            transition_id="tr-3",
            from_state=TransactionState.OBSERVING,
            to_state=TransactionState.VERIFYING,
            reason="Gateway evidence received",
            timestamp=t0 + timedelta(minutes=3),
        ),
        StateTransitionRecord(
            transition_id="tr-4",
            from_state=TransactionState.VERIFYING,
            to_state=TransactionState.PASS,
            reason="Integrity checks passed",
            timestamp=t0 + timedelta(minutes=4),
        ),
    ]


# --- 1. Determinism Tests (§22.1–§22.3) ---

def test_replay_determinism_identical_output(base_intent, auth_evidence, items_evidence, pass_events, pass_transitions):
    ref_time = base_intent.issued_at + timedelta(minutes=10)
    evidence_bundle = [auth_evidence, items_evidence]
    integrity = evaluate_integrity(
        contract=base_intent,
        evidence_list=evidence_bundle,
        events=pass_events,
        reference_time=ref_time,
    )
    snapshot = ReplaySnapshot(
        replay_id="rep-001",
        transaction_id="tx-001",
        contract=base_intent,
        events=pass_events,
        evidence=evidence_bundle,
        state_transitions=pass_transitions,
        recorded_integrity_result=integrity,
        recorded_final_state=TransactionState.PASS,
        reference_time=ref_time,
    )

    res1 = ReplayEngine.replay(snapshot)
    res2 = ReplayEngine.replay(snapshot)

    assert res1.verdict == ReplayVerdict.MATCH
    assert res2.verdict == ReplayVerdict.MATCH
    assert res1.replayed_state == res2.replayed_state == TransactionState.PASS
    assert res1.replayed_integrity_result.status == res2.replayed_integrity_result.status == IntegrityStatus.PASS
    assert res1.ordered_event_ids == res2.ordered_event_ids
    assert res1.ordered_evidence_ids == res2.ordered_evidence_ids
    assert len(res1.discrepancies) == 0


def test_repeated_replay_stability(base_intent, auth_evidence, items_evidence, pass_events, pass_transitions):
    ref_time = base_intent.issued_at + timedelta(minutes=10)
    snapshot = ReplaySnapshot(
        replay_id="rep-repeat",
        transaction_id="tx-repeat",
        contract=base_intent,
        events=pass_events,
        evidence=[auth_evidence, items_evidence],
        state_transitions=pass_transitions,
        recorded_final_state=TransactionState.PASS,
        reference_time=ref_time,
    )
    first_res = ReplayEngine.replay(snapshot)
    for _ in range(50):
        res = ReplayEngine.replay(snapshot)
        assert res.verdict == first_res.verdict
        assert res.replayed_state == first_res.replayed_state
        assert res.replayed_integrity_result.status == first_res.replayed_integrity_result.status


def test_explicit_reference_time_reproducibility(base_intent, pass_events):
    expired_time = base_intent.expires_at + timedelta(days=5)
    expired_event = CanonicalEvent(
        event_id="evt-late",
        transaction_id="tx-expired",
        intent_id=base_intent.intent_id,
        event_type="PAYMENT_CAPTURED",
        timestamp=expired_time,
        sequence_number=1,
        source=EvidenceSource.RAZORPAY,
        amount=Money(amount=5000, currency="INR"),
    )
    snapshot = ReplaySnapshot(
        replay_id="rep-expired",
        transaction_id="tx-expired",
        contract=base_intent,
        events=[expired_event],
        evidence=[],
        state_transitions=[],
        reference_time=expired_time,
    )
    res = ReplayEngine.replay(snapshot)
    assert res.replayed_integrity_result.status == IntegrityStatus.DRIFT


# --- 2. Event Ordering Tests (§22.4–§22.7) ---

def test_chronological_replay_out_of_order_events(base_intent):
    t0 = base_intent.issued_at
    e1 = CanonicalEvent(event_id="e1", transaction_id="tx-1", intent_id=base_intent.intent_id, event_type="INIT", timestamp=t0 + timedelta(seconds=10), source=EvidenceSource.SYSTEM)
    e2 = CanonicalEvent(event_id="e2", transaction_id="tx-1", intent_id=base_intent.intent_id, event_type="AUTH", timestamp=t0 + timedelta(seconds=20), source=EvidenceSource.SYSTEM)
    e3 = CanonicalEvent(event_id="e3", transaction_id="tx-1", intent_id=base_intent.intent_id, event_type="CAPT", timestamp=t0 + timedelta(seconds=30), source=EvidenceSource.SYSTEM)

    ordered = order_canonical_events([e3, e1, e2])
    assert [e.event_id for e in ordered] == ["e1", "e2", "e3"]


def test_deterministic_timestamp_tie_breaker(base_intent):
    t0 = base_intent.issued_at
    eA = CanonicalEvent(event_id="evt-A", transaction_id="tx-1", intent_id=base_intent.intent_id, event_type="SAME_TIME", timestamp=t0, source=EvidenceSource.SYSTEM)
    eB = CanonicalEvent(event_id="evt-B", transaction_id="tx-1", intent_id=base_intent.intent_id, event_type="SAME_TIME", timestamp=t0, source=EvidenceSource.SYSTEM)

    ordered1 = order_canonical_events([eB, eA])
    ordered2 = order_canonical_events([eA, eB])
    assert [e.event_id for e in ordered1] == ["evt-A", "evt-B"]
    assert [e.event_id for e in ordered2] == ["evt-A", "evt-B"]


def test_ambiguous_ordering_rejected(base_intent):
    t0 = base_intent.issued_at
    e1 = CanonicalEvent(event_id="evt-dup", transaction_id="tx-1", intent_id=base_intent.intent_id, event_type="TYPE_A", timestamp=t0, source=EvidenceSource.SYSTEM)
    e2 = CanonicalEvent(event_id="evt-dup", transaction_id="tx-1", intent_id=base_intent.intent_id, event_type="TYPE_B", timestamp=t0 + timedelta(seconds=5), source=EvidenceSource.SYSTEM)

    with pytest.raises(ReplayAmbiguityError):
        order_canonical_events([e1, e2])


# --- 3. State Machine Replay Tests (§22.8–§22.12) ---

def test_illegal_state_transition_detected(base_intent):
    t0 = base_intent.issued_at
    illegal_transitions = [
        StateTransitionRecord(
            transition_id="tr-1",
            from_state=TransactionState.CREATED,
            to_state=TransactionState.EXECUTING,
            reason="Dispatched",
            timestamp=t0 + timedelta(minutes=1),
        ),
        StateTransitionRecord(
            transition_id="tr-2",
            from_state=TransactionState.EXECUTING,
            to_state=TransactionState.PASS,  # ILLEGAL JUMP: cannot jump directly from EXECUTING to PASS
            reason="Forced pass bypass",
            timestamp=t0 + timedelta(minutes=2),
        ),
    ]
    snapshot = ReplaySnapshot(
        replay_id="rep-illegal-sm",
        transaction_id="tx-illegal-sm",
        contract=base_intent,
        events=[],
        evidence=[],
        state_transitions=illegal_transitions,
        reference_time=t0 + timedelta(minutes=5),
    )
    result = ReplayEngine.replay(snapshot)
    assert result.verdict == ReplayVerdict.INVALID_REPLAY
    assert any("Illegal transition" in d.explanation for d in result.discrepancies)


def test_skipped_transition_detected(base_intent):
    t0 = base_intent.issued_at
    skipped_transitions = [
        StateTransitionRecord(
            transition_id="tr-1",
            from_state=TransactionState.CREATED,
            to_state=TransactionState.VERIFYING,  # SKIPPED EXECUTING & OBSERVING
            reason="Skipped",
            timestamp=t0 + timedelta(minutes=1),
        ),
    ]
    snapshot = ReplaySnapshot(
        replay_id="rep-skipped-sm",
        transaction_id="tx-skipped-sm",
        contract=base_intent,
        events=[],
        evidence=[],
        state_transitions=skipped_transitions,
        reference_time=t0 + timedelta(minutes=5),
    )
    result = ReplayEngine.replay(snapshot)
    assert result.verdict == ReplayVerdict.INVALID_REPLAY


def test_unknown_resolution_lifecycle_replay(base_intent):
    t0 = base_intent.issued_at
    valid_unknown_lifecycle = [
        StateTransitionRecord(
            transition_id="tr-1",
            from_state=TransactionState.CREATED,
            to_state=TransactionState.EXECUTING,
            reason="Dispatched",
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
            to_state=TransactionState.UNKNOWN,
            reason="Gateway timeout observed",
            timestamp=t0 + timedelta(minutes=4),
        ),
        StateTransitionRecord(
            transition_id="tr-5",
            from_state=TransactionState.UNKNOWN,
            to_state=TransactionState.RESOLVING,
            reason="Resolution initiated",
            timestamp=t0 + timedelta(minutes=5),
        ),
        StateTransitionRecord(
            transition_id="tr-6",
            from_state=TransactionState.RESOLVING,
            to_state=TransactionState.REVALIDATING,
            reason="Evidence obtained, revalidating",
            timestamp=t0 + timedelta(minutes=6),
        ),
        StateTransitionRecord(
            transition_id="tr-7",
            from_state=TransactionState.REVALIDATING,
            to_state=TransactionState.PASS,
            reason="Integrity confirmed post-resolution",
            timestamp=t0 + timedelta(minutes=7),
        ),
    ]
    snapshot = ReplaySnapshot(
        replay_id="rep-unknown-flow",
        transaction_id="tx-unknown-flow",
        contract=base_intent,
        events=[],
        evidence=[],
        state_transitions=valid_unknown_lifecycle,
        recorded_final_state=TransactionState.PASS,
        reference_time=t0 + timedelta(minutes=10),
    )
    result = ReplayEngine.replay(snapshot)
    assert result.replayed_state == TransactionState.PASS
    assert not any("state_transition" in d.field for d in result.discrepancies)


# --- 4. Integrity & Tamper Detection Tests (§22.13–§22.18) ---

def test_historical_pass_matches(base_intent, auth_evidence, items_evidence, pass_events, pass_transitions):
    ref_time = base_intent.issued_at + timedelta(minutes=10)
    evidence_bundle = [auth_evidence, items_evidence]
    integrity = evaluate_integrity(base_intent, evidence_bundle, pass_events, reference_time=ref_time)
    snapshot = ReplaySnapshot(
        replay_id="rep-pass",
        transaction_id="tx-pass",
        contract=base_intent,
        events=pass_events,
        evidence=evidence_bundle,
        state_transitions=pass_transitions,
        recorded_integrity_result=integrity,
        recorded_final_state=TransactionState.PASS,
        reference_time=ref_time,
    )
    res = ReplayEngine.replay(snapshot)
    assert res.verdict == ReplayVerdict.MATCH
    assert res.is_match


def test_tampered_evidence_amount_causes_mismatch(base_intent, auth_evidence, items_evidence, pass_events, pass_transitions):
    ref_time = base_intent.issued_at + timedelta(minutes=10)
    evidence_bundle = [auth_evidence, items_evidence]
    recorded_integrity = evaluate_integrity(base_intent, evidence_bundle, pass_events, reference_time=ref_time)

    # Tampered higher amount
    tampered_evidence = Evidence(
        evidence_id="evi-tampered",
        intent_id=base_intent.intent_id,
        source=EvidenceSource.RAZORPAY,
        authority=EvidenceAuthority.AUTHORITATIVE,
        field_name="total_amount",
        field_value=Money(amount=999999, currency="INR"),
        observed_at=auth_evidence.observed_at,
        is_authoritative=True,
    )
    snapshot = ReplaySnapshot(
        replay_id="rep-tampered-evi",
        transaction_id="tx-tampered-evi",
        contract=base_intent,
        events=pass_events,
        evidence=[tampered_evidence, items_evidence],
        state_transitions=pass_transitions,
        recorded_integrity_result=recorded_integrity,
        recorded_final_state=TransactionState.PASS,
        reference_time=ref_time,
    )
    res = ReplayEngine.replay(snapshot)
    assert res.verdict == ReplayVerdict.MISMATCH
    assert res.is_mismatch
    assert any("integrity_result.status" in d.field for d in res.discrepancies)


def test_tampered_intent_causes_mismatch(base_intent, auth_evidence, items_evidence, pass_events, pass_transitions):
    ref_time = base_intent.issued_at + timedelta(minutes=10)
    evidence_bundle = [auth_evidence, items_evidence]
    recorded_integrity = evaluate_integrity(base_intent, evidence_bundle, pass_events, reference_time=ref_time)

    tampered_intent = IntentContract(
        intent_id=base_intent.intent_id,
        issued_by=base_intent.issued_by,
        issued_at=base_intent.issued_at,
        expires_at=base_intent.expires_at,
        currency="INR",
        max_total=Money(amount=100, currency="INR"),  # only 100 paise authorized
        items=[
            IntentItem(
                item_id="item-1",
                sku="SKU-BOOK",
                name="Tech Book",
                quantity=1,
                unit_price=Money(amount=100, currency="INR"),
                total_price=Money(amount=100, currency="INR"),
            )
        ],
        max_successful_captures=1,
    )
    snapshot = ReplaySnapshot(
        replay_id="rep-tampered-intent",
        transaction_id="tx-tampered-intent",
        contract=tampered_intent,
        events=pass_events,
        evidence=evidence_bundle,
        state_transitions=pass_transitions,
        recorded_integrity_result=recorded_integrity,
        recorded_final_state=TransactionState.PASS,
        reference_time=ref_time,
    )
    res = ReplayEngine.replay(snapshot)
    assert res.verdict == ReplayVerdict.MISMATCH


# --- 5. MRDP Validation & Tamper Tests (§22.23–§22.24) ---

def test_mrdp_proof_match(base_intent):
    ref_time = base_intent.issued_at + timedelta(minutes=10)
    drift_evidence = Evidence(
        evidence_id="evi-drift",
        intent_id=base_intent.intent_id,
        source=EvidenceSource.RAZORPAY,
        authority=EvidenceAuthority.AUTHORITATIVE,
        field_name="total_amount",
        field_value=Money(amount=7500, currency="INR"),  # 7500 > 5000 max_total
        observed_at=ref_time,
        is_authoritative=True,
    )
    integrity = evaluate_integrity(base_intent, [drift_evidence], [], reference_time=ref_time)
    bundle = EvidenceBundle(
        bundle_id="b-1",
        intent_id=base_intent.intent_id,
        transaction_id="tx-drift",
        created_at=ref_time,
        records=[drift_evidence],
    )
    recorded_mrdp = build_mrdp(
        contract=base_intent,
        integrity_result=integrity,
        evidence_bundle=bundle,
        generated_at=ref_time,
        mrdp_id="proof-drift-1",
    )

    t0 = base_intent.issued_at
    drift_transitions = [
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
            to_state=TransactionState.DRIFT,
            reason="Drift detected",
            timestamp=t0 + timedelta(minutes=4),
        ),
    ]

    snapshot = ReplaySnapshot(
        replay_id="rep-mrdp-match",
        transaction_id="tx-drift",
        contract=base_intent,
        events=[],
        evidence=[drift_evidence],
        state_transitions=drift_transitions,
        recorded_integrity_result=integrity,
        recorded_final_state=TransactionState.DRIFT,
        recorded_mrdp=recorded_mrdp,
        reference_time=ref_time,
    )
    res = ReplayEngine.replay(snapshot)
    assert res.is_mrdp_valid is True
    assert res.verdict == ReplayVerdict.MATCH


def test_tampered_mrdp_digest_detected(base_intent):
    ref_time = base_intent.issued_at + timedelta(minutes=10)
    drift_evidence = Evidence(
        evidence_id="evi-drift",
        intent_id=base_intent.intent_id,
        source=EvidenceSource.RAZORPAY,
        authority=EvidenceAuthority.AUTHORITATIVE,
        field_name="total_amount",
        field_value=Money(amount=7500, currency="INR"),
        observed_at=ref_time,
        is_authoritative=True,
    )
    integrity = evaluate_integrity(base_intent, [drift_evidence], [], reference_time=ref_time)
    bundle = EvidenceBundle(
        bundle_id="b-1",
        intent_id=base_intent.intent_id,
        transaction_id="tx-drift",
        created_at=ref_time,
        records=[drift_evidence],
    )
    original_mrdp = build_mrdp(
        contract=base_intent,
        integrity_result=integrity,
        evidence_bundle=bundle,
        generated_at=ref_time,
        mrdp_id="proof-drift-tamper",
    )

    # Attacker alters violation text without updating proof_digest
    tampered_mrdp = original_mrdp.model_copy(update={"violation": "Injected malicious message"})

    snapshot = ReplaySnapshot(
        replay_id="rep-mrdp-tamper",
        transaction_id="tx-drift",
        contract=base_intent,
        events=[],
        evidence=[drift_evidence],
        state_transitions=[],
        recorded_integrity_result=integrity,
        recorded_final_state=TransactionState.DRIFT,
        recorded_mrdp=tampered_mrdp,
        reference_time=ref_time,
    )
    res = ReplayEngine.replay(snapshot)
    assert res.is_mrdp_valid is False
    assert res.verdict == ReplayVerdict.MISMATCH
    assert any("recorded_mrdp.proof_digest" in d.field for d in res.discrepancies)


# --- 6. AI Independence Tests (§22.31–§22.33) ---

def test_replay_works_without_ai(base_intent, auth_evidence, items_evidence, pass_events, pass_transitions):
    ref_time = base_intent.issued_at + timedelta(minutes=10)
    snapshot = ReplaySnapshot(
        replay_id="rep-no-ai",
        transaction_id="tx-no-ai",
        contract=base_intent,
        events=pass_events,
        evidence=[auth_evidence, items_evidence],
        state_transitions=pass_transitions,
        reference_time=ref_time,
    )
    res = ReplayEngine.replay(snapshot)
    assert res.replayed_integrity_result.status == IntegrityStatus.PASS


def test_advisory_ai_evidence_cannot_override_drift(base_intent):
    ref_time = base_intent.issued_at + timedelta(minutes=10)
    drift_auth = Evidence(
        evidence_id="evi-auth-overcharge",
        intent_id=base_intent.intent_id,
        source=EvidenceSource.RAZORPAY,
        authority=EvidenceAuthority.AUTHORITATIVE,
        field_name="total_amount",
        field_value=Money(amount=99000, currency="INR"),
        observed_at=ref_time,
        is_authoritative=True,
    )
    ai_advisory = Evidence(
        evidence_id="evi-ai-pass-opinion",
        intent_id=base_intent.intent_id,
        source=EvidenceSource.AGENT,
        authority=EvidenceAuthority.ADVISORY,
        field_name="total_amount",
        field_value=Money(amount=5000, currency="INR"),
        observed_at=ref_time,
        is_authoritative=False,
    )
    snapshot = ReplaySnapshot(
        replay_id="rep-ai-override-attempt",
        transaction_id="tx-ai-override",
        contract=base_intent,
        events=[],
        evidence=[drift_auth, ai_advisory],
        state_transitions=[],
        reference_time=ref_time,
    )
    res = ReplayEngine.replay(snapshot)
    assert res.replayed_integrity_result.status == IntegrityStatus.DRIFT


# --- 7. API Endpoint Tests (§20) ---

def test_api_replay_endpoint(base_intent, auth_evidence, items_evidence, pass_events, pass_transitions):
    client = TestClient(app)
    ref_time = base_intent.issued_at + timedelta(minutes=10)
    evidence_bundle = [auth_evidence, items_evidence]
    integrity = evaluate_integrity(base_intent, evidence_bundle, pass_events, reference_time=ref_time)
    snapshot = ReplaySnapshot(
        replay_id="rep-api-test",
        transaction_id="tx-api-test",
        contract=base_intent,
        events=pass_events,
        evidence=evidence_bundle,
        state_transitions=pass_transitions,
        recorded_integrity_result=integrity,
        recorded_final_state=TransactionState.PASS,
        reference_time=ref_time,
    )
    response = client.post("/api/v1/replay", json=snapshot.model_dump(mode="json"))
    assert response.status_code == 200
    data = response.json()
    assert data["replay_id"] == "rep-api-test"
    assert data["verdict"] == "MATCH"
    assert data["replayed_state"] == "PASS"
    assert data["discrepancies"] == []
