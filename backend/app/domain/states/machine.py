"""
Transaction state machine orchestrator for TarkaRaksha.
Maintains state progression, history audit log, and enforces safety boundaries
and deterministic consumption of T04 IntegrityResults.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid

from backend.app.domain.models.enums import TransactionState, ActionType, IntegrityStatus
from backend.app.domain.models.intent import IntentContract
from backend.app.domain.models.integrity import IntegrityResult
from backend.app.domain.models.money import Money

from .models import (
    StateTransitionRecord,
    InvalidStateTransitionError,
    SafetyInvariantViolationError,
)
from .transitions import can_transition, validate_transition
from .invariants import (
    assert_financial_action_permitted,
    assert_ai_proposal_safety,
    assert_intent_immutability,
)


class TransactionStateMachine:
    """
    Deterministic transaction state machine for TarkaRaksha.
    Tracks state progression, preserves immutable transition history,
    and enforces structural and financial safety invariants.
    """

    def __init__(
        self,
        transaction_id: str,
        intent: IntentContract,
        initial_state: TransactionState = TransactionState.CREATED,
        created_at: Optional[datetime] = None,
    ):
        self.transaction_id = transaction_id
        self.intent = intent
        self.current_state = initial_state
        self.history: List[StateTransitionRecord] = []
        
        # Reference timestamps
        ts = created_at or intent.created_at
        if ts.tzinfo is None:
            raise ValueError("created_at timestamp must be timezone-aware (e.g. UTC)")
        self.created_at = ts
        self.updated_at = ts

    def can_transition_to(self, to_state: TransactionState) -> bool:
        """
        Predicate to check if transition from current state to `to_state` is valid.
        """
        return can_transition(self.current_state, to_state)

    def transition_to(
        self,
        to_state: TransactionState,
        reason: str,
        timestamp: datetime,
        triggered_by: str = "SYSTEM",
        is_verified: bool = True,
        context: Optional[Dict[str, Any]] = None,
        integrity_status: Optional[IntegrityStatus] = None,
    ) -> StateTransitionRecord:
        """
        Executes a validated state transition.
        Atomically updates current state and appends to transition history.
        Raises InvalidStateTransitionError or SafetyInvariantViolationError if forbidden.
        """
        if timestamp.tzinfo is None:
            raise ValueError("Timestamp must be timezone-aware (e.g. UTC)")
        
        if timestamp < self.updated_at:
            raise ValueError(
                f"Transition timestamp {timestamp.isoformat()} cannot precede current updated_at {self.updated_at.isoformat()}"
            )

        if not reason or not reason.strip():
            raise InvalidStateTransitionError(
                from_state=self.current_state,
                to_state=to_state,
                reason="Transition reason cannot be empty",
            )

        # Invariant D: AI proposal => deterministic validation required
        assert_ai_proposal_safety(triggered_by=triggered_by, is_verified=is_verified)

        # Validate lifecycle progression
        validate_transition(
            from_state=self.current_state,
            to_state=to_state,
            context_reason=reason,
        )

        # Build immutable transition record
        record = StateTransitionRecord(
            transition_id=f"tr_{uuid.uuid4().hex[:12]}",
            from_state=self.current_state,
            to_state=to_state,
            timestamp=timestamp,
            reason=reason.strip(),
            triggered_by=triggered_by,
            is_verified=is_verified,
            context=context or {},
            integrity_status=integrity_status,
        )

        # Atomic mutation of state machine
        self.current_state = to_state
        self.updated_at = timestamp
        self.history.append(record)
        return record

    def apply_integrity_result(
        self,
        integrity_result: IntegrityResult,
        timestamp: datetime,
        reason: Optional[str] = None,
    ) -> StateTransitionRecord:
        """
        Consumes a deterministic T04 IntegrityResult.
        Only valid from VERIFYING or REVALIDATING states.
        Transitions state to PASS, DRIFT, or UNKNOWN matching the result status.
        """
        if self.current_state not in (TransactionState.VERIFYING, TransactionState.REVALIDATING):
            raise InvalidStateTransitionError(
                from_state=self.current_state,
                to_state=TransactionState(integrity_result.status.value),
                reason=f"Cannot apply integrity result from state {self.current_state.value}. Must be in VERIFYING or REVALIDATING.",
            )

        target_state = TransactionState(integrity_result.status.value)
        effective_reason = reason or f"Deterministic integrity evaluation returned {integrity_result.status.value}"

        return self.transition_to(
            to_state=target_state,
            reason=effective_reason,
            timestamp=timestamp,
            triggered_by="DETERMINISTIC_ENGINE",
            is_verified=True,
            context={
                "drift_domains": [d.value for d in integrity_result.drift_domains],
                "primary_reason": integrity_result.primary_reason,
                "evidence_ids": integrity_result.evidence_ids,
            },
            integrity_status=integrity_result.status,
        )

    def request_action(
        self,
        action: ActionType,
        amount: Optional[Money] = None,
    ) -> None:
        """
        Validates whether a financial or administrative action is permitted in current state.
        Enforces Invariants A, B, and E.
        """
        assert_financial_action_permitted(
            state=self.current_state,
            action=action,
            amount=amount,
            intent=self.intent,
        )

    def verify_intent_immutability(self, original_intent: IntentContract) -> None:
        """
        Invariant C: Asserts that original intent constraints remain identical.
        """
        assert_intent_immutability(original_intent=original_intent, current_intent=self.intent)
