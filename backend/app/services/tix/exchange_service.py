"""TIX Exchange Service for TarkaRaksha (I6).

Coordinates the lightweight internal exchange format between:
BUYER AGENT <-> TARKARAKSHA <-> MERCHANT AGENT

Responsibilities:
1. Validates and appends TIX messages to an in-memory chronological ledger.
2. Maintains cryptographic SHA-256 hash chains per transaction_id.
3. Enforces deterministic replay, expiration, and identity binding checks.
4. Bridges advisory agent claims to TarkaRaksha's deterministic integrity engine without
   ever elevating advisory claims into authoritative payment authorizations.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.app.domain.models.evidence import CanonicalEvent, Evidence
from backend.app.domain.models.intent import IntentContract
from backend.app.domain.models.enums import IntegrityStatus
from backend.app.domain.models.integrity import IntegrityResult
from backend.app.domain.tix.contracts import (
    TIXMessage,
    TIXMessageType,
    TIXParticipantRole,
    TIXVerificationOutcome,
    TIXViolationCode,
)
from backend.app.domain.tix.verifier import TIXExchangeVerifier
from backend.app.services.evaluation import evaluate_integrity


class TIXExchangeService:
    """Manages TIX protocol exchanges, verification, and ledger recording."""

    def __init__(self, verifier: Optional[TIXExchangeVerifier] = None):
        self.verifier = verifier or TIXExchangeVerifier()
        self._ledgers: Dict[str, List[TIXMessage]] = {}
        self._seen_message_ids: Set[str] = set()

    def append_and_verify(
        self,
        message: TIXMessage,
        expected_intent_id: Optional[str] = None,
        expected_attempt_id: Optional[str] = None,
        expected_sender: Optional[str] = None,
        expected_receiver: Optional[str] = None,
        reference_time: Optional[datetime] = None,
    ) -> Tuple[TIXVerificationOutcome, Optional[TIXMessage]]:
        """Verifies a TIX message, computes canonical hash, and commits it to the transaction ledger.

        Returns (TIXVerificationOutcome, hashed_message_if_valid).
        """
        ledger = self._ledgers.get(message.transaction_id, [])
        expected_prev_hash = ledger[-1].current_message_hash if ledger else None

        # Verify through the deterministic verifier
        outcome = self.verifier.verify_message(
            message=message,
            expected_intent_id=expected_intent_id,
            expected_transaction_id=message.transaction_id,
            expected_attempt_id=expected_attempt_id,
            expected_sender=expected_sender,
            expected_receiver=expected_receiver,
            reference_time=reference_time,
            seen_message_ids=self._seen_message_ids,
            expected_previous_hash=expected_prev_hash,
        )

        if not outcome.is_valid:
            return outcome, None

        # Populate current_message_hash if not provided
        committed_msg = message if message.current_message_hash else message.with_computed_hash()

        # Commit to ledger and track seen message ID
        if message.transaction_id not in self._ledgers:
            self._ledgers[message.transaction_id] = []
        self._ledgers[message.transaction_id].append(committed_msg)
        self._seen_message_ids.add(committed_msg.message_id)

        return outcome, committed_msg

    def get_ledger(self, transaction_id: str) -> List[TIXMessage]:
        """Returns the immutable list of messages in chronological order for the transaction."""
        return list(self._ledgers.get(transaction_id, []))

    def get_chain_hash(self, transaction_id: str) -> Optional[str]:
        """Returns the current head hash of the transaction's message chain."""
        ledger = self._ledgers.get(transaction_id, [])
        return ledger[-1].current_message_hash if ledger else None

    def verify_chain_integrity(self, transaction_id: str) -> Tuple[bool, Optional[str]]:
        """Audits the full cryptographic hash chain of a transaction ledger."""
        ledger = self._ledgers.get(transaction_id, [])
        if not ledger:
            return True, None

        expected_prev = None
        for idx, msg in enumerate(ledger):
            # Check previous hash pointer
            actual_prev = msg.previous_message_hash
            if actual_prev != expected_prev:
                return (
                    False,
                    f"Message at index {idx} ({msg.message_id}) expected previous hash '{expected_prev}', got '{actual_prev}'.",
                )

            # Check computed hash
            computed = msg.compute_canonical_hash()
            if msg.current_message_hash != computed:
                return (
                    False,
                    f"Message at index {idx} ({msg.message_id}) computed hash '{computed}' does not match '{msg.current_message_hash}'.",
                )

            expected_prev = msg.current_message_hash

        return True, None

    # --- Factory and Builder Helpers ---

    def build_intent_message(
        self,
        message_id: str,
        intent: IntentContract,
        transaction_id: str,
        sender: str = TIXParticipantRole.BUYER_AGENT.value,
        receiver: str = TIXParticipantRole.TARKARAKSHA_ROUTER.value,
        attempt_id: str = "att_1",
        expires_at: Optional[datetime] = None,
        previous_hash: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ) -> TIXMessage:
        """Constructs an INTENT message declaring authorized buyer constraints."""
        ts = timestamp or intent.issued_at
        payload = {
            "intent_id": intent.intent_id,
            "issued_by": intent.issued_by,
            "max_total_paise": intent.max_total.amount,
            "currency": intent.max_total.currency,
            "allowed_substitutions": intent.allowed_substitutions,
            "allow_partial": intent.allow_partial,
            "items": [{"sku": item.sku, "quantity": item.quantity} for item in intent.items],
            "item_count": len(intent.items),
        }
        msg = TIXMessage(
            message_id=message_id,
            transaction_id=transaction_id,
            intent_id=intent.intent_id,
            attempt_id=attempt_id,
            sender=sender,
            receiver=receiver,
            timestamp=ts,
            expires_at=expires_at or intent.expires_at,
            message_type=TIXMessageType.INTENT,
            payload=payload,
            previous_message_hash=previous_hash,
        )
        return msg.with_computed_hash()

    def build_offer_message(
        self,
        message_id: str,
        intent_id: str,
        transaction_id: str,
        offer_payload: Dict[str, Any],
        sender: str = TIXParticipantRole.MERCHANT_AGENT.value,
        receiver: str = TIXParticipantRole.TARKARAKSHA_ROUTER.value,
        attempt_id: str = "att_1",
        evidence_refs: Optional[List[str]] = None,
        capability_refs: Optional[List[str]] = None,
        policy_version: Optional[str] = None,
        expires_at: Optional[datetime] = None,
        previous_hash: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ) -> TIXMessage:
        """Constructs an OFFER message carrying merchant-attested terms."""
        ts = timestamp or datetime.now(timezone.utc)
        msg = TIXMessage(
            message_id=message_id,
            transaction_id=transaction_id,
            intent_id=intent_id,
            attempt_id=attempt_id,
            sender=sender,
            receiver=receiver,
            timestamp=ts,
            expires_at=expires_at,
            message_type=TIXMessageType.OFFER,
            payload=offer_payload,
            evidence_refs=evidence_refs or [],
            capability_refs=capability_refs or [],
            policy_version=policy_version,
            previous_message_hash=previous_hash,
        )
        return msg.with_computed_hash()

    def build_integrity_check_message(
        self,
        message_id: str,
        intent_id: str,
        transaction_id: str,
        sender: str = TIXParticipantRole.TARKARAKSHA_ROUTER.value,
        receiver: str = TIXParticipantRole.TARKARAKSHA_CORE.value,
        attempt_id: str = "att_1",
        evidence_refs: Optional[List[str]] = None,
        previous_hash: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ) -> TIXMessage:
        """Constructs an INTEGRITY_CHECK message requesting deterministic verification."""
        ts = timestamp or datetime.now(timezone.utc)
        msg = TIXMessage(
            message_id=message_id,
            transaction_id=transaction_id,
            intent_id=intent_id,
            attempt_id=attempt_id,
            sender=sender,
            receiver=receiver,
            timestamp=ts,
            message_type=TIXMessageType.INTEGRITY_CHECK,
            payload={"action": "VERIFY_INTEGRITY"},
            evidence_refs=evidence_refs or [],
            previous_message_hash=previous_hash,
        )
        return msg.with_computed_hash()

    def build_drift_notice_message(
        self,
        message_id: str,
        intent_id: str,
        transaction_id: str,
        violations: List[str],
        sender: str = TIXParticipantRole.TARKARAKSHA_CORE.value,
        receiver: str = TIXParticipantRole.BUYER_AGENT.value,
        attempt_id: str = "att_1",
        previous_hash: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ) -> TIXMessage:
        """Constructs a DRIFT_NOTICE message notifying agents of deterministic violations."""
        ts = timestamp or datetime.now(timezone.utc)
        msg = TIXMessage(
            message_id=message_id,
            transaction_id=transaction_id,
            intent_id=intent_id,
            attempt_id=attempt_id,
            sender=sender,
            receiver=receiver,
            timestamp=ts,
            message_type=TIXMessageType.DRIFT_NOTICE,
            payload={"status": "DRIFT", "violations": violations},
            previous_message_hash=previous_hash,
        )
        return msg.with_computed_hash()

    def build_remediation_request_message(
        self,
        message_id: str,
        intent_id: str,
        transaction_id: str,
        requested_remediation: str,
        sender: str = TIXParticipantRole.BUYER_AGENT.value,
        receiver: str = TIXParticipantRole.MERCHANT_AGENT.value,
        attempt_id: str = "att_1",
        previous_hash: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ) -> TIXMessage:
        """Constructs a REMEDIATION_REQUEST message from buyer to merchant."""
        ts = timestamp or datetime.now(timezone.utc)
        msg = TIXMessage(
            message_id=message_id,
            transaction_id=transaction_id,
            intent_id=intent_id,
            attempt_id=attempt_id,
            sender=sender,
            receiver=receiver,
            timestamp=ts,
            message_type=TIXMessageType.REMEDIATION_REQUEST,
            payload={"remediation": requested_remediation},
            previous_message_hash=previous_hash,
        )
        return msg.with_computed_hash()

    def build_outcome_message(
        self,
        message_id: str,
        intent_id: str,
        transaction_id: str,
        status: str,
        violations: Optional[List[str]] = None,
        sender: str = TIXParticipantRole.TARKARAKSHA_CORE.value,
        receiver: str = TIXParticipantRole.TARKARAKSHA_ROUTER.value,
        attempt_id: str = "att_1",
        evidence_refs: Optional[List[str]] = None,
        previous_hash: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ) -> TIXMessage:
        """Constructs an OUTCOME message carrying deterministic evaluation results."""
        ts = timestamp or datetime.now(timezone.utc)
        payload = {
            "status": status,
            "violations": violations or [],
            "authoritative": True if sender in {TIXParticipantRole.TARKARAKSHA_CORE.value, "tarkaraksha"} else False,
        }
        msg = TIXMessage(
            message_id=message_id,
            transaction_id=transaction_id,
            intent_id=intent_id,
            attempt_id=attempt_id,
            sender=sender,
            receiver=receiver,
            timestamp=ts,
            message_type=TIXMessageType.OUTCOME,
            payload=payload,
            evidence_refs=evidence_refs or [],
            previous_message_hash=previous_hash,
        )
        return msg.with_computed_hash()

    def evaluate_and_record_integrity(
        self,
        intent: IntentContract,
        evidence_list: List[Evidence],
        transaction_id: str,
        outcome_message_id: str,
        events: Optional[List[CanonicalEvent]] = None,
        attempt_id: str = "att_1",
        reference_time: Optional[datetime] = None,
    ) -> Tuple[TIXMessage, IntegrityResult]:
        """Bridges to the deterministic integrity engine and appends the outcome to the TIX ledger.

        Guarantees that:
        1. Deterministic TarkaRaksha evaluation is authoritative.
        2. TIX conveys the exact evaluation verdict without mutation.
        3. Zero payment authorization is granted.
        """
        ref_time = reference_time or intent.issued_at
        result = evaluate_integrity(
            contract=intent,
            evidence_list=evidence_list,
            events=events,
            reference_time=ref_time,
        )

        prev_hash = self.get_chain_hash(transaction_id)
        violations = [str(v) for v in result.violations]
        ev_refs = [e.evidence_id for e in evidence_list]

        if result.status == IntegrityStatus.DRIFT:
            out_msg = self.build_drift_notice_message(
                message_id=outcome_message_id,
                intent_id=intent.intent_id,
                transaction_id=transaction_id,
                violations=violations,
                attempt_id=attempt_id,
                previous_hash=prev_hash,
                timestamp=ref_time,
            )
        else:
            out_msg = self.build_outcome_message(
                message_id=outcome_message_id,
                intent_id=intent.intent_id,
                transaction_id=transaction_id,
                status=result.status.value,
                violations=violations,
                attempt_id=attempt_id,
                evidence_refs=ev_refs,
                previous_hash=prev_hash,
                timestamp=ref_time,
            )

        outcome, committed_msg = self.append_and_verify(
            message=out_msg,
            expected_intent_id=intent.intent_id,
            expected_attempt_id=attempt_id,
            reference_time=ref_time,
        )
        if not outcome.is_valid:
            raise RuntimeError(f"TIX failed to record outcome message: {outcome.explanation}")

        return committed_msg, result
