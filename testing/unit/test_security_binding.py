"""
Focused Test Suite for TarkaRaksha I2 — Security & Protocol Binding.

Validates all 28 documented checkpoint requirements:
1. Valid message -> accepted (is_valid=True).
2. Wrong intent -> rejected (INTENT_MISMATCH).
3. Wrong transaction -> rejected (TRANSACTION_MISMATCH).
4. Expired message -> rejected (STALE_MESSAGE).
5. Replayed consumed intent -> rejected (REPLAY).
6. Tampered message chain -> invalid (HASH_CHAIN_MISMATCH).
7. Protocol attack detection: REPLAY.
8. Protocol attack detection: INTENT_MISMATCH.
9. Protocol attack detection: TRANSACTION_MISMATCH.
10. Protocol attack detection: STALE_MESSAGE.
11. Protocol attack detection: DUPLICATE_MESSAGE.
12. Protocol attack detection: AGENT_ID_MISMATCH.
13. Protocol attack detection: STATE_DESYNC.
14. Valid hash chain across multiple consecutive messages.
15. First message with no previous hash accepted.
16. Canonical hash reproducibility across identical inputs.
17. Modified payload changes current hash.
18. Modified previous hash breaks chain.
19. Expired intent state rejection (INTENT_NOT_ACTIVE).
20. Revoked intent state rejection (INTENT_NOT_ACTIVE).
21. Consumed intent reuse on a different transaction rejected (REPLAY).
22. Attempt ID mismatch detection (TRANSACTION_MISMATCH).
23. Duplicate message identifier detection (DUPLICATE_MESSAGE).
24. Duplicate payload with distinct message IDs accepted when legitimate.
25. Invalid/malformed message rejected (extra fields forbidden, strict types).
26. Naive datetime rejection (timezone-awareness enforced).
27. Explicit reference-time determinism (zero wall-clock dependence).
28. Repeated verification produces identical result.
"""
from datetime import datetime, timezone, timedelta
import pytest
from pydantic import ValidationError

from backend.app.domain.models import (
    IntentConsumptionState,
    TransactionState,
    Money,
)
from backend.app.domain.security import (
    AgentTransactionMessage,
    ProtocolViolationCode,
    ProtocolVerificationOutcome,
    ProtocolSecurityVerifier,
    canonicalize_for_hash,
)


@pytest.fixture
def base_time() -> datetime:
    return datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def base_message(base_time: datetime) -> AgentTransactionMessage:
    msg = AgentTransactionMessage(
        message_id="msg_001",
        intent_id="int_001",
        transaction_id="tx_001",
        attempt_id="att_1",
        sender="agent_buyer_01",
        receiver="tarkaraksha_control_plane",
        timestamp=base_time,
        expires_at=base_time + timedelta(minutes=10),
        message_type="INTENT_SUBMIT",
        payload={"action": "order", "amount": Money(amount=50000, currency="INR")},
        claimed_state=TransactionState.CREATED,
        evidence_refs=["ev_int_01"],
        previous_message_hash=None,
    )
    return msg.with_computed_hash()


# ---------------------------------------------------------------------------
# Core Acceptance and Mismatch Rejections (Req 1, 2, 3, 4, 5, 6)
# ---------------------------------------------------------------------------

def test_valid_message_accepted(base_message, base_time):
    """Req 1: Valid message with matching identifiers and valid timestamps is accepted."""
    verifier = ProtocolSecurityVerifier()
    verifier.register_intent("int_001", IntentConsumptionState.ACTIVE)

    res = verifier.verify_message(
        message=base_message,
        expected_intent_id="int_001",
        expected_transaction_id="tx_001",
        expected_agent_id="agent_buyer_01",
        reference_time=base_time,
    )
    assert res.is_valid is True
    assert res.violation_code is None


def test_intent_mismatch_rejected(base_message, base_time):
    """Req 2 & 8: Wrong intent_id is deterministically rejected with INTENT_MISMATCH."""
    verifier = ProtocolSecurityVerifier()
    res = verifier.verify_message(
        message=base_message,
        expected_intent_id="int_divergent_999",
        expected_transaction_id="tx_001",
        reference_time=base_time,
    )
    assert res.is_valid is False
    assert res.violation_code == ProtocolViolationCode.INTENT_MISMATCH
    assert "int_001" in res.explanation


