"""
Unit tests for Deterministic Reproducibility Records (I3.2).
"""
from datetime import datetime, timezone
import pytest

from backend.app.domain.governance import (
    DEFAULT_POLICY_VERSION,
    DEFAULT_RULES_VERSION,
    ReproducibilityRecord,
)
from backend.app.domain.models import (
    ActionType,
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


@pytest.fixture
def base_intent():
    unit_m = Money(amount=10000, currency="INR")
    return IntentContract(
        intent_id="intent_rep_1",
        issued_by="usr_rep_1",
        currency="INR",
        max_total=unit_m,
        items=[IntentItem(item_id="item_1", sku="SKU-1", name="Wireless Mouse", quantity=1, unit_price=unit_m, total_price=unit_m)],
        issued_at=datetime(2026, 9, 5, 10, 0, 0, tzinfo=timezone.utc),
        expires_at=datetime(2026, 9, 5, 11, 0, 0, tzinfo=timezone.utc),
    )


@pytest.fixture
def base_events():
    return [
        CanonicalEvent(
            event_id="ev_1",
            transaction_id="tx_rep_1",
            intent_id="intent_rep_1",
            event_type="ORDER_CREATED",
            source=EvidenceSource.MERCHANT,
            authority=EvidenceAuthority.MERCHANT_ATTESTED,
            timestamp=datetime(2026, 9, 5, 10, 5, 0, tzinfo=timezone.utc),
            payload_summary={"order_id": "order_1", "amount": 10000},
        ),
        CanonicalEvent(
            event_id="ev_2",
            transaction_id="tx_rep_1",
            intent_id="intent_rep_1",
            event_type="PAYMENT_CAPTURED",
            source=EvidenceSource.RAZORPAY,
            authority=EvidenceAuthority.AUTHORITATIVE,
            timestamp=datetime(2026, 9, 5, 10, 6, 0, tzinfo=timezone.utc),
            payload_summary={"payment_id": "pay_1", "amount": 10000},
        ),
    ]


@pytest.fixture
def base_evidence():
    return [
        Evidence(
            evidence_id="evi_1",
            intent_id="intent_rep_1",
            transaction_id="tx_rep_1",
            source=EvidenceSource.RAZORPAY,
            authority=EvidenceAuthority.AUTHORITATIVE,
            field_name="payment_status",
            field_value="captured",
            observed_at=datetime(2026, 9, 5, 10, 6, 1, tzinfo=timezone.utc),
        )
    ]


@pytest.fixture
def base_result():
    return IntegrityResult(
        evaluation_id="eval_1",
        intent_id="intent_rep_1",
        status=IntegrityStatus.PASS,
        evaluated_at=datetime(2026, 9, 5, 10, 10, 0, tzinfo=timezone.utc),
        rule_results={},
        violations=[],
        evidence_ids=["evi_1"],
    )


def test_reproducibility_record_creation(base_intent, base_events, base_evidence, base_result):
    ref_time = datetime(2026, 9, 5, 10, 10, 0, tzinfo=timezone.utc)
    rec = ReproducibilityRecord.create(
        record_id="rec_1",
        transaction_id="tx_rep_1",
        intent=base_intent,
        events=base_events,
        evidence=base_evidence,
        reference_time=ref_time,
        recorded_result=base_result,
        recorded_final_state=TransactionState.PASS,
    )

    assert rec.record_id == "rec_1"
    assert rec.transaction_id == "tx_rep_1"
    assert rec.rules_version == DEFAULT_RULES_VERSION
    assert rec.policy_version == DEFAULT_POLICY_VERSION
    assert rec.input_snapshot_hash is not None
    assert len(rec.input_snapshot_hash) == 64
    assert rec.verify_input_hash() is True


def test_same_inputs_same_rules_same_policy_equals_same_hash(base_intent, base_events, base_evidence, base_result):
    ref_time = datetime(2026, 9, 5, 10, 10, 0, tzinfo=timezone.utc)

    # Scramble the input event and evidence ordering to prove canonical ordering invariance
    scrambled_events = list(reversed(base_events))

    rec1 = ReproducibilityRecord.create(
        record_id="rec_1",
        transaction_id="tx_rep_1",
        intent=base_intent,
        events=base_events,
        evidence=base_evidence,
        reference_time=ref_time,
        recorded_result=base_result,
    )

    rec2 = ReproducibilityRecord.create(
        record_id="rec_2",
        transaction_id="tx_rep_1",
        intent=base_intent,
        events=scrambled_events,
        evidence=base_evidence,
        reference_time=ref_time,
        recorded_result=base_result,
    )

    assert rec1.input_snapshot_hash == rec2.input_snapshot_hash


def test_different_rules_or_policy_version_changes_hash(base_intent, base_events, base_evidence, base_result):
    ref_time = datetime(2026, 9, 5, 10, 10, 0, tzinfo=timezone.utc)

    rec_base = ReproducibilityRecord.create(
        record_id="rec_1",
        transaction_id="tx_rep_1",
        intent=base_intent,
        events=base_events,
        evidence=base_evidence,
        reference_time=ref_time,
        recorded_result=base_result,
        rules_version="integrity-1.0.0",
        policy_version="merchant-policy-1",
    )

    rec_rules_diff = ReproducibilityRecord.create(
        record_id="rec_2",
        transaction_id="tx_rep_1",
        intent=base_intent,
        events=base_events,
        evidence=base_evidence,
        reference_time=ref_time,
        recorded_result=base_result,
        rules_version="integrity-1.1.0",
        policy_version="merchant-policy-1",
    )

    rec_policy_diff = ReproducibilityRecord.create(
        record_id="rec_3",
        transaction_id="tx_rep_1",
        intent=base_intent,
        events=base_events,
        evidence=base_evidence,
        reference_time=ref_time,
        recorded_result=base_result,
        rules_version="integrity-1.0.0",
        policy_version="merchant-policy-2",
    )

    assert rec_base.input_snapshot_hash != rec_rules_diff.input_snapshot_hash
    assert rec_base.input_snapshot_hash != rec_policy_diff.input_snapshot_hash
    assert rec_rules_diff.input_snapshot_hash != rec_policy_diff.input_snapshot_hash


def test_reference_time_is_preserved_and_deterministic(base_intent, base_events, base_evidence, base_result):
    ref_time_1 = datetime(2026, 9, 5, 10, 10, 0, tzinfo=timezone.utc)
    ref_time_2 = datetime(2026, 9, 5, 10, 15, 0, tzinfo=timezone.utc)

    rec1 = ReproducibilityRecord.create(
        record_id="rec_1",
        transaction_id="tx_rep_1",
        intent=base_intent,
        events=base_events,
        evidence=base_evidence,
        reference_time=ref_time_1,
        recorded_result=base_result,
    )
    rec2 = ReproducibilityRecord.create(
        record_id="rec_2",
        transaction_id="tx_rep_1",
        intent=base_intent,
        events=base_events,
        evidence=base_evidence,
        reference_time=ref_time_2,
        recorded_result=base_result,
    )

    assert rec1.reference_time == ref_time_1
    assert rec2.reference_time == ref_time_2
    assert rec1.input_snapshot_hash != rec2.input_snapshot_hash


def test_input_snapshot_tamper_detection(base_intent, base_events, base_evidence, base_result):
    ref_time = datetime(2026, 9, 5, 10, 10, 0, tzinfo=timezone.utc)
    rec = ReproducibilityRecord.create(
        record_id="rec_1",
        transaction_id="tx_rep_1",
        intent=base_intent,
        events=base_events,
        evidence=base_evidence,
        reference_time=ref_time,
        recorded_result=base_result,
    )
    assert rec.verify_input_hash() is True

    # Artificially alter the intent max_total in the record dictionary
    tampered_intent = base_intent.model_copy(update={"max_total": Money(amount=99999, currency="INR")})
    tampered_rec = rec.model_copy(update={"intent": tampered_intent})

    assert tampered_rec.verify_input_hash() is False
