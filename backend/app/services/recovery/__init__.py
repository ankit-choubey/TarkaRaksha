"""
Recovery Control Plane Package for TarkaRaksha (T11).
Implements the closed loop:
Detect (T04) -> Prove (T07) -> Repair (T11) -> Revalidate (T04).
"""
from .contracts import (
    MAX_RECOVERY_ATTEMPTS,
    InvalidRecoveryStateError,
    NonRecoverableDriftError,
    RecoverabilityStatus,
    RecoveryClassification,
    RecoveryError,
    RecoveryExecutionResult,
    RecoveryExhaustedError,
    RecoveryIdempotencyError,
    UnsafeActionRequestError,
)
from .executor import RecoveryExecutor
from .policy import classify_recovery
from .validator import PERMISSIBLE_RECOVERY_ACTIONS, validate_action_request

__all__ = [
    "MAX_RECOVERY_ATTEMPTS",
    "PERMISSIBLE_RECOVERY_ACTIONS",
    "InvalidRecoveryStateError",
    "NonRecoverableDriftError",
    "RecoverabilityStatus",
    "RecoveryClassification",
    "RecoveryError",
    "RecoveryExecutionResult",
    "RecoveryExecutor",
    "RecoveryExhaustedError",
    "RecoveryIdempotencyError",
    "UnsafeActionRequestError",
    "classify_recovery",
    "validate_action_request",
]
