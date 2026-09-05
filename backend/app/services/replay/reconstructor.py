"""
State machine replay and historical transition reconstruction for TarkaRaksha (T13).

Requirements (§8):
1. Reuse the existing T05 TransactionStateMachine. Do not implement a second state machine.
2. Replay reconstructs legal state progression from recorded events/results.
3. Verify:
   - legal transitions
   - illegal transitions
   - skipped states
   - terminal-state violations
   - recovery lifecycle
   - UNKNOWN resolution lifecycle
   - revalidation lifecycle
4. Replay must identify illegal transitions or skips (e.g. UNKNOWN -> PASS directly without RESOLVING/OBSERVING/VERIFYING).
"""
from typing import List, Optional, Tuple
from datetime import datetime

from backend.app.domain.models import IntentContract, TransactionState
from backend.app.domain.states.machine import TransactionStateMachine
from backend.app.domain.states.models import (
    InvalidStateTransitionError,
    SafetyInvariantViolationError,
    StateTransitionRecord,
)
from backend.app.services.replay.contracts import (
    ReplayDiscrepancy,
    ReplayVerdict,
)


class StateReplayOutcome:
    """
    Result of replaying state transitions through TransactionStateMachine.
    """
    def __init__(
        self,
        final_state: TransactionState,
        reconstructed_history: List[StateTransitionRecord],
        is_valid: bool,
        has_illegal_transition: bool,
        discrepancies: List[ReplayDiscrepancy],
    ):
        self.final_state = final_state
        self.reconstructed_history = reconstructed_history
        self.is_valid = is_valid
        self.has_illegal_transition = has_illegal_transition
        self.discrepancies = discrepancies


def replay_state_transitions(
    transaction_id: str,
    contract: IntentContract,
    recorded_transitions: List[StateTransitionRecord],
    expected_final_state: Optional[TransactionState] = None,
) -> StateReplayOutcome:
    """
    Replays recorded StateTransitionRecords sequentially using the authoritative T05 TransactionStateMachine.
    
    If no transitions are recorded, initializes machine in CREATED state.
    For each transition in recorded_transitions:
    - Checks whether transition from current machine state to record.to_state is valid according to T05 rules.
    - If valid, executes transition_to on the machine.
    - If invalid or illegal (e.g. UNKNOWN -> PASS directly, or skipped transitions),
      captures the exact discrepancy and marks has_illegal_transition=True.
    """
    discrepancies: List[ReplayDiscrepancy] = []

    # Initialize machine in CREATED state
    initial_time = contract.issued_at
    if recorded_transitions:
        # Use initial transition timestamp if available and timezone-aware
        initial_time = recorded_transitions[0].timestamp

    machine = TransactionStateMachine(
        transaction_id=transaction_id,
        intent=contract,
        initial_state=TransactionState.CREATED,
        created_at=initial_time,
    )

    if not recorded_transitions:
        # If no transitions recorded, compare against expected_final_state as an outcome discrepancy (MISMATCH, not INVALID_REPLAY)
        if expected_final_state and expected_final_state != TransactionState.CREATED:
            discrepancies.append(
                ReplayDiscrepancy(
                    field="final_state",
                    recorded_value=expected_final_state.value,
                    replayed_value=TransactionState.CREATED.value,
                    explanation="No state transitions recorded; machine remained in CREATED state.",
                )
            )
        return StateReplayOutcome(
            final_state=TransactionState.CREATED,
            reconstructed_history=[],
            is_valid=True,
            has_illegal_transition=False,
            discrepancies=discrepancies,
        )

    # Replay each recorded transition sequentially
    for idx, rec in enumerate(recorded_transitions):
        from_state = rec.from_state
        to_state = rec.to_state

        # Check for state discontinuity (e.g., recorded record claims from_state != machine.current_state)
        if machine.current_state != from_state:
            discrepancies.append(
                ReplayDiscrepancy(
                    field=f"state_transition[{idx}].from_state",
                    recorded_value=from_state.value,
                    replayed_value=machine.current_state.value,
                    explanation=(
                        f"State continuity breach at transition {idx}: recorded transition started from "
                        f"{from_state.value}, but machine was in {machine.current_state.value}."
                    ),
                )
            )
            return StateReplayOutcome(
                final_state=machine.current_state,
                reconstructed_history=machine.history,
                is_valid=False,
                has_illegal_transition=True,
                discrepancies=discrepancies,
            )

        # Attempt transition through the authoritative T05 state machine
        try:
            machine.transition_to(
                to_state=to_state,
                reason=rec.reason,
                timestamp=rec.timestamp,
                triggered_by=rec.triggered_by,
                is_verified=rec.is_verified,
                context=rec.context,
                integrity_status=rec.integrity_status,
            )
        except (InvalidStateTransitionError, SafetyInvariantViolationError, ValueError) as err:
            discrepancies.append(
                ReplayDiscrepancy(
                    field=f"state_transition[{idx}]",
                    recorded_value=f"{from_state.value} -> {to_state.value}",
                    replayed_value=f"FORBIDDEN: {type(err).__name__}",
                    explanation=f"Illegal transition recorded in history: {str(err)}",
                )
            )
            return StateReplayOutcome(
                final_state=machine.current_state,
                reconstructed_history=machine.history,
                is_valid=False,
                has_illegal_transition=True,
                discrepancies=discrepancies,
            )

    # Check if final replayed state matches expected recorded final state
    if expected_final_state and machine.current_state != expected_final_state:
        discrepancies.append(
            ReplayDiscrepancy(
                field="final_state",
                recorded_value=expected_final_state.value,
                replayed_value=machine.current_state.value,
                explanation=(
                    f"Final state divergence: recorded final state was {expected_final_state.value}, "
                    f"but replaying transitions yielded {machine.current_state.value}."
                ),
            )
        )

    return StateReplayOutcome(
        final_state=machine.current_state,
        reconstructed_history=machine.history,
        is_valid=len(discrepancies) == 0,
        has_illegal_transition=False,
        discrepancies=discrepancies,
    )
