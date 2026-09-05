"""
Domain enumeration types for TarkaRaksha.
Defines authoritative states, sources, decisions, and integrity statuses.
"""
from enum import Enum


class IntegrityStatus(str, Enum):
    """
    Core integrity verification outcome.
    UNKNOWN is a first-class legitimate state, completely distinct from PASS and DRIFT.
    """
    PASS = "PASS"
    DRIFT = "DRIFT"
    UNKNOWN = "UNKNOWN"


class DecisionAction(str, Enum):
    """
    System decision action determined by the control plane.
    Distinct from the raw IntegrityStatus observation.
    """
    CONTINUE = "CONTINUE"
    ABSTAIN = "ABSTAIN"
    RECOVER = "RECOVER"
    RESOLVE = "RESOLVE"
    REVALIDATE = "REVALIDATE"


class EvidenceSource(str, Enum):
    """
    Origin category of observed evidence.
    Used by the deterministic verifier to apply authoritative weighting.
    """
    INTENT = "INTENT"
    AGENT = "AGENT"
    MERCHANT = "MERCHANT"
    RAZORPAY = "RAZORPAY"
    REPLAY = "REPLAY"
    SYNTHETIC = "SYNTHETIC"


class TransactionState(str, Enum):
    """
    Canonical lifecycle state of a transaction in TarkaRaksha.
    """
    CREATED = "CREATED"
    EXECUTING = "EXECUTING"
    OBSERVING = "OBSERVING"
    VERIFYING = "VERIFYING"
    PASS = "PASS"
    DRIFT = "DRIFT"
    UNKNOWN = "UNKNOWN"
    RESOLVING = "RESOLVING"
    ABSTAIN = "ABSTAIN"
    RECOVERING = "RECOVERING"
    REVALIDATING = "REVALIDATING"


class ActionType(str, Enum):
    """
    Types of actions that may be proposed or executed.
    """
    CAPTURE = "CAPTURE"
    VOID = "VOID"
    REFUND = "REFUND"
    CANCEL = "CANCEL"
    NOTIFY = "NOTIFY"
    HOLD = "HOLD"
