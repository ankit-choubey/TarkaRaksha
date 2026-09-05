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
    Distinguishes the source of evidence from its authoritative weighting.
    """
    INTENT = "INTENT"
    USER_INTENT = "USER_INTENT"
    AGENT = "AGENT"
    MERCHANT = "MERCHANT"
    RAZORPAY = "RAZORPAY"
    SYSTEM = "SYSTEM"
    REPLAY = "REPLAY"
    SYNTHETIC = "SYNTHETIC"


class EvidenceAuthority(str, Enum):
    """
    Authoritative weighting tiers for deterministic conflict resolution.
    Follows IDEA §31 and Execution §7.24 hierarchy:
    AUTHORITATIVE (100) > PROTOCOL_TRUSTED (90) > MERCHANT_ATTESTED (70) > REPLAY_OBSERVED (60) > SYSTEM_DERIVED (50) > ADVISORY (20)
    """
    AUTHORITATIVE = "AUTHORITATIVE"          # Provider gateway truth (e.g. Razorpay payment capture)
    PROTOCOL_TRUSTED = "PROTOCOL_TRUSTED"    # Authenticated user intent contract
    MERCHANT_ATTESTED = "MERCHANT_ATTESTED"  # Merchant order/checkout confirmation
    REPLAY_OBSERVED = "REPLAY_OBSERVED"      # Historical replayed audit log
    SYSTEM_DERIVED = "SYSTEM_DERIVED"        # Control plane calculation / synthetic benchmark
    ADVISORY = "ADVISORY"                    # Untrusted AI/agent proposal or hypothesis


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
