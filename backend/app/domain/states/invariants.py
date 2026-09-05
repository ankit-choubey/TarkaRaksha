"""
Safety invariants for TarkaRaksha transaction lifecycle.
Enforces hard safety invariants:
- UNKNOWN => no financial action
- DRIFT => no unauthorized financial action
- ABSTAIN => cannot execute financial action
- Recovery => original constraints remain unchanged
- AI proposal => deterministic verification required before state mutation or financial execution
"""
from typing import Optional
from backend.app.domain.models.enums import TransactionState, ActionType
from backend.app.domain.models.intent import IntentContract
from backend.app.domain.models.money import Money
from .models import SafetyInvariantViolationError


# Actions categorized as consequential financial operations
FINANCIAL_ACTIONS = {
    ActionType.CAPTURE,
    ActionType.REFUND,
    ActionType.VOID,
}


def assert_financial_action_permitted(
    state: TransactionState,
    action: ActionType,
    amount: Optional[Money] = None,
    intent: Optional[IntentContract] = None,
) -> None:
    """
    Asserts that a financial action is permitted in the current state.
    Raises SafetyInvariantViolationError if the action violates lifecycle safety invariants.
    """
    # Invariant A: UNKNOWN => no financial action
    if state == TransactionState.UNKNOWN and action in FINANCIAL_ACTIONS:
        raise SafetyInvariantViolationError(
            state=state,
            action=action,
            reason="Financial actions are strictly forbidden while in UNKNOWN state. Must resolve first.",
        )

    # Invariant B: DRIFT => no unauthorized financial action
    if state == TransactionState.DRIFT and action in FINANCIAL_ACTIONS:
        raise SafetyInvariantViolationError(
            state=state,
            action=action,
            reason="Consequential financial actions (e.g., CAPTURE) are strictly forbidden in DRIFT state without successful revalidation.",
        )

    # Invariant E: ABSTAIN => cannot execute financial action
    if state == TransactionState.ABSTAIN and action in FINANCIAL_ACTIONS:
        raise SafetyInvariantViolationError(
            state=state,
            action=action,
            reason="Financial actions are permanently blocked in ABSTAIN state.",
        )

    # Intermediate non-terminal states cannot execute financial capture directly
    if state in (
        TransactionState.CREATED,
        TransactionState.EXECUTING,
        TransactionState.OBSERVING,
        TransactionState.VERIFYING,
        TransactionState.RESOLVING,
        TransactionState.RECOVERING,
        TransactionState.REVALIDATING,
    ) and action == ActionType.CAPTURE:
        raise SafetyInvariantViolationError(
            state=state,
            action=action,
            reason=f"Cannot execute financial CAPTURE directly in non-verified state {state.value}. Must pass verification first.",
        )

    # If amount is provided, assert it does not exceed original authorized intent
    if amount is not None and intent is not None and action == ActionType.CAPTURE:
        if amount.currency != intent.max_total.currency:
            raise SafetyInvariantViolationError(
                state=state,
                action=action,
                reason=f"Currency mismatch: action currency {amount.currency} != intent currency {intent.max_total.currency}",
            )
        if amount.amount > intent.max_total.amount:
            raise SafetyInvariantViolationError(
                state=state,
                action=action,
                reason=f"Action amount {amount.amount} exceeds authorized intent maximum {intent.max_total.amount}",
            )


def assert_ai_proposal_safety(
    triggered_by: str,
    is_verified: bool,
) -> None:
    """
    Invariant D: AI proposal => deterministic validation required.
    Rejects any transition or action triggered directly by AI or an agent
    without deterministic verification.
    """
    untrusted_triggers = {"AI", "AGENT", "AGENT_PROPOSAL", "LLM"}
    if triggered_by.upper() in untrusted_triggers and not is_verified:
        raise SafetyInvariantViolationError(
            state=TransactionState.RECOVERING,
            action=None,
            reason="AI and agent recommendations are advisory. State transition requires deterministic validation.",
        )


def assert_intent_immutability(
    original_intent: IntentContract,
    current_intent: IntentContract,
) -> None:
    """
    Invariant C: Recovery => original constraints remain unchanged.
    Asserts that original intent constraints (ID, amounts, items, currency)
    have not been mutated across recovery or state transitions.
    """
    if original_intent.intent_id != current_intent.intent_id:
        raise SafetyInvariantViolationError(
            state=TransactionState.RECOVERING,
            action=None,
            reason="Intent ID mismatch; intent immutability violated.",
        )
    if original_intent.max_total != current_intent.max_total:
        raise SafetyInvariantViolationError(
            state=TransactionState.RECOVERING,
            action=None,
            reason="Authorized amount mismatch; intent immutability violated.",
        )
    if len(original_intent.items) != len(current_intent.items):
        raise SafetyInvariantViolationError(
            state=TransactionState.RECOVERING,
            action=None,
            reason="Item specification count mismatch; intent immutability violated.",
        )
    for orig_item, curr_item in zip(original_intent.items, current_intent.items):
        if orig_item.sku != curr_item.sku or orig_item.quantity != curr_item.quantity:
            raise SafetyInvariantViolationError(
                state=TransactionState.RECOVERING,
                action=None,
                reason=f"Item spec modified for SKU {orig_item.sku}; intent immutability violated.",
            )
