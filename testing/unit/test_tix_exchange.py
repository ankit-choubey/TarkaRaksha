"""Unit tests for I6 — TIX Exchange Service & Protocol Verifier.

Tests:
1. Valid message accepted by TIXExchangeVerifier.
2. Context binding: INTENT_MISMATCH, TRANSACTION_MISMATCH, ATTEMPT_MISMATCH.
3. Participant binding: SENDER_MISMATCH, RECEIVER_MISMATCH.
4. Temporal freshness: EXPIRED_MESSAGE, FUTURE_TIMESTAMP.
5. Duplication / Replay: DUPLICATE_MESSAGE_ID.
6. Hash integrity: HASH_MISMATCH, HASH_CHAIN_MISMATCH.
7. TIXExchangeService multi-round message exchange with sequential hash chaining.
8. Ledger retrieval and verify_chain_integrity.
9. Deterministic integrity evaluation bridge (PASS and DRIFT outcome recording).
"""
from datetime import datetime, timedelta, timezone
import pytest

from backend.app.domain.models.enums import EvidenceSource, IntegrityStatus
from backend.app.domain.models.evidence import CanonicalEvent, Evidence
from backend.app.domain.models.intent import IntentContract, IntentItem
from backend.app.domain.models.money import Money
from backend.app.domain.tix import (
    TIXExchangeVerifier,
    TIXMessage,
    TIXMessageType,
    TIXParticipantRole,
    TIXViolationCode,
)
from backend.app.services.tix import TIXExchangeService


@pytest.fixture
def base_time() -> datetime:
    return datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def verifier() -> TIXExchangeVerifier:
    return TIXExchangeVerifier(max_clock_skew_seconds=60)


@pytest.fixture
def sample_message(base_time: datetime) -> TIXMessage:
    return TIXMessage(
        message_id="msg_001",
        transaction_id="tx_100",
        intent_id="intent_100",
        attempt_id="att_1",
        sender="buyer_agent",
        receiver="tarkaraksha_router",
        timestamp=base_time,
        expires_at=base_time + timedelta(minutes=10),
        message_type=TIXMessageType.INTENT,
        payload={"sku": "SERVER-256", "max_paise": 5000000},
    ).with_computed_hash()


def test_verifier_accepts_valid_message(verifier: TIXExchangeVerifier, sample_message: TIXMessage, base_time: datetime):
    outcome = verifier.verify_message(
        message=sample_message,
        expected_intent_id="intent_100",
        expected_transaction_id="tx_100",
        expected_attempt_id="att_1",
        expected_sender="buyer_agent",
        expected_receiver="tarkaraksha_router",
        reference_time=base_time,
    )
    assert outcome.is_valid is True
    assert outcome.violation_code is None


def test_verifier_detects_intent_mismatch(verifier: TIXExchangeVerifier, sample_message: TIXMessage, base_time: datetime):
    outcome = verifier.verify_message(
        message=sample_message,
        expected_intent_id="intent_WRONG",
        expected_transaction_id="tx_100",
        reference_time=base_time,
    )
    assert outcome.is_valid is False
    assert outcome.violation_code == TIXViolationCode.INTENT_MISMATCH


def test_verifier_detects_transaction_mismatch(verifier: TIXExchangeVerifier, sample_message: TIXMessage, base_time: datetime):
    outcome = verifier.verify_message(
        message=sample_message,
        expected_intent_id="intent_100",
        expected_transaction_id="tx_WRONG",
        reference_time=base_time,
    )
    assert outcome.is_valid is False
    assert outcome.violation_code == TIXViolationCode.TRANSACTION_MISMATCH


def test_verifier_detects_attempt_mismatch(verifier: TIXExchangeVerifier, sample_message: TIXMessage, base_time: datetime):
    outcome = verifier.verify_message(
        message=sample_message,
        expected_attempt_id="att_WRONG",
        reference_time=base_time,
    )
    assert outcome.is_valid is False
    assert outcome.violation_code == TIXViolationCode.ATTEMPT_MISMATCH


def test_verifier_detects_sender_and_receiver_mismatch(verifier: TIXExchangeVerifier, sample_message: TIXMessage, base_time: datetime):
    outcome_s = verifier.verify_message(
        message=sample_message,
        expected_sender="merchant_agent",
        reference_time=base_time,
    )
    assert outcome_s.is_valid is False
    assert outcome_s.violation_code == TIXViolationCode.SENDER_MISMATCH

    outcome_r = verifier.verify_message(
        message=sample_message,
        expected_receiver="unauthorized_endpoint",
        reference_time=base_time,
    )
    assert outcome_r.is_valid is False
    assert outcome_r.violation_code == TIXViolationCode.RECEIVER_MISMATCH


