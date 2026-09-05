"""
Domain state machine package for TarkaRaksha.
Provides state models, transition rules, safety invariants, and state machine orchestrator.
"""
from .models import (
    StateMachineError,
    InvalidStateTransitionError,
    SafetyInvariantViolationError,
    StateTransitionRecord,
    StateTransitionRequest,
)
from .transitions import (
    PERMITTED_TRANSITIONS,
    can_transition,
    validate_transition,
)
from .invariants import (
    FINANCIAL_ACTIONS,
    assert_financial_action_permitted,
    assert_ai_proposal_safety,
    assert_intent_immutability,
)

__all__ = [
    "StateMachineError",
    "InvalidStateTransitionError",
    "SafetyInvariantViolationError",
    "StateTransitionRecord",
    "StateTransitionRequest",
    "PERMITTED_TRANSITIONS",
    "can_transition",
    "validate_transition",
    "FINANCIAL_ACTIONS",
    "assert_financial_action_permitted",
    "assert_ai_proposal_safety",
    "assert_intent_immutability",
]
