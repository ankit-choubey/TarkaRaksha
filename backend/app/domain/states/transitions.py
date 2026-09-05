"""
Transition graph and validation logic for TarkaRaksha transaction lifecycle.
Enforces the explicit transition graph defined in TarkaRaksha technical architecture.
"""
from typing import Dict, Optional, Set
from backend.app.domain.models.enums import TransactionState
from .models import InvalidStateTransitionError

# Authoritative transition graph mapping each source state to its set of permitted destination states
PERMITTED_TRANSITIONS: Dict[TransactionState, Set[TransactionState]] = {
    # 1. CREATED: initial state when intent is registered; can only begin execution
    TransactionState.CREATED: {
        TransactionState.EXECUTING,
    },
    # 2. EXECUTING: agent or checkout flow is active; moves to observing gateway/merchant events
    TransactionState.EXECUTING: {
        TransactionState.OBSERVING,
    },
    # 3. OBSERVING: collecting raw events; moves to verifying when bundle is ready
    TransactionState.OBSERVING: {
        TransactionState.VERIFYING,
    },
    # 4. VERIFYING: deterministic integrity engine evaluation; bifurcates into PASS, DRIFT, or UNKNOWN
    TransactionState.VERIFYING: {
        TransactionState.PASS,
        TransactionState.DRIFT,
        TransactionState.UNKNOWN,
    },
    # 5. PASS: verified safe outcome; terminal for this transaction execution cycle
    TransactionState.PASS: set(),
    # 6. DRIFT: invariant violation detected; can initiate recovery, resolve/escalate, or abstain
    TransactionState.DRIFT: {
        TransactionState.RECOVERING,
        TransactionState.RESOLVING,
        TransactionState.ABSTAIN,
    },
    # 7. UNKNOWN: ambiguous or missing evidence; requires resolution workflow or abstaining
    TransactionState.UNKNOWN: {
        TransactionState.RESOLVING,
        TransactionState.ABSTAIN,
    },
    # 8. RESOLVING: active investigation/evidence gathering for UNKNOWN/DRIFT; revalidates or abstains
    TransactionState.RESOLVING: {
        TransactionState.REVALIDATING,
        TransactionState.ABSTAIN,
    },
    # 9. RECOVERING: generating/validating compensatory action plan; moves to revalidating or abstains
    TransactionState.RECOVERING: {
        TransactionState.REVALIDATING,
        TransactionState.ABSTAIN,
    },
    # 10. REVALIDATING: re-running deterministic checks post-resolution/recovery; yields PASS, DRIFT, UNKNOWN, or re-enters VERIFYING
    TransactionState.REVALIDATING: {
        TransactionState.PASS,
        TransactionState.DRIFT,
        TransactionState.UNKNOWN,
        TransactionState.VERIFYING,
    },
    # 11. ABSTAIN: terminal safety state; control plane refuses further action to prevent loss
    TransactionState.ABSTAIN: set(),
}


def can_transition(from_state: TransactionState, to_state: TransactionState) -> bool:
    """
    Pure predicate to check whether a transition from `from_state` to `to_state`
    is structurally permitted by the TarkaRaksha lifecycle graph.
    """
    if not isinstance(from_state, TransactionState) or not isinstance(to_state, TransactionState):
        return False
    
    if from_state == to_state:
        return False

    allowed_targets = PERMITTED_TRANSITIONS.get(from_state, set())
    return to_state in allowed_targets


def validate_transition(
    from_state: TransactionState,
    to_state: TransactionState,
    context_reason: Optional[str] = None,
) -> None:
    """
    Validates that a transition from `from_state` to `to_state` is allowed.
    Raises `InvalidStateTransitionError` if the transition is forbidden.
    """
    if from_state == to_state:
        raise InvalidStateTransitionError(
            from_state=from_state,
            to_state=to_state,
            reason="Self-transitions are disallowed; state cannot transition to itself",
        )

    if not can_transition(from_state, to_state):
        detail = context_reason or f"Transition from {from_state.value} to {to_state.value} is not permitted"
        raise InvalidStateTransitionError(
            from_state=from_state,
            to_state=to_state,
            reason=detail,
        )