def test_verifier_detects_expired_message(verifier: TIXExchangeVerifier, sample_message: TIXMessage, base_time: datetime):
    # expires at base_time + 10 mins; check at base_time + 11 mins
    outcome = verifier.verify_message(
        message=sample_message,
        reference_time=base_time + timedelta(minutes=11),
    )
    assert outcome.is_valid is False
    assert outcome.violation_code == TIXViolationCode.EXPIRED_MESSAGE


def test_verifier_detects_future_timestamp(verifier: TIXExchangeVerifier, sample_message: TIXMessage, base_time: datetime):
    # message timestamp is base_time, reference is base_time - 2 mins (message is from future)
    outcome = verifier.verify_message(
        message=sample_message,
        reference_time=base_time - timedelta(minutes=2),
    )
    assert outcome.is_valid is False
    assert outcome.violation_code == TIXViolationCode.FUTURE_TIMESTAMP


def test_verifier_detects_duplicate_message(verifier: TIXExchangeVerifier, sample_message: TIXMessage, base_time: datetime):
    seen = {sample_message.message_id}
    outcome = verifier.verify_message(
        message=sample_message,
        seen_message_ids=seen,
        reference_time=base_time,
    )
    assert outcome.is_valid is False
    assert outcome.violation_code == TIXViolationCode.DUPLICATE_MESSAGE_ID


def test_verifier_detects_hash_mismatch(verifier: TIXExchangeVerifier, sample_message: TIXMessage, base_time: datetime):
    # Construct message with forged hash
    forged_data = sample_message.model_dump()
    forged_data["current_message_hash"] = "0" * 64
    forged_msg = TIXMessage(**forged_data)

    outcome = verifier.verify_message(
        message=forged_msg,
        reference_time=base_time,
    )
    assert outcome.is_valid is False
    assert outcome.violation_code == TIXViolationCode.HASH_MISMATCH


def test_verifier_detects_hash_chain_mismatch(verifier: TIXExchangeVerifier, sample_message: TIXMessage, base_time: datetime):
    outcome = verifier.verify_message(
        message=sample_message,
        expected_previous_hash="expected_preceding_hash_value",
        reference_time=base_time,
    )
    assert outcome.is_valid is False
    assert outcome.violation_code == TIXViolationCode.HASH_CHAIN_MISMATCH


# --- Exchange Service Multi-Round Exchange Tests ---

def test_exchange_service_multi_round_hash_chain(base_time: datetime):
    service = TIXExchangeService()
    tx_id = "tx_multi_001"
    intent_id = "intent_multi_001"

    # Message 1: INTENT
    m1 = TIXMessage(
        message_id="msg_1",
        transaction_id=tx_id,
        intent_id=intent_id,
        sender="buyer_agent",
        receiver="tarkaraksha_router",
        timestamp=base_time,
        message_type=TIXMessageType.INTENT,
        payload={"sku": "SERVER-256", "max_price": 50000},
    ).with_computed_hash()

    res1, comm1 = service.append_and_verify(m1, reference_time=base_time)
    assert res1.is_valid is True
    assert comm1 is not None
    assert service.get_chain_hash(tx_id) == comm1.current_message_hash

    # Message 2: OFFER
    m2 = TIXMessage(
        message_id="msg_2",
        transaction_id=tx_id,
        intent_id=intent_id,
        sender="merchant_agent",
        receiver="tarkaraksha_router",
        timestamp=base_time + timedelta(seconds=1),
        message_type=TIXMessageType.OFFER,
        payload={"sku": "SERVER-256", "price": 49000},
        previous_message_hash=comm1.current_message_hash,
    ).with_computed_hash()

    res2, comm2 = service.append_and_verify(m2, reference_time=base_time + timedelta(seconds=1))
    assert res2.is_valid is True
    assert comm2 is not None
    assert service.get_chain_hash(tx_id) == comm2.current_message_hash

    # Message 3: INTEGRITY_CHECK
    m3 = TIXMessage(
        message_id="msg_3",
        transaction_id=tx_id,
        intent_id=intent_id,
        sender="tarkaraksha_router",
        receiver="tarkaraksha_core",
        timestamp=base_time + timedelta(seconds=2),
        message_type=TIXMessageType.INTEGRITY_CHECK,
        payload={"action": "VERIFY"},
        previous_message_hash=comm2.current_message_hash,
    ).with_computed_hash()

    res3, comm3 = service.append_and_verify(m3, reference_time=base_time + timedelta(seconds=2))
    assert res3.is_valid is True
    assert comm3 is not None
    assert service.get_chain_hash(tx_id) == comm3.current_message_hash

    # Message 4: OUTCOME
    m4 = TIXMessage(
        message_id="msg_4",
        transaction_id=tx_id,
        intent_id=intent_id,
        sender=TIXParticipantRole.TARKARAKSHA_CORE.value,
        receiver="tarkaraksha_router",
        timestamp=base_time + timedelta(seconds=3),
        message_type=TIXMessageType.OUTCOME,
        payload={"status": "PASS", "authoritative": True},
        previous_message_hash=comm3.current_message_hash,
    ).with_computed_hash()

    res4, comm4 = service.append_and_verify(m4, reference_time=base_time + timedelta(seconds=3))
    assert res4.is_valid is True
    assert comm4 is not None

    # Check ledger length and audit chain integrity
    ledger = service.get_ledger(tx_id)
    assert len(ledger) == 4
    is_chain_valid, err = service.verify_chain_integrity(tx_id)
    assert is_chain_valid is True
    assert err is None