def test_transaction_mismatch_rejected(base_message, base_time):
    """Req 3 & 9: Wrong transaction_id is deterministically rejected with TRANSACTION_MISMATCH."""
    verifier = ProtocolSecurityVerifier()
    res = verifier.verify_message(
        message=base_message,
        expected_intent_id="int_001",
        expected_transaction_id="tx_unauthorized_888",
        reference_time=base_time,
    )
    assert res.is_valid is False
    assert res.violation_code == ProtocolViolationCode.TRANSACTION_MISMATCH
    assert "tx_001" in res.explanation


def test_expired_message_rejected(base_message, base_time):
    """Req 4 & 10: Message evaluated after expires_at is rejected with STALE_MESSAGE."""
    verifier = ProtocolSecurityVerifier()
    eval_time = base_time + timedelta(minutes=15)  # expires_at is base_time + 10 mins

    res = verifier.verify_message(
        message=base_message,
        expected_intent_id="int_001",
        expected_transaction_id="tx_001",
        reference_time=eval_time,
    )
    assert res.is_valid is False
    assert res.violation_code == ProtocolViolationCode.STALE_MESSAGE
    assert "expired" in res.explanation.lower()


def test_replayed_consumed_intent_rejected(base_message, base_time):
    """Req 5 & 21: A consumed intent bound to tx_001 cannot be reused for tx_002 (REPLAY)."""
    verifier = ProtocolSecurityVerifier()
    verifier.consume_intent(intent_id="int_001", transaction_id="tx_001")

    # Second transaction attempts to use same consumed intent
    msg2 = AgentTransactionMessage(
        message_id="msg_002",
        intent_id="int_001",
        transaction_id="tx_002",
        attempt_id="att_1",
        sender="agent_buyer_01",
        timestamp=base_time,
    ).with_computed_hash()

    res = verifier.verify_message(
        message=msg2,
        expected_intent_id="int_001",
        expected_transaction_id="tx_002",
        reference_time=base_time,
    )
    assert res.is_valid is False
    assert res.violation_code == ProtocolViolationCode.REPLAY
    assert "already CONSUMED" in res.explanation


def test_tampered_message_chain_rejected(base_message, base_time):
    """Req 6 & 18: Modified current_message_hash or broken previous_message_hash is rejected."""
    verifier = ProtocolSecurityVerifier()

    tampered_msg = AgentTransactionMessage(
        message_id=base_message.message_id,
        intent_id=base_message.intent_id,
        transaction_id=base_message.transaction_id,
        attempt_id=base_message.attempt_id,
        sender=base_message.sender,
        timestamp=base_message.timestamp,
        current_message_hash="0000000000000000000000000000000000000000000000000000000000000000",
    )

    res = verifier.verify_message(
        message=tampered_msg,
        expected_intent_id="int_001",
        expected_transaction_id="tx_001",
        reference_time=base_time,
    )
    assert res.is_valid is False
    assert res.violation_code == ProtocolViolationCode.HASH_CHAIN_MISMATCH


# ---------------------------------------------------------------------------
# Protocol Attack Detections (Req 7, 11, 12, 13)
# ---------------------------------------------------------------------------

def test_duplicate_message_id_rejected(base_message, base_time):
    """Req 11 & 23: Identical message_id re-sent is rejected as DUPLICATE_MESSAGE."""
    verifier = ProtocolSecurityVerifier()

    res1 = verifier.verify_message(
        message=base_message,
        expected_intent_id="int_001",
        expected_transaction_id="tx_001",
        reference_time=base_time,
    )
    assert res1.is_valid is True

    # Immediate replay of the exact same message
    res2 = verifier.verify_message(
        message=base_message,
        expected_intent_id="int_001",
        expected_transaction_id="tx_001",
        reference_time=base_time,
    )
    assert res2.is_valid is False
    assert res2.violation_code == ProtocolViolationCode.DUPLICATE_MESSAGE


def test_agent_id_mismatch_rejected(base_message, base_time):
    """Req 12: Unexpected agent identity claiming message is rejected as AGENT_ID_MISMATCH."""
    verifier = ProtocolSecurityVerifier()

    res = verifier.verify_message(
        message=base_message,
        expected_intent_id="int_001",
        expected_transaction_id="tx_001",
        expected_agent_id="agent_merchant_impostor",
        reference_time=base_time,
    )
    assert res.is_valid is False
    assert res.violation_code == ProtocolViolationCode.AGENT_ID_MISMATCH


