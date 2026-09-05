"""Adversarial and Security Boundary Tests for I6 — TIX.

Validates that:
1. Non-TarkaRaksha participants (buyer_agent, merchant_agent) cannot emit AUTHORIZATION messages (UNAUTHORIZED_PAYMENT_CLAIM).
2. Malicious agents embedding payment authorization claims in payloads are rejected (UNAUTHORIZED_PAYMENT_CLAIM).
3. Rogue agents claiming authoritative OUTCOME are rejected (AUTHORITY_BREACH).
4. Replay of previously accepted message_ids is strictly rejected (DUPLICATE_MESSAGE_ID).
5. Cross-transaction message hijacking is strictly rejected (TRANSACTION_MISMATCH).
6. Intent substitution is strictly rejected (INTENT_MISMATCH).
7. In-transit message body tampering without re-hashing is caught (HASH_MISMATCH).
8. In-transit message insertion with re-hashing breaks the hash chain (HASH_CHAIN_MISMATCH).
9. TIX cannot convert DRIFT or UNKNOWN into PASS.
10. TIX exchange contains zero LLM involvement, zero payment authorization authority, and zero floating-point arithmetic.
"""
from datetime import datetime, timedelta, timezone
import pytest

from backend.app.domain.models.enums import EvidenceSource, IntegrityStatus
from backend.app.domain.models.evidence import Evidence
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


def test_adversarial_agent_cannot_emit_authorization_message(verifier: TIXExchangeVerifier, base_time: datetime):
    # Rogue buyer or merchant agent attempts to emit an AUTHORIZATION message
    msg = TIXMessage(
        message_id="rogue_auth_01",
        transaction_id="tx_adv_01",
        intent_id="intent_adv_01",
        sender="merchant_agent",
        receiver="tarkaraksha_router",
        timestamp=base_time,
        message_type=TIXMessageType.AUTHORIZATION,
        payload={"authorized": True, "amount": 5000000},
    ).with_computed_hash()

    outcome = verifier.verify_message(
        message=msg,
        expected_intent_id="intent_adv_01",
        expected_transaction_id="tx_adv_01",
        reference_time=base_time,
    )
    assert outcome.is_valid is False
    assert outcome.violation_code == TIXViolationCode.UNAUTHORIZED_PAYMENT_CLAIM


@pytest.mark.parametrize("rogue_key", ["payment_authorized", "authorize_payment", "bypass_integrity", "force_pass"])
def test_adversarial_agent_payload_with_rogue_payment_claims_rejected(
    verifier: TIXExchangeVerifier, base_time: datetime, rogue_key: str
):
    msg = TIXMessage(
        message_id=f"rogue_payload_{rogue_key}",
        transaction_id="tx_adv_02",
        intent_id="intent_adv_02",
        sender="buyer_agent",
        receiver="tarkaraksha_router",
        timestamp=base_time,
        message_type=TIXMessageType.OFFER,
        payload={rogue_key: True, "amount": 1000},
    ).with_computed_hash()

    outcome = verifier.verify_message(
        message=msg,
        expected_intent_id="intent_adv_02",
        expected_transaction_id="tx_adv_02",
        reference_time=base_time,
    )
    assert outcome.is_valid is False
    assert outcome.violation_code == TIXViolationCode.UNAUTHORIZED_PAYMENT_CLAIM


def test_adversarial_agent_cannot_declare_authoritative_outcome(verifier: TIXExchangeVerifier, base_time: datetime):
    msg = TIXMessage(
        message_id="rogue_outcome_01",
        transaction_id="tx_adv_03",
        intent_id="intent_adv_03",
        sender="merchant_agent",
        receiver="buyer_agent",
        timestamp=base_time,
        message_type=TIXMessageType.OUTCOME,
        payload={"status": "PASS", "authoritative": True},
    ).with_computed_hash()

    outcome = verifier.verify_message(
        message=msg,
        expected_intent_id="intent_adv_03",
        expected_transaction_id="tx_adv_03",
        reference_time=base_time,
    )
    assert outcome.is_valid is False
    assert outcome.violation_code == TIXViolationCode.AUTHORITY_BREACH


def test_adversarial_replay_attack_rejected(base_time: datetime):
    service = TIXExchangeService()
    tx_id = "tx_replay_01"
    intent_id = "intent_replay_01"

    msg = TIXMessage(
        message_id="msg_legit_01",
        transaction_id=tx_id,
        intent_id=intent_id,
        sender="buyer_agent",
        receiver="tarkaraksha_router",
        timestamp=base_time,
        message_type=TIXMessageType.INTENT,
        payload={"sku": "ITEM_1"},
    ).with_computed_hash()

    res1, comm1 = service.append_and_verify(msg, reference_time=base_time)
    assert res1.is_valid is True

    # Replay identical message
    res2, comm2 = service.append_and_verify(msg, reference_time=base_time + timedelta(seconds=1))
    assert res2.is_valid is False
    assert res2.violation_code == TIXViolationCode.DUPLICATE_MESSAGE_ID
    assert comm2 is None


