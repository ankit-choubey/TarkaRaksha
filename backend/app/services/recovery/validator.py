"""
Deterministic ActionRequest Safety Validator for TarkaRaksha (T11).
Enforces the core invariant:
Original authorized intent is strictly immutable.
Recovery may repair divergence but may NEVER expand original authority.
Financial actions require deterministic authorization.
"""
from datetime import datetime, timezone
from typing import Optional

from backend.app.domain.models import (
    ActionRequest,
    ActionType,
    IntentContract,
    Money,
    MRDP,
    TransactionState,
)
from .contracts import (
    MAX_RECOVERY_ATTEMPTS,
    InvalidRecoveryStateError,
    RecoveryExhaustedError,
    UnsafeActionRequestError,
)

# Explicit allowlist of permissible recovery action types (§8, §9)
# CAPTURE is strictly excluded from recovery
PERMISSIBLE_RECOVERY_ACTIONS = {
    ActionType.REFUND,
    ActionType.VOID,
    ActionType.CANCEL,
    ActionType.NOTIFY,
    ActionType.HOLD,
}

# Legal lifecycle states from which recovery may be initiated or executed (§14)
LEGAL_RECOVERY_STATES = {
    TransactionState.DRIFT,
    TransactionState.UNKNOWN,
    TransactionState.RESOLVING,
    TransactionState.RECOVERING,
}


def validate_action_request(
    action_request: ActionRequest,
    contract: IntentContract,
    mrdp: Optional[MRDP] = None,
    current_state: Optional[TransactionState] = None,
    attempt_count: int = 1,
) -> ActionRequest:
    """
    Deterministically validates an ActionRequest against contract bounds,
    state machine rules, and MRDP discrepancy facts.
    Returns validated copy with `is_validated=True`.
    Raises UnsafeActionRequestError, InvalidRecoveryStateError, or RecoveryExhaustedError on violation.
    """
    # 1. State Machine Boundary Check (§14)
    if current_state is not None and current_state not in LEGAL_RECOVERY_STATES:
        raise InvalidRecoveryStateError(
            f"Cannot initiate or execute recovery from lifecycle state '{current_state.value}'. "
            f"Recovery is strictly permitted only from {sorted(s.value for s in LEGAL_RECOVERY_STATES)}."
        )

    # 2. Recovery Attempts Limit Check (§15)
    if attempt_count >= MAX_RECOVERY_ATTEMPTS:
        raise RecoveryExhaustedError(
            f"Recovery attempts limit ({MAX_RECOVERY_ATTEMPTS}) reached for intent '{contract.intent_id}'. "
            "Action request rejected. Escalating to ABSTAIN."
        )

    # 3. Action Type Allowlist Check (§8, §9)
    if action_request.action_type == ActionType.CAPTURE:
        raise UnsafeActionRequestError(
            "ActionType.CAPTURE is strictly forbidden in the recovery control plane. "
            "Recovery can never initiate financial capture."
        )

    if action_request.action_type not in PERMISSIBLE_RECOVERY_ACTIONS:
        raise UnsafeActionRequestError(
            f"ActionType '{action_request.action_type.value}' is not a permissible recovery action. "
            f"Allowed actions: {sorted(a.value for a in PERMISSIBLE_RECOVERY_ACTIONS)}."
        )

    # 4. Intent ID Alignment Check
    if action_request.intent_id != contract.intent_id:
        raise UnsafeActionRequestError(
            f"ActionRequest intent_id '{action_request.intent_id}' does not match contract intent_id '{contract.intent_id}'"
        )

    # 5. Temporal Expiration Check (§16)
    # Recovery cannot execute compensatory actions if the intent authorization has expired
    req_time = action_request.requested_at
    if req_time.tzinfo is None:
        req_time = req_time.replace(tzinfo=timezone.utc)
    
    if req_time > contract.expires_at:
        raise UnsafeActionRequestError(
            f"Cannot execute recovery: request time {req_time.isoformat()} exceeds contract expiration {contract.expires_at.isoformat()}"
        )

    # 6. Financial Bounds Validation (§7, §8, §9)
    if action_request.amount is not None:
        # Currency alignment
        if action_request.amount.currency != contract.currency:
            raise UnsafeActionRequestError(
                f"Requested amount currency '{action_request.amount.currency}' does not match contract currency '{contract.currency}'"
            )

        # Amount must be strictly positive
        if action_request.amount.amount <= 0:
            raise UnsafeActionRequestError(
                f"Requested amount must be strictly greater than zero, got {action_request.amount.amount}"
            )

        # Cannot exceed original contract max_total ceiling
        if action_request.amount.amount > contract.max_total.amount:
            raise UnsafeActionRequestError(
                f"Requested recovery amount {action_request.amount} exceeds authorized contract max_total {contract.max_total}"
            )

        # For REFUND actions: cannot exceed detected MRDP discrepancy amount
        if action_request.action_type == ActionType.REFUND and mrdp is not None and mrdp.discrepancy_amount is not None:
            if action_request.amount.amount > mrdp.discrepancy_amount.amount:
                raise UnsafeActionRequestError(
                    f"Requested refund amount {action_request.amount} exceeds detected MRDP discrepancy {mrdp.discrepancy_amount}"
                )

    # 7. Idempotency Key Non-Empty Guard (§10)
    if not action_request.idempotency_key or not action_request.idempotency_key.strip():
        raise UnsafeActionRequestError("ActionRequest must include a non-empty idempotency_key")

    # Return validated immutable copy
    return ActionRequest(
        request_id=action_request.request_id,
        intent_id=action_request.intent_id,
        action_type=action_request.action_type,
        amount=action_request.amount,
        target_reference=action_request.target_reference,
        idempotency_key=action_request.idempotency_key.strip(),
        requested_at=action_request.requested_at,
        requested_by=action_request.requested_by,
        proposal_reference=action_request.proposal_reference,
        is_validated=True,
        validation_notes="Deterministic recovery validation PASSED",
    )
