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

__all__ = [
    "MAX_RECOVERY_ATTEMPTS",
    "InvalidRecoveryStateError",
    "NonRecoverableDriftError",
    "RecoverabilityStatus",
    "RecoveryClassification",
    "RecoveryError",
    "RecoveryExecutionResult",
    "RecoveryExhaustedError",
    "RecoveryIdempotencyError",
    "UnsafeActionRequestError",
]
