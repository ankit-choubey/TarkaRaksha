"""
Protocol Security and Message Binding Module for TarkaRaksha (I2).

Provides:
1. AgentTransactionMessage representation with strict binding:
   - message_id, intent_id, transaction_id, attempt_id
   - sender, receiver, message_type
   - timestamp, expires_at
   - previous_message_hash, current_message_hash
2. Intent consumption tracking (ACTIVE, CONSUMED, EXPIRED, REVOKED).
3. Deterministic protocol attack detection:
   - REPLAY
   - INTENT_MISMATCH
   - TRANSACTION_MISMATCH
   - STALE_MESSAGE
   - DUPLICATE_MESSAGE
   - AGENT_ID_MISMATCH
   - STATE_DESYNC
4. Cryptographic hash-chain verification with canonical JSON serialization (SHA-256).
"""
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.domain.models.enums import IntentConsumptionState, TransactionState
from backend.app.domain.models.money import Money


class ProtocolViolationCode(str, Enum):
    """
    Deterministic detection codes for agent protocol and binding violations.
    """
    REPLAY = "REPLAY"
    INTENT_MISMATCH = "INTENT_MISMATCH"
    TRANSACTION_MISMATCH = "TRANSACTION_MISMATCH"
    STALE_MESSAGE = "STALE_MESSAGE"
    DUPLICATE_MESSAGE = "DUPLICATE_MESSAGE"
    AGENT_ID_MISMATCH = "AGENT_ID_MISMATCH"
    STATE_DESYNC = "STATE_DESYNC"
    HASH_CHAIN_MISMATCH = "HASH_CHAIN_MISMATCH"
    INTENT_NOT_ACTIVE = "INTENT_NOT_ACTIVE"


def canonicalize_for_hash(val: Any) -> Any:
    """Recursively normalizes values into canonical JSON primitives for deterministic hashing."""
    if isinstance(val, Money):
        return {"amount": val.amount, "currency": val.currency}
    if isinstance(val, datetime):
        return val.astimezone(timezone.utc).isoformat()
    if isinstance(val, Enum):
        return val.value
    if isinstance(val, (list, tuple, set)):
        return [canonicalize_for_hash(item) for item in val]
    if isinstance(val, dict):
        return {k: canonicalize_for_hash(v) for k, v in sorted(val.items())}
    return val


class AgentTransactionMessage(BaseModel):
    """
    Structured, tamper-evident envelope for agent transaction messages.
    Strictly binds identity, transaction scope, and chronological sequence.
    """
    message_id: str
    intent_id: str
    transaction_id: str
    attempt_id: str = "att_1"
    sender: str
    receiver: str = "tarkaraksha_control_plane"
    timestamp: datetime
    expires_at: Optional[datetime] = None
    message_type: str = "TRANSACTION_ACTION"
    payload: Dict[str, Any] = Field(default_factory=dict)
    claimed_state: Optional[TransactionState] = None
    evidence_refs: List[str] = Field(default_factory=list)
    previous_message_hash: Optional[str] = None
    current_message_hash: Optional[str] = None

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )

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
        """
        Computes deterministic SHA-256 hash over canonical message content
        including previous_message_hash (excluding current_message_hash itself).
        """
        data = {
            "message_id": self.message_id,
            "intent_id": self.intent_id,
            "transaction_id": self.transaction_id,
            "attempt_id": self.attempt_id,
            "sender": self.sender,
            "receiver": self.receiver,
            "timestamp": canonicalize_for_hash(self.timestamp),
            "expires_at": canonicalize_for_hash(self.expires_at) if self.expires_at else None,
            "message_type": self.message_type,
            "payload": canonicalize_for_hash(self.payload),
            "claimed_state": self.claimed_state.value if self.claimed_state else None,
            "evidence_refs": sorted(str(ref) for ref in self.evidence_refs),
            "previous_message_hash": self.previous_message_hash or "",
        }
        canonical_json = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    def with_computed_hash(self) -> "AgentTransactionMessage":
        """Returns a copy of the message with current_message_hash populated."""
        computed = self.compute_canonical_hash()
        d = self.model_dump()
        d["current_message_hash"] = computed
        return AgentTransactionMessage(**d)


class ProtocolVerificationOutcome(BaseModel):
    """
    Structured outcome of deterministic protocol binding and attack detection.
    """
    is_valid: bool
    violation_code: Optional[ProtocolViolationCode] = None
    explanation: str
    details: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )


class ProtocolSecurityVerifier:
    """
    Deterministic verification engine for agent protocol binding, replay defense,
    message-chain integrity, and attack detection.
    """

    def __init__(self):
        # Seen message IDs to detect duplicate messages / replays
        self._seen_message_ids: Set[str] = set()
        # Mapping from transaction_id to latest message hash in chain
        self._latest_hashes: Dict[str, str] = {}
        # Mapping from intent_id to consumption state
        self._intent_states: Dict[str, IntentConsumptionState] = {}
        # Mapping from intent_id to bound transaction_id
        self._intent_to_tx: Dict[str, str] = {}

    def register_intent(
        self,
        intent_id: str,
        initial_state: IntentConsumptionState = IntentConsumptionState.ACTIVE,
    ) -> None:
        """Registers an intent into the tracker."""
        self._intent_states[intent_id] = initial_state

    def get_intent_state(self, intent_id: str) -> IntentConsumptionState:
        """Returns the current consumption state of an intent (defaults to ACTIVE)."""
        return self._intent_states.get(intent_id, IntentConsumptionState.ACTIVE)

    def set_intent_state(self, intent_id: str, state: IntentConsumptionState) -> None:
        """Sets the consumption state of an intent."""
        self._intent_states[intent_id] = state

    def consume_intent(self, intent_id: str, transaction_id: str) -> None:
        """Marks an intent as CONSUMED and bound to a specific transaction."""
        self._intent_states[intent_id] = IntentConsumptionState.CONSUMED
        self._intent_to_tx[intent_id] = transaction_id

    def verify_message(
        self,
        message: AgentTransactionMessage,
        expected_intent_id: str,
        expected_transaction_id: str,
        expected_agent_id: Optional[str] = None,
        expected_attempt_id: Optional[str] = None,
        authoritative_state: Optional[TransactionState] = None,
        reference_time: Optional[datetime] = None,
        require_hash_chain: bool = True,
        record_on_success: bool = True,
    ) -> ProtocolVerificationOutcome:
        """
        Deterministically verifies all 7 protocol attack dimensions:
        1. Identifier Binding (INTENT_MISMATCH, TRANSACTION_MISMATCH, AGENT_ID_MISMATCH).
        2. Uniqueness / Replay (DUPLICATE_MESSAGE, REPLAY).
        3. Intent Consumption State (INTENT_NOT_ACTIVE / REPLAY).
        4. Freshness / Expiry (STALE_MESSAGE).
        5. State Consistency (STATE_DESYNC).
        6. Message-Chain Cryptographic Integrity (HASH_CHAIN_MISMATCH).
        """
        ref = reference_time or message.timestamp
        if ref.tzinfo is None:
            raise ValueError("reference_time must be timezone-aware (e.g. UTC)")

        # 1. Intent Identifier Binding
        if message.intent_id != expected_intent_id:
            return ProtocolVerificationOutcome(
                is_valid=False,
                violation_code=ProtocolViolationCode.INTENT_MISMATCH,
                explanation=f"Message intent_id '{message.intent_id}' does not match expected '{expected_intent_id}'",
                details={"message_intent_id": message.intent_id, "expected_intent_id": expected_intent_id},
            )

        # 2. Transaction Identifier Binding
        if message.transaction_id != expected_transaction_id:
            return ProtocolVerificationOutcome(
                is_valid=False,
                violation_code=ProtocolViolationCode.TRANSACTION_MISMATCH,
                explanation=f"Message transaction_id '{message.transaction_id}' does not match expected '{expected_transaction_id}'",
                details={"message_transaction_id": message.transaction_id, "expected_transaction_id": expected_transaction_id},
            )

        # 3. Agent Identity Binding
        if expected_agent_id and message.sender != expected_agent_id:
            return ProtocolVerificationOutcome(
                is_valid=False,
                violation_code=ProtocolViolationCode.AGENT_ID_MISMATCH,
                explanation=f"Message sender '{message.sender}' does not match expected agent identity '{expected_agent_id}'",
                details={"sender": message.sender, "expected_agent_id": expected_agent_id},
            )

        # 4. Attempt ID Binding (if specified)
        if expected_attempt_id and message.attempt_id != expected_attempt_id:
            return ProtocolVerificationOutcome(
                is_valid=False,
                violation_code=ProtocolViolationCode.TRANSACTION_MISMATCH,
                explanation=f"Message attempt_id '{message.attempt_id}' does not match expected attempt '{expected_attempt_id}'",
                details={"attempt_id": message.attempt_id, "expected_attempt_id": expected_attempt_id},
            )

        # 5. Intent Consumption State / Replay
        curr_intent_state = self.get_intent_state(message.intent_id)
        if curr_intent_state == IntentConsumptionState.CONSUMED:
            # Check if intent was already bound to a different transaction
            bound_tx = self._intent_to_tx.get(message.intent_id)
            if bound_tx and bound_tx != message.transaction_id:
                return ProtocolVerificationOutcome(
                    is_valid=False,
                    violation_code=ProtocolViolationCode.REPLAY,
                    explanation=f"Intent '{message.intent_id}' is already CONSUMED by transaction '{bound_tx}'. Replay rejected.",
                    details={"intent_id": message.intent_id, "bound_tx": bound_tx, "state": curr_intent_state.value},
                )
        elif curr_intent_state in (IntentConsumptionState.EXPIRED, IntentConsumptionState.REVOKED):
            return ProtocolVerificationOutcome(
                is_valid=False,
                violation_code=ProtocolViolationCode.INTENT_NOT_ACTIVE,
                explanation=f"Intent '{message.intent_id}' is in non-active state '{curr_intent_state.value}'. Action rejected.",
                details={"intent_id": message.intent_id, "state": curr_intent_state.value},
            )

        # 6. Duplicate Message ID (Replay / Duplicate)
        if message.message_id in self._seen_message_ids:
            return ProtocolVerificationOutcome(
                is_valid=False,
                violation_code=ProtocolViolationCode.DUPLICATE_MESSAGE,
                explanation=f"Message ID '{message.message_id}' has already been processed. Replay/Duplicate rejected.",
                details={"message_id": message.message_id},
            )

        # 7. Message Freshness & Expiration (now <= expiry)
        if message.expires_at is not None:
            if ref > message.expires_at:
                return ProtocolVerificationOutcome(
                    is_valid=False,
                    violation_code=ProtocolViolationCode.STALE_MESSAGE,
                    explanation=f"Message '{message.message_id}' is expired. Reference time {ref.isoformat()} > expires_at {message.expires_at.isoformat()}",
                    details={"expires_at": message.expires_at.isoformat(), "reference_time": ref.isoformat()},
                )

        # 8. State Desynchronization Check
        if authoritative_state is not None and message.claimed_state is not None:
            # If agent message claims a state divergent from authoritative state machine
            if message.claimed_state != authoritative_state:
                return ProtocolVerificationOutcome(
                    is_valid=False,
                    violation_code=ProtocolViolationCode.STATE_DESYNC,
                    explanation=(
                        f"Agent claimed state '{message.claimed_state.value}' desynchronized from "
                        f"authoritative transaction state '{authoritative_state.value}'"
                    ),
                    details={
                        "claimed_state": message.claimed_state.value,
                        "authoritative_state": authoritative_state.value,
                    },
                )

        # 9. Cryptographic Hash-Chain Verification
        if require_hash_chain:
            expected_prev_hash = self._latest_hashes.get(message.transaction_id)
            if expected_prev_hash is not None:
                # Subsequent message must reference the exact previous hash
                if message.previous_message_hash != expected_prev_hash:
                    return ProtocolVerificationOutcome(
                        is_valid=False,
                        violation_code=ProtocolViolationCode.HASH_CHAIN_MISMATCH,
                        explanation=(
                            f"Previous message hash mismatch in chain for transaction '{message.transaction_id}'. "
                            f"Expected '{expected_prev_hash}', got '{message.previous_message_hash}'"
                        ),
                        details={
                            "expected_previous_hash": expected_prev_hash,
                            "provided_previous_hash": message.previous_message_hash,
                        },
                    )
            elif message.previous_message_hash not in (None, ""):
                # First message had an unexpected previous hash
                return ProtocolVerificationOutcome(
                    is_valid=False,
                    violation_code=ProtocolViolationCode.HASH_CHAIN_MISMATCH,
                    explanation=f"First message in transaction '{message.transaction_id}' should have empty previous_message_hash",
                    details={"provided_previous_hash": message.previous_message_hash},
                )

            # Verify current_message_hash matches computed hash
            computed_current = message.compute_canonical_hash()
            if message.current_message_hash is not None and message.current_message_hash != computed_current:
                return ProtocolVerificationOutcome(
                    is_valid=False,
                    violation_code=ProtocolViolationCode.HASH_CHAIN_MISMATCH,
                    explanation=(
                        f"Current message hash tampering detected. "
                        f"Provided '{message.current_message_hash}' != computed '{computed_current}'"
                    ),
                    details={
                        "provided_hash": message.current_message_hash,
                        "computed_hash": computed_current,
                    },
                )

        # Record successful message if requested
        if record_on_success:
            self._seen_message_ids.add(message.message_id)
            curr_hash = message.current_message_hash or message.compute_canonical_hash()
            self._latest_hashes[message.transaction_id] = curr_hash

        return ProtocolVerificationOutcome(
            is_valid=True,
            violation_code=None,
            explanation="Message strictly satisfies all transaction binding, freshness, state, and hash-chain constraints",
            details={
                "message_id": message.message_id,
                "transaction_id": message.transaction_id,
                "intent_id": message.intent_id,
            },
        )