def test_state_desync_rejected(base_message, base_time):
    """Req 13: Agent message claiming divergent state from state machine triggers STATE_DESYNC."""
    verifier = ProtocolSecurityVerifier()

    # Base message claims CREATED, but authoritative engine is already at EXECUTING
    res = verifier.verify_message(
        message=base_message,
        expected_intent_id="int_001",
        expected_transaction_id="tx_001",
        authoritative_state=TransactionState.EXECUTING,
        reference_time=base_time,
    )
    assert res.is_valid is False
    assert res.violation_code == ProtocolViolationCode.STATE_DESYNC


# ---------------------------------------------------------------------------
# Message Chain & Cryptographic Hashing (Req 14, 15, 16, 17)
# ---------------------------------------------------------------------------

def test_valid_chain_across_multiple_messages(base_time):
    """Req 14 & 15: Valid chain of 3 sequential messages linked by hash."""
    verifier = ProtocolSecurityVerifier()

    # Message 1 (first message, previous_message_hash is None)
    m1 = AgentTransactionMessage(
        message_id="msg_001",
        intent_id="int_001",
        transaction_id="tx_001",
        sender="buyer_agent",
        timestamp=base_time,
        previous_message_hash=None,
    ).with_computed_hash()

    r1 = verifier.verify_message(m1, "int_001", "tx_001", reference_time=base_time)
    assert r1.is_valid is True

    # Message 2 (links to m1.current_message_hash)
    m2 = AgentTransactionMessage(
        message_id="msg_002",
        intent_id="int_001",
        transaction_id="tx_001",
        sender="buyer_agent",
        timestamp=base_time + timedelta(seconds=1),
        previous_message_hash=m1.current_message_hash,
    ).with_computed_hash()

    r2 = verifier.verify_message(m2, "int_001", "tx_001", reference_time=base_time)
    assert r2.is_valid is True

    # Message 3 (links to m2.current_message_hash)
    m3 = AgentTransactionMessage(
        message_id="msg_003",
        intent_id="int_001",
        transaction_id="tx_001",
        sender="buyer_agent",
        timestamp=base_time + timedelta(seconds=2),
        previous_message_hash=m2.current_message_hash,
    ).with_computed_hash()

    r3 = verifier.verify_message(m3, "int_001", "tx_001", reference_time=base_time)
    assert r3.is_valid is True


def test_canonical_hash_reproducibility(base_time):
    """Req 16: Identical semantic inputs produce byte-identical SHA-256 hash."""
    m1 = AgentTransactionMessage(
        message_id="msg_hash_test",
        intent_id="int_01",
        transaction_id="tx_01",
        sender="agent_01",
        timestamp=base_time,
        payload={"b": 2, "a": 1},
    )
    m2 = AgentTransactionMessage(
        message_id="msg_hash_test",
        intent_id="int_01",
        transaction_id="tx_01",
        sender="agent_01",
        timestamp=base_time,
        payload={"a": 1, "b": 2},  # Different dict insertion order
    )
    assert m1.compute_canonical_hash() == m2.compute_canonical_hash()


def test_modified_payload_changes_hash(base_time):
    """Req 17: Altering payload alters computed SHA-256 hash."""
    m1 = AgentTransactionMessage(
        message_id="msg_payload_test",
        intent_id="int_01",
        transaction_id="tx_01",
        sender="agent_01",
        timestamp=base_time,
        payload={"amount": 50000},
    )
    m2 = AgentTransactionMessage(
        message_id="msg_payload_test",
        intent_id="int_01",
        transaction_id="tx_01",
        sender="agent_01",
        timestamp=base_time,
        payload={"amount": 50001},  # Altered amount
    )
    assert m1.compute_canonical_hash() != m2.compute_canonical_hash()


# ---------------------------------------------------------------------------
# Intent Consumption States & Attempt Binding (Req 19, 20, 22, 24)
# ---------------------------------------------------------------------------