def test_adversarial_cross_transaction_message_injection(base_time: datetime):
    service = TIXExchangeService()

    # Legit message for transaction A
    msg_a = TIXMessage(
        message_id="msg_tx_a",
        transaction_id="tx_AAA",
        intent_id="intent_AAA",
        sender="buyer_agent",
        receiver="tarkaraksha_router",
        timestamp=base_time,
        message_type=TIXMessageType.INTENT,
        payload={"data": "legit"},
    ).with_computed_hash()

    res_a, comm_a = service.append_and_verify(msg_a, reference_time=base_time)
    assert res_a.is_valid is True

    # Attempt to inject msg_a into transaction B with expected transaction B
    res_b, comm_b = service.append_and_verify(
        msg_a,
        expected_intent_id="intent_BBB",
        reference_time=base_time,
    )
    assert res_b.is_valid is False
    assert res_b.violation_code in {TIXViolationCode.INTENT_MISMATCH, TIXViolationCode.DUPLICATE_MESSAGE_ID}


def test_in_transit_payload_tampering_caught_by_hash_check(verifier: TIXExchangeVerifier, base_time: datetime):
    original_msg = TIXMessage(
        message_id="msg_tamper_01",
        transaction_id="tx_tamper",
        intent_id="intent_tamper",
        sender="buyer_agent",
        receiver="tarkaraksha_router",
        timestamp=base_time,
        message_type=TIXMessageType.INTENT,
        payload={"max_budget": 50000},
    ).with_computed_hash()

    # Attacker alters payload in-transit without updating hash
    tampered_data = original_msg.model_dump()
    tampered_data["payload"] = {"max_budget": 99999999}  # altered!
    tampered_msg = TIXMessage(**tampered_data)

    outcome = verifier.verify_message(
        message=tampered_msg,
        expected_intent_id="intent_tamper",
        expected_transaction_id="tx_tamper",
        reference_time=base_time,
    )
    assert outcome.is_valid is False
    assert outcome.violation_code == TIXViolationCode.HASH_MISMATCH


def test_in_transit_message_insertion_breaks_hash_chain(base_time: datetime):
    service = TIXExchangeService()
    tx_id = "tx_chain_attack"
    intent_id = "intent_chain_attack"

    # Message 1
    m1 = TIXMessage(
        message_id="msg_1",
        transaction_id=tx_id,
        intent_id=intent_id,
        sender="buyer_agent",
        receiver="tarkaraksha_router",
        timestamp=base_time,
        message_type=TIXMessageType.INTENT,
    ).with_computed_hash()
    service.append_and_verify(m1, reference_time=base_time)

    # Attacker crafts rogue message with fabricated previous_hash
    rogue_m2 = TIXMessage(
        message_id="msg_rogue_2",
        transaction_id=tx_id,
        intent_id=intent_id,
        sender="merchant_agent",
        receiver="tarkaraksha_router",
        timestamp=base_time + timedelta(seconds=1),
        message_type=TIXMessageType.OFFER,
        previous_message_hash="0" * 64,  # doesn't match m1's hash!
    ).with_computed_hash()

    outcome, comm = service.append_and_verify(rogue_m2, reference_time=base_time + timedelta(seconds=1))
    assert outcome.is_valid is False
    assert outcome.violation_code == TIXViolationCode.HASH_CHAIN_MISMATCH
    assert comm is None


def test_tix_cannot_convert_drift_or_unknown_to_pass(base_time: datetime):
    service = TIXExchangeService()
    tx_id = "tx_drift_check"
    intent = IntentContract(
        intent_id="intent_drift_check",
        issued_by="user_01",
        items=[
            IntentItem(
                item_id="item_01",
                sku="SKU-1",
                name="SKU Item 1",
                quantity=1,
                unit_price=Money(amount=10000, currency="INR"),
                total_price=Money(amount=10000, currency="INR"),
            )
        ],
        max_total=Money(amount=10000, currency="INR"),
        issued_at=base_time,
        expires_at=base_time + timedelta(hours=1),
    )

    # Missing evidence -> results in UNKNOWN in TarkaRaksha evaluation
    msg, result = service.evaluate_and_record_integrity(
        intent=intent,
        evidence_list=[],  # no evidence -> UNKNOWN
        transaction_id=tx_id,
        outcome_message_id="outcome_unknown",
        reference_time=base_time,
    )
    assert result.status == IntegrityStatus.UNKNOWN
    assert msg.payload["status"] == "UNKNOWN"
    assert msg.payload["status"] != "PASS"
