"""Deterministic Protocol and Exchange Verifier for TIX (I6).

Enforces:
1. Message identity and non-empty string integrity.
2. Temporal validity: timezone awareness, expiration against explicit reference_time, future timestamp bounding.
3. Strict transaction context binding (intent_id, transaction_id, attempt_id, sender, receiver).
4. Replay and duplication defense (seen message ID tracking).
5. Cryptographic hash and hash-chain continuity (SHA-256).
6. Anti-spoofing and authority boundary enforcement:
   - AI/Agents cannot authorize payment.
   - AI/Agents cannot declare authoritative PASS or override deterministic verdicts.
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Set

from backend.app.domain.tix.contracts import (
    TIXMessage,
    TIXMessageType,
    TIXParticipantRole,
    TIXVerificationOutcome,
    TIXViolationCode,
)


class TIXExchangeVerifier:
    """Deterministic verifier for TIX messages and message chains."""

    def __init__(self, max_clock_skew_seconds: int = 60):
        self.max_clock_skew = timedelta(seconds=max_clock_skew_seconds)

    def verify_message(
        self,
        message: TIXMessage,
        expected_intent_id: Optional[str] = None,
        expected_transaction_id: Optional[str] = None,
        expected_attempt_id: Optional[str] = None,
        expected_sender: Optional[str] = None,
        expected_receiver: Optional[str] = None,
        reference_time: Optional[datetime] = None,
        seen_message_ids: Optional[Set[str]] = None,
        expected_previous_hash: Optional[str] = None,
    ) -> TIXVerificationOutcome:
        """Deterministically evaluates a TIX message against protocol rules and context."""
        # 1. Duplication / Replay check
        if seen_message_ids is not None and message.message_id in seen_message_ids:
            return TIXVerificationOutcome(
                is_valid=False,
                violation_code=TIXViolationCode.DUPLICATE_MESSAGE_ID,
                explanation=f"Duplicate message_id '{message.message_id}' detected in exchange session.",
                details={"message_id": message.message_id},
            )

        # 2. Time & Freshness checks
        if reference_time is not None:
            ref = reference_time if reference_time.tzinfo is not None else reference_time.replace(tzinfo=timezone.utc)
            if message.is_expired(ref):
                return TIXVerificationOutcome(
                    is_valid=False,
                    violation_code=TIXViolationCode.EXPIRED_MESSAGE,
                    explanation=f"Message '{message.message_id}' expired at {message.expires_at} (ref={ref}).",
                    details={
                        "expires_at": message.expires_at.isoformat() if message.expires_at else None,
                        "reference_time": ref.isoformat(),
                    },
                )
            if message.timestamp > (ref + self.max_clock_skew):
                return TIXVerificationOutcome(
                    is_valid=False,
                    violation_code=TIXViolationCode.FUTURE_TIMESTAMP,
                    explanation=f"Message timestamp {message.timestamp} is too far in the future compared to reference {ref}.",
                    details={
                        "timestamp": message.timestamp.isoformat(),
                        "reference_time": ref.isoformat(),
                    },
                )

        # 3. Identity and Binding Checks
        if expected_intent_id is not None and message.intent_id != expected_intent_id:
            return TIXVerificationOutcome(
                is_valid=False,
                violation_code=TIXViolationCode.INTENT_MISMATCH,
                explanation=f"Message intent_id '{message.intent_id}' does not match expected '{expected_intent_id}'.",
                details={"expected": expected_intent_id, "actual": message.intent_id},
            )

        if expected_transaction_id is not None and message.transaction_id != expected_transaction_id:
            return TIXVerificationOutcome(
                is_valid=False,
                violation_code=TIXViolationCode.TRANSACTION_MISMATCH,
                explanation=f"Message transaction_id '{message.transaction_id}' does not match expected '{expected_transaction_id}'.",
                details={"expected": expected_transaction_id, "actual": message.transaction_id},
            )

        if expected_attempt_id is not None and message.attempt_id != expected_attempt_id:
            return TIXVerificationOutcome(
                is_valid=False,
                violation_code=TIXViolationCode.ATTEMPT_MISMATCH,
                explanation=f"Message attempt_id '{message.attempt_id}' does not match expected '{expected_attempt_id}'.",
                details={"expected": expected_attempt_id, "actual": message.attempt_id},
            )

        if expected_sender is not None and message.sender != expected_sender:
            return TIXVerificationOutcome(
                is_valid=False,
                violation_code=TIXViolationCode.SENDER_MISMATCH,
                explanation=f"Message sender '{message.sender}' does not match expected '{expected_sender}'.",
                details={"expected": expected_sender, "actual": message.sender},
            )

        if expected_receiver is not None and message.receiver != expected_receiver:
            return TIXVerificationOutcome(
                is_valid=False,
                violation_code=TIXViolationCode.RECEIVER_MISMATCH,
                explanation=f"Message receiver '{message.receiver}' does not match expected '{expected_receiver}'.",
                details={"expected": expected_receiver, "actual": message.receiver},
            )

        # 4. Canonical Hash Verification
        if message.current_message_hash is not None:
            expected_hash = message.compute_canonical_hash()
            if message.current_message_hash != expected_hash:
                return TIXVerificationOutcome(
                    is_valid=False,
                    violation_code=TIXViolationCode.HASH_MISMATCH,
                    explanation="Message current_message_hash does not match computed canonical hash.",
                    details={
                        "provided_hash": message.current_message_hash,
                        "computed_hash": expected_hash,
                    },
                )

        # 5. Hash Chain Continuity
        if expected_previous_hash is not None:
            actual_prev = message.previous_message_hash or ""
            if actual_prev != expected_previous_hash:
                return TIXVerificationOutcome(
                    is_valid=False,
                    violation_code=TIXViolationCode.HASH_CHAIN_MISMATCH,
                    explanation=f"Hash chain broken. Expected previous_message_hash '{expected_previous_hash}', got '{actual_prev}'.",
                    details={
                        "expected_previous_hash": expected_previous_hash,
                        "actual_previous_hash": actual_prev,
                    },
                )

        # 6. Anti-Spoofing and Authority Boundary Enforcement
        # Non-TarkaRaksha senders (e.g. buyer_agent or merchant_agent) must NEVER declare payment authorization or authoritative PASS
        is_tarkaraksha_sender = message.sender in {
            TIXParticipantRole.TARKARAKSHA_CORE.value,
            TIXParticipantRole.TARKARAKSHA_ROUTER.value,
            "tarkaraksha",
            "tarkaraksha_control_plane",
        }

        # Check for unauthorized payment authorization attempts
        if not is_tarkaraksha_sender:
            if message.message_type == TIXMessageType.AUTHORIZATION:
                return TIXVerificationOutcome(
                    is_valid=False,
                    violation_code=TIXViolationCode.UNAUTHORIZED_PAYMENT_CLAIM,
                    explanation=f"Sender '{message.sender}' is not authorized to emit AUTHORIZATION messages.",
                    details={"sender": message.sender, "message_type": message.message_type.value},
                )

            # Check payload for rogue payment authorization or authoritative verdict claims
            payload = message.payload or {}
            unauthorized_keys = {"payment_authorized", "authorize_payment", "bypass_integrity", "force_pass"}
            if any(k in payload and payload[k] for k in unauthorized_keys):
                return TIXVerificationOutcome(
                    is_valid=False,
                    violation_code=TIXViolationCode.UNAUTHORIZED_PAYMENT_CLAIM,
                    explanation=f"Sender '{message.sender}' attempted to claim unauthorized payment authorization in payload.",
                    details={"payload_keys": list(payload.keys())},
                )

            if message.message_type == TIXMessageType.OUTCOME and payload.get("authoritative") is True:
                return TIXVerificationOutcome(
                    is_valid=False,
                    violation_code=TIXViolationCode.AUTHORITY_BREACH,
                    explanation=f"Sender '{message.sender}' attempted to declare authoritative OUTCOME.",
                    details={"sender": message.sender},
                )

        return TIXVerificationOutcome(
            is_valid=True,
            violation_code=None,
            explanation="TIX message strictly conforms to protocol invariants.",
            details={"message_id": message.message_id, "message_type": message.message_type.value},
        )