def test_exchange_service_integrity_evaluation_bridge(base_time: datetime):
    service = TIXExchangeService()
    tx_id = "tx_bridge_001"
    intent = IntentContract(
        intent_id="intent_bridge_001",
        issued_by="user_01",
        items=[
            IntentItem(
                item_id="item_01",
                sku="SERVER-256",
                name="Server 256",
                quantity=1,
                unit_price=Money(amount=5000000, currency="INR"),
                total_price=Money(amount=5000000, currency="INR"),
            )
        ],
        max_total=Money(amount=5000000, currency="INR"),
        issued_at=base_time,
        expires_at=base_time + timedelta(hours=1),
    )

    # Compliant evidence
    evidence = [
        Evidence(
            evidence_id="ev_01",
            intent_id="intent_bridge_001",
            source=EvidenceSource.RAZORPAY,
            field_name="total_amount",
            field_value=Money(amount=5000000, currency="INR"),
            observed_at=base_time,
            is_authoritative=True,
        ),
        Evidence(
            evidence_id="ev_02",
            intent_id="intent_bridge_001",
            source=EvidenceSource.RAZORPAY,
            field_name="executed_items",
            field_value=[{"sku": "SERVER-256", "quantity": 1}],
            observed_at=base_time,
            is_authoritative=True,
        ),
    ]

    events = [
        CanonicalEvent(
            event_id="evt_01",
            transaction_id=tx_id,
            intent_id=intent.intent_id,
            event_type="PAYMENT_CAPTURED",
            timestamp=base_time,
            sequence_number=1,
        )
    ]

    msg, result = service.evaluate_and_record_integrity(
        intent=intent,
        evidence_list=evidence,
        events=events,
        transaction_id=tx_id,
        outcome_message_id="outcome_01",
        reference_time=base_time,
    )

    assert result.status == IntegrityStatus.PASS
    assert msg.message_type == TIXMessageType.OUTCOME
    assert msg.payload["status"] == "PASS"
    assert msg.payload["authoritative"] is True

    # Drift evidence (amount exceeds intent)
    drift_ev = [
        Evidence(
            evidence_id="ev_03",
            intent_id="intent_bridge_001",
            source=EvidenceSource.RAZORPAY,
            field_name="total_amount",
            field_value=Money(amount=6000000, currency="INR"),
            observed_at=base_time,
            is_authoritative=True,
        ),
        Evidence(
            evidence_id="ev_04",
            intent_id="intent_bridge_001",
            source=EvidenceSource.RAZORPAY,
            field_name="executed_items",
            field_value=[{"sku": "SERVER-256", "quantity": 1}],
            observed_at=base_time,
            is_authoritative=True,
        ),
    ]

    msg_drift, result_drift = service.evaluate_and_record_integrity(
        intent=intent,
        evidence_list=drift_ev,
        transaction_id=tx_id,
        outcome_message_id="outcome_02",
        reference_time=base_time,
    )

    assert result_drift.status == IntegrityStatus.DRIFT
    assert msg_drift.message_type == TIXMessageType.DRIFT_NOTICE
    assert msg_drift.payload["status"] == "DRIFT"
    assert len(msg_drift.payload["violations"]) > 0


def test_buyer_agent_proposal_in_tix_exchange(base_time: datetime):
    service = TIXExchangeService()
    tx_id = "tx_buyer_tix_01"
    intent = IntentContract(
        intent_id="intent_b_01",
        issued_by="buyer_alice",
        items=[
            IntentItem(
                item_id="i1",
                sku="LAPTOP-16",
                name="Pro Laptop",
                quantity=1,
                unit_price=Money(amount=7500000, currency="INR"),
                total_price=Money(amount=7500000, currency="INR"),
            )
        ],
        max_total=Money(amount=7500000, currency="INR"),
        issued_at=base_time,
        expires_at=base_time + timedelta(hours=2),
    )

    intent_msg = service.build_intent_message(
        message_id="msg_b_01",
        intent=intent,
        transaction_id=tx_id,
        timestamp=base_time,
    )

    outcome, committed = service.append_and_verify(intent_msg, reference_time=base_time)
    assert outcome.is_valid is True
    assert committed is not None
    assert committed.payload["max_total_paise"] == 7500000
    assert committed.payload["currency"] == "INR"


