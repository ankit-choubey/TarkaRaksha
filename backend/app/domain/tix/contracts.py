"""Authoritative Domain Contracts for I6 — TIX: TarkaRaksha Integrity Exchange.

TIX is a lightweight internal exchange format allowing:
BUYER AGENT <-> TARKARAKSHA <-> MERCHANT AGENT
to exchange transaction-integrity information.

TIX transports claims.
Deterministic TarkaRaksha logic verifies claims.
Authoritative payment evidence remains authoritative.
Zero payment authorization authority resides in TIX.
"""
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.domain.models.money import Money


def canonicalize_for_tix_hash(val: Any) -> Any:
    """Recursively normalizes values into canonical JSON primitives for deterministic hashing."""
    if isinstance(val, Money):
        return {"amount": val.amount, "currency": val.currency}
    if isinstance(val, datetime):
        return val.astimezone(timezone.utc).isoformat()
    if isinstance(val, Enum):
        return val.value
    if isinstance(val, (list, tuple, set)):
        return [canonicalize_for_tix_hash(item) for item in val]
    if isinstance(val, dict):
        return {k: canonicalize_for_tix_hash(v) for k, v in sorted(val.items())}
    return val


class TIXMessageType(str, Enum):
    """Bounded canonical set of 12 TIX message types (I6.2)."""
    INTENT = "INTENT"
    OFFER = "OFFER"
    EVIDENCE_REQUEST = "EVIDENCE_REQUEST"
    EVIDENCE_RESPONSE = "EVIDENCE_RESPONSE"
    INTEGRITY_CHECK = "INTEGRITY_CHECK"
    DRIFT_NOTICE = "DRIFT_NOTICE"
    REMEDIATION_REQUEST = "REMEDIATION_REQUEST"
    REMEDIATION_RESPONSE = "REMEDIATION_RESPONSE"
    REVALIDATION = "REVALIDATION"
    AUTHORIZATION = "AUTHORIZATION"
    EXECUTION = "EXECUTION"
    OUTCOME = "OUTCOME"


class TIXParticipantRole(str, Enum):
    """Canonical participant roles in TIX communication."""
    BUYER_AGENT = "buyer_agent"
    MERCHANT_AGENT = "merchant_agent"
    TARKARAKSHA_ROUTER = "tarkaraksha_router"
    TARKARAKSHA_CORE = "tarkaraksha_core"


class TIXViolationCode(str, Enum):
    """Deterministic detection and error codes for TIX protocol violations."""
    REPLAY = "REPLAY"
    INTENT_MISMATCH = "INTENT_MISMATCH"
    TRANSACTION_MISMATCH = "TRANSACTION_MISMATCH"
    ATTEMPT_MISMATCH = "ATTEMPT_MISMATCH"
    SENDER_MISMATCH = "SENDER_MISMATCH"
    RECEIVER_MISMATCH = "RECEIVER_MISMATCH"
    EXPIRED_MESSAGE = "EXPIRED_MESSAGE"
    FUTURE_TIMESTAMP = "FUTURE_TIMESTAMP"
    HASH_MISMATCH = "HASH_MISMATCH"
    HASH_CHAIN_MISMATCH = "HASH_CHAIN_MISMATCH"
    DUPLICATE_MESSAGE_ID = "DUPLICATE_MESSAGE_ID"
    MALFORMED_PAYLOAD = "MALFORMED_PAYLOAD"
    UNAUTHORIZED_PAYMENT_CLAIM = "UNAUTHORIZED_PAYMENT_CLAIM"
    AUTHORITY_BREACH = "AUTHORITY_BREACH"


class TIXMessage(BaseModel):
    """Structured, tamper-evident envelope for TIX messages (I6.3).

    Strictly binds transaction identity, chronological sequence,
    and agent roles with canonical SHA-256 hash chaining.
    """
    message_id: str
    transaction_id: str
    intent_id: str
    attempt_id: str = "att_1"
    sender: str
    receiver: str
    timestamp: datetime
    expires_at: Optional[datetime] = None
    message_type: TIXMessageType
    payload: Dict[str, Any] = Field(default_factory=dict)
    evidence_refs: List[str] = Field(default_factory=list)
    capability_refs: List[str] = Field(default_factory=list)
    policy_version: Optional[str] = None
    rules_version: Optional[str] = None
    previous_message_hash: Optional[str] = None
    current_message_hash: Optional[str] = None

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )

    @field_validator("message_id", "transaction_id", "intent_id", "attempt_id", "sender", "receiver")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Identifier fields cannot be empty or whitespace.")
        return v.strip()

    @field_validator("timestamp", "expires_at", mode="before")
    @classmethod
    def validate_timezone(cls, v: Any) -> Optional[datetime]:
        if v is None:
            return None
        if isinstance(v, str):
            dt = datetime.fromisoformat(v)
        elif isinstance(v, datetime):
            dt = v
        else:
            raise TypeError(f"Timestamp must be datetime or ISO string, got {type(v).__name__}")
        if dt.tzinfo is None:
            raise ValueError("Timestamp must be timezone-aware (e.g. UTC)")
        return dt

    def compute_canonical_hash(self) -> str:
        """Computes deterministic SHA-256 hash over canonical message content.

        Excludes current_message_hash itself so that hashing is repeatable.
        """
        data = {
            "message_id": self.message_id,
            "transaction_id": self.transaction_id,
            "intent_id": self.intent_id,
            "attempt_id": self.attempt_id,
            "sender": self.sender,
            "receiver": self.receiver,
            "timestamp": canonicalize_for_tix_hash(self.timestamp),
            "expires_at": canonicalize_for_tix_hash(self.expires_at) if self.expires_at else None,
            "message_type": self.message_type.value,
            "payload": canonicalize_for_tix_hash(self.payload),
            "evidence_refs": sorted(str(ref) for ref in self.evidence_refs),
            "capability_refs": sorted(str(cap) for cap in self.capability_refs),
            "policy_version": self.policy_version or "",
            "rules_version": self.rules_version or "",
            "previous_message_hash": self.previous_message_hash or "",
        }
        canonical_json = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    def with_computed_hash(self) -> "TIXMessage":
        """Returns an immutable copy with current_message_hash populated."""
        computed = self.compute_canonical_hash()
        d = self.model_dump()
        d["current_message_hash"] = computed
        return TIXMessage(**d)

    def is_expired(self, reference_time: datetime) -> bool:
        """Deterministically checks whether the message has expired against reference_time."""
        if self.expires_at is None:
            return False
        ref = reference_time if reference_time.tzinfo is not None else reference_time.replace(tzinfo=timezone.utc)
        return ref > self.expires_at


class TIXVerificationOutcome(BaseModel):
    """Structured outcome of deterministic TIX protocol verification."""
    is_valid: bool
    violation_code: Optional[TIXViolationCode] = None
    explanation: str
    details: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )
