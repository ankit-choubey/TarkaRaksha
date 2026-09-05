"""Unit tests for I6 — TIX Domain Contracts.

Validates:
1. Valid TIXMessage creation with all canonical fields.
2. All 12 TIXMessageType enum values.
3. Empty or whitespace string validation for identifiers.
4. Timezone awareness enforcement (rejection of naive datetimes).
5. Strict Pydantic model validation (extra="forbid", frozen=True).
6. Deterministic canonical hash computation (SHA-256).
7. Hash sensitivity (modifying payload, timestamps, or headers changes hash).
8. with_computed_hash helper.
9. Deterministic is_expired evaluation against reference_time.
"""
from datetime import datetime, timedelta, timezone
import pytest
from pydantic import ValidationError

from backend.app.domain.tix.contracts import (
    TIXMessage,
    TIXMessageType,
    TIXParticipantRole,
    TIXVerificationOutcome,
    TIXViolationCode,
)


@pytest.fixture
def base_time() -> datetime:
    return datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def valid_message(base_time: datetime) -> TIXMessage:
    return TIXMessage(
        message_id="tix_msg_001",
        transaction_id="tx_001",
        intent_id="intent_001",
        attempt_id="att_1",
        sender="buyer_agent",
        receiver="tarkaraksha_router",
        timestamp=base_time,
        expires_at=base_time + timedelta(minutes=5),
        message_type=TIXMessageType.INTENT,
        payload={"max_total": 50000, "sku": "SERVER-256"},
        evidence_refs=["ev_001"],
        capability_refs=["cap_001"],
        policy_version="v1.0",
        rules_version="v2.0",
        previous_message_hash=None,
    )


def test_valid_tix_message_instantiation(valid_message: TIXMessage, base_time: datetime):
    assert valid_message.message_id == "tix_msg_001"
    assert valid_message.transaction_id == "tx_001"
    assert valid_message.intent_id == "intent_001"
    assert valid_message.attempt_id == "att_1"
    assert valid_message.sender == "buyer_agent"
    assert valid_message.receiver == "tarkaraksha_router"
    assert valid_message.timestamp == base_time
    assert valid_message.message_type == TIXMessageType.INTENT
    assert valid_message.payload == {"max_total": 50000, "sku": "SERVER-256"}
    assert valid_message.evidence_refs == ["ev_001"]
    assert valid_message.capability_refs == ["cap_001"]
    assert valid_message.policy_version == "v1.0"
    assert valid_message.rules_version == "v2.0"
    assert valid_message.previous_message_hash is None
    assert valid_message.current_message_hash is None


def test_all_twelve_message_types_supported():
    expected = {
        "INTENT",
        "OFFER",
        "EVIDENCE_REQUEST",
        "EVIDENCE_RESPONSE",
        "INTEGRITY_CHECK",
        "DRIFT_NOTICE",
        "REMEDIATION_REQUEST",
        "REMEDIATION_RESPONSE",
        "REVALIDATION",
        "AUTHORIZATION",
        "EXECUTION",
        "OUTCOME",
    }
    actual = {m.value for m in TIXMessageType}
    assert actual == expected


@pytest.mark.parametrize(
    "field",
    ["message_id", "transaction_id", "intent_id", "attempt_id", "sender", "receiver"],
)
def test_empty_or_whitespace_identifiers_rejected(valid_message: TIXMessage, field: str):
    data = valid_message.model_dump()
    data[field] = "   "
    with pytest.raises(ValidationError):
        TIXMessage(**data)

    data[field] = ""
    with pytest.raises(ValidationError):
        TIXMessage(**data)


def test_naive_datetime_rejected(valid_message: TIXMessage):
    data = valid_message.model_dump()
    data["timestamp"] = datetime(2026, 9, 5, 12, 0, 0)  # naive
    with pytest.raises(ValidationError):
        TIXMessage(**data)


def test_extra_fields_forbidden(valid_message: TIXMessage):
    data = valid_message.model_dump()
    data["rogue_field"] = "unauthorized"
    with pytest.raises(ValidationError):
        TIXMessage(**data)


def test_model_immutability(valid_message: TIXMessage):
    with pytest.raises(ValidationError):
        valid_message.sender = "rogue_agent"  # type: ignore


def test_canonical_hash_computation_deterministic(valid_message: TIXMessage):
    h1 = valid_message.compute_canonical_hash()
    h2 = valid_message.compute_canonical_hash()
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex string


def test_hash_sensitivity_to_changes(valid_message: TIXMessage):
    base_hash = valid_message.compute_canonical_hash()

    # Change payload
    d1 = valid_message.model_dump()
    d1["payload"] = {"max_total": 50001, "sku": "SERVER-256"}
    m1 = TIXMessage(**d1)
    assert m1.compute_canonical_hash() != base_hash

    # Change previous_message_hash
    d2 = valid_message.model_dump()
    d2["previous_message_hash"] = "abc123"
    m2 = TIXMessage(**d2)
    assert m2.compute_canonical_hash() != base_hash

    # Change message_type
    d3 = valid_message.model_dump()
    d3["message_type"] = TIXMessageType.OFFER
    m3 = TIXMessage(**d3)
    assert m3.compute_canonical_hash() != base_hash


def test_with_computed_hash_populates_current_hash(valid_message: TIXMessage):
    hashed = valid_message.with_computed_hash()
    assert hashed.current_message_hash is not None
    assert hashed.current_message_hash == valid_message.compute_canonical_hash()
    # original remains untouched
    assert valid_message.current_message_hash is None


def test_is_expired(valid_message: TIXMessage, base_time: datetime):
    # base_time + 4 mins: not expired
    assert not valid_message.is_expired(base_time + timedelta(minutes=4))
    # base_time + 5 mins 1 sec: expired
    assert valid_message.is_expired(base_time + timedelta(minutes=5, seconds=1))