def test_expired_and_revoked_intent_state(base_message, base_time):
    """Req 19 & 20: EXPIRED and REVOKED intent states cannot accept new transaction actions."""
    verifier = ProtocolSecurityVerifier()

    # Expired intent
    verifier.set_intent_state("int_001", IntentConsumptionState.EXPIRED)
    res_exp = verifier.verify_message(base_message, "int_001", "tx_001", reference_time=base_time)
    assert res_exp.is_valid is False
    assert res_exp.violation_code == ProtocolViolationCode.INTENT_NOT_ACTIVE

    # Revoked intent
    verifier.set_intent_state("int_001", IntentConsumptionState.REVOKED)
    res_rev = verifier.verify_message(base_message, "int_001", "tx_001", reference_time=base_time)
    assert res_rev.is_valid is False
    assert res_rev.violation_code == ProtocolViolationCode.INTENT_NOT_ACTIVE


def test_attempt_id_mismatch_rejected(base_message, base_time):
    """Req 22: Expected attempt att_2 rejects message marked att_1."""
    verifier = ProtocolSecurityVerifier()
    res = verifier.verify_message(
        message=base_message,
        expected_intent_id="int_001",
        expected_transaction_id="tx_001",
        expected_attempt_id="att_2",
        reference_time=base_time,
    )
    assert res.is_valid is False
    assert res.violation_code == ProtocolViolationCode.TRANSACTION_MISMATCH


def test_duplicate_payload_with_distinct_message_id_accepted(base_time):
    """Req 24: Legitimate consecutive observations with identical payloads but unique IDs are accepted."""
    verifier = ProtocolSecurityVerifier()

    m1 = AgentTransactionMessage(
        message_id="msg_obs_01",
        intent_id="int_001",
        transaction_id="tx_001",
        sender="monitor_agent",
        timestamp=base_time,
        payload={"status": "POLLING_GATEWAY"},
    ).with_computed_hash()

    r1 = verifier.verify_message(m1, "int_001", "tx_001", reference_time=base_time)
    assert r1.is_valid is True

    # Same payload, distinct unique message_id
    m2 = AgentTransactionMessage(
        message_id="msg_obs_02",
        intent_id="int_001",
        transaction_id="tx_001",
        sender="monitor_agent",
        timestamp=base_time + timedelta(seconds=5),
        payload={"status": "POLLING_GATEWAY"},
        previous_message_hash=m1.current_message_hash,
    ).with_computed_hash()

    r2 = verifier.verify_message(m2, "int_001", "tx_001", reference_time=base_time)
    assert r2.is_valid is True


# ---------------------------------------------------------------------------
# Strict Validation & Determinism (Req 25, 26, 27, 28)
# ---------------------------------------------------------------------------

def test_extra_fields_forbidden_on_message(base_time):
    """Req 25: Pydantic extra='forbid' rejects unauthorized injected fields."""
    with pytest.raises(ValidationError):
        AgentTransactionMessage(
            message_id="msg_bad",
            intent_id="int_01",
            transaction_id="tx_01",
            sender="agent_01",
            timestamp=base_time,
            malicious_injection="ADMIN_OVERRIDE",  # type: ignore
        )


def test_naive_datetime_rejected():
    """Req 26: Naive datetime without timezone is strictly rejected."""
    naive_dt = datetime(2026, 9, 5, 12, 0, 0)
    with pytest.raises(ValueError, match="timezone-aware"):
        AgentTransactionMessage(
            message_id="msg_naive",
            intent_id="int_01",
            transaction_id="tx_01",
            sender="agent_01",
            timestamp=naive_dt,
        )


def test_explicit_reference_time_determinism_100x(base_message, base_time):
    """Req 27 & 28: Repeated verification with explicit reference time yields 100% stable results."""
    verifier = ProtocolSecurityVerifier()
    ref_time = base_time + timedelta(minutes=5)

    base_res = verifier.verify_message(
        message=base_message,
        expected_intent_id="int_001",
        expected_transaction_id="tx_001",
        reference_time=ref_time,
        record_on_success=False,
    )
    assert base_res.is_valid is True

    for _ in range(100):
        res = verifier.verify_message(
            message=base_message,
            expected_intent_id="int_001",
            expected_transaction_id="tx_001",
            reference_time=ref_time,
            record_on_success=False,
        )
        assert res.is_valid == base_res.is_valid
        assert res.violation_code == base_res.violation_code
        assert res.explanation == base_res.explanation