def test_merchant_agent_offer_in_tix_exchange(base_time: datetime):
    service = TIXExchangeService()
    tx_id = "tx_merch_tix_01"

    offer_msg = service.build_offer_message(
        message_id="msg_m_01",
        intent_id="intent_m_01",
        transaction_id=tx_id,
        offer_payload={"sku": "LAPTOP-16", "offered_price_paise": 7400000, "in_stock": True},
        evidence_refs=["ev_inv_01"],
        capability_refs=["cap_shipping_v1", "cap_inventory_v1"],
        policy_version="policy_2026_09",
        expires_at=base_time + timedelta(minutes=15),
        timestamp=base_time,
    )

    outcome, committed = service.append_and_verify(offer_msg, reference_time=base_time)
    assert outcome.is_valid is True
    assert committed is not None
    assert committed.capability_refs == ["cap_shipping_v1", "cap_inventory_v1"]
    assert committed.policy_version == "policy_2026_09"
    assert committed.evidence_refs == ["ev_inv_01"]


def test_full_tix_multi_round_remediation_chain(base_time: datetime):
    service = TIXExchangeService()
    tx_id = "tx_full_flow_01"
    intent_id = "intent_full_flow_01"

    # 1. Buyer INTENT
    m1 = service.build_intent_message(
        message_id="m1_intent",
        intent=IntentContract(
            intent_id=intent_id,
            issued_by="buyer_alice",
            items=[
                IntentItem(
                    item_id="i1",
                    sku="SERVER-256",
                    name="Server",
                    quantity=1,
                    unit_price=Money(amount=5000000, currency="INR"),
                    total_price=Money(amount=5000000, currency="INR"),
                )
            ],
            max_total=Money(amount=5000000, currency="INR"),
            issued_at=base_time,
            expires_at=base_time + timedelta(hours=1),
        ),
        transaction_id=tx_id,
        timestamp=base_time,
    )
    res1, c1 = service.append_and_verify(m1, reference_time=base_time)
    assert res1.is_valid is True

    # 2. Merchant initial OFFER (Over budget)
    m2 = service.build_offer_message(
        message_id="m2_offer",
        intent_id=intent_id,
        transaction_id=tx_id,
        offer_payload={"sku": "SERVER-256", "price": 5400000},
        previous_hash=c1.current_message_hash,
        timestamp=base_time + timedelta(seconds=1),
    )
    res2, c2 = service.append_and_verify(m2, reference_time=base_time + timedelta(seconds=1))
    assert res2.is_valid is True

    # 3. TarkaRaksha DRIFT_NOTICE
    m3 = service.build_drift_notice_message(
        message_id="m3_drift",
        intent_id=intent_id,
        transaction_id=tx_id,
        violations=["MAX_TOTAL_EXCEEDED: ₹54,000 > ₹50,000"],
        previous_hash=c2.current_message_hash,
        timestamp=base_time + timedelta(seconds=2),
    )
    res3, c3 = service.append_and_verify(m3, reference_time=base_time + timedelta(seconds=2))
    assert res3.is_valid is True

    # 4. Buyer REMEDIATION_REQUEST (Request counter within budget)
    m4 = service.build_remediation_request_message(
        message_id="m4_remedy",
        intent_id=intent_id,
        transaction_id=tx_id,
        requested_remediation="Counter-offer required under ₹50,000",
        previous_hash=c3.current_message_hash,
        timestamp=base_time + timedelta(seconds=3),
    )
    res4, c4 = service.append_and_verify(m4, reference_time=base_time + timedelta(seconds=3))
    assert res4.is_valid is True

    # 5. Merchant revised OFFER (compliant at ₹49,500)
    m5 = service.build_offer_message(
        message_id="m5_revised_offer",
        intent_id=intent_id,
        transaction_id=tx_id,
        offer_payload={"sku": "SERVER-256", "price": 4950000},
        previous_hash=c4.current_message_hash,
        timestamp=base_time + timedelta(seconds=4),
    )
    res5, c5 = service.append_and_verify(m5, reference_time=base_time + timedelta(seconds=4))
    assert res5.is_valid is True

    # 6. TarkaRaksha final OUTCOME
    m6 = service.build_outcome_message(
        message_id="m6_outcome",
        intent_id=intent_id,
        transaction_id=tx_id,
        status="PASS",
        previous_hash=c5.current_message_hash,
        timestamp=base_time + timedelta(seconds=5),
    )
    res6, c6 = service.append_and_verify(m6, reference_time=base_time + timedelta(seconds=5))
    assert res6.is_valid is True

    # Ledger audit
    ledger = service.get_ledger(tx_id)
    assert len(ledger) == 6
    chain_ok, err = service.verify_chain_integrity(tx_id)
    assert chain_ok is True
    assert err is None
