"""
Replay Engine Domain Models, Contracts, and Error Hierarchy for TarkaRaksha (T13).
Enforces the core invariants:
1. Replay is a verification and audit capability, not an execution engine.
2. Identical authorized intent + identical ordered evidence + same rules version + same reference time
   MUST yield an identical deterministic replay result.
3. Pure functions with zero live network calls, zero live AI dependencies, and zero financial side effects.
"""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.domain.models import (
    CanonicalEvent,
    Evidence,
    EvidenceBundle,
    IntegrityResult,
    IntegrityStatus,
    IntentContract,
    MRDP,
    TransactionState,
)
from backend.app.domain.states.models import StateTransitionRecord


# Current stable rule and replay engine protocol version
REPLAY_PROTOCOL_VERSION: str = "1.0.0"
RULES_VERSION_DEFAULT: str = "1.0.0"


class ReplayVerdict(str, Enum):
    """
    Comparison outcome between recorded historical transaction reality and deterministic replay (§15).
    """
    MATCH = "MATCH"                    # Historical result perfectly agrees with deterministic replay
    MISMATCH = "MISMATCH"              # Historical result differs from deterministic replay (divergence/tamper detected)
    INVALID_REPLAY = "INVALID_REPLAY"  # Input history itself violates replay invariants or cannot be safely ordered


class ReplayDiscrepancy(BaseModel):
    """
    Detailed audit record of an exact point of divergence between recorded history and replay.
    """
    field: str
    recorded_value: Any
    replayed_value: Any
    explanation: str

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )


class ReplaySnapshot(BaseModel):
    """
    Immutable historical audit snapshot provided as input to the Replay Engine (§5).
    Contains everything needed to deterministically reconstruct the decision history:
    - IntentContract baseline
    - Recorded CanonicalEvents
    - Recorded Evidence records
    - Recorded state transitions
    - Expected/recorded integrity evaluation result
    - Expected/recorded MRDP proof (if non-PASS)
    - Reference timestamp for deterministic temporal evaluation
    """
    replay_id: str
    transaction_id: str
    contract: IntentContract
    events: List[CanonicalEvent] = Field(default_factory=list)
    evidence: List[Evidence] = Field(default_factory=list)
    state_transitions: List[StateTransitionRecord] = Field(default_factory=list)
    recorded_integrity_result: Optional[IntegrityResult] = None
    recorded_final_state: Optional[TransactionState] = None
    recorded_mrdp: Optional[MRDP] = None
    reference_time: datetime
    rules_version: str = RULES_VERSION_DEFAULT
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )

    @field_validator("reference_time", mode="before")
    @classmethod
    def validate_reference_time_timezone(cls, v: Any) -> datetime:
        if isinstance(v, str):
            dt = datetime.fromisoformat(v)
        elif isinstance(v, datetime):
            dt = v
        else:
            raise TypeError(f"Timestamp must be datetime or ISO string, got {type(v).__name__}")
        if dt.tzinfo is None:
            raise ValueError("reference_time must be timezone-aware (e.g. UTC)")
        return dt

    @field_validator("replay_id", "transaction_id")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Field cannot be empty or whitespace")
        return v.strip()


class ReplayResult(BaseModel):
    """
    Comprehensive output produced by the Replay Engine (§15).
    Exposes:
    - Overall verdict: MATCH, MISMATCH, INVALID_REPLAY
    - Reconstructed final state machine state
    - Replayed integrity result (pure deterministic re-evaluation)
    - Replayed MRDP (if DRIFT or UNKNOWN)
    - Comparison diagnostics and discrepancies list
    - Ordered canonical events and evidence used
    - Tamper detection indicators
    """
    replay_id: str
    transaction_id: str
    verdict: ReplayVerdict
    replayed_state: TransactionState
    replayed_integrity_result: IntegrityResult
    replayed_mrdp: Optional[MRDP] = None
    discrepancies: List[ReplayDiscrepancy] = Field(default_factory=list)
    ordered_event_ids: List[str] = Field(default_factory=list)
    ordered_evidence_ids: List[str] = Field(default_factory=list)
    is_mrdp_valid: Optional[bool] = None
    rules_version_match: bool = True
    executed_at: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )

    @property
    def is_match(self) -> bool:
        return self.verdict == ReplayVerdict.MATCH

    @property
    def is_mismatch(self) -> bool:
        return self.verdict == ReplayVerdict.MISMATCH

    @property
    def is_invalid(self) -> bool:
        return self.verdict == ReplayVerdict.INVALID_REPLAY


# --- Replay Exception Hierarchy ---

class ReplayError(Exception):
    """Base exception for all replay engine operations."""
    pass


class InvalidReplayInputError(ReplayError):
    """Raised when replay snapshot input violates structural or ordering invariants."""
    pass


class ReplayAmbiguityError(ReplayError):
    """Raised when event history has irreconcilable temporal or sequence ambiguities."""
    pass
