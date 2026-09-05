"""
Deterministic Reproducibility Record for TarkaRaksha Governance and Replay (I3.2).

Captures an immutable, cryptographically verifiable snapshot of replay inputs:
- intent
- events
- evidence
- rules_version
- policy_version
- reference_time
- input_snapshot_hash
- recorded_result

Central Invariant:
same inputs + same rules + same policy = same decision
"""
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.domain.models.enums import (
    EvidenceAuthority,
    EvidenceSource,
    IntegrityStatus,
    TransactionState,
)
from backend.app.domain.models.evidence import CanonicalEvent, Evidence
from backend.app.domain.models.integrity import IntegrityResult
from backend.app.domain.models.intent import IntentContract
from backend.app.domain.models.money import Money
from backend.app.domain.states.models import StateTransitionRecord
from backend.app.domain.governance.contracts import (
    DEFAULT_POLICY_VERSION,
    DEFAULT_RULES_VERSION,
)


def canonical_repr_for_hashing(val: Any) -> Any:
    """Recursively converts structures to canonical, deterministic representations for hashing."""
    if isinstance(val, Money):
        return {"amount": val.amount, "currency": val.currency}
    if isinstance(val, datetime):
        return val.astimezone(timezone.utc).isoformat()
    if isinstance(val, Enum):
        return val.value
    if isinstance(val, (list, tuple)):
        return [canonical_repr_for_hashing(item) for item in val]
    if isinstance(val, set):
        return sorted([canonical_repr_for_hashing(item) for item in val])
    if isinstance(val, dict):
        return {k: canonical_repr_for_hashing(v) for k, v in sorted(val.items())}
    if hasattr(val, "model_dump"):
        return canonical_repr_for_hashing(val.model_dump())
    return val


def compute_deterministic_hash(data: Any) -> str:
    """Produces a hex-encoded SHA-256 digest over canonical JSON."""
    canonical_data = canonical_repr_for_hashing(data)
    json_bytes = json.dumps(canonical_data, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(json_bytes).hexdigest()


class ReproducibilityRecord(BaseModel):
    """
    Immutable audit record linking exact input snapshots, governance versions,
    explicit reference time, and recorded decision result.
    """
    record_id: str
    transaction_id: str
    intent: IntentContract
    events: List[CanonicalEvent] = Field(default_factory=list)
    evidence: List[Evidence] = Field(default_factory=list)
    state_transitions: List[StateTransitionRecord] = Field(default_factory=list)
    rules_version: str = Field(default=DEFAULT_RULES_VERSION)
    policy_version: str = Field(default=DEFAULT_POLICY_VERSION)
    reference_time: datetime
    input_snapshot_hash: str
    recorded_result: IntegrityResult
    recorded_final_state: Optional[TransactionState] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )

    @field_validator("reference_time", "created_at", mode="before")
    @classmethod
    def validate_timezone(cls, v: Any) -> datetime:
        if isinstance(v, str):
            dt = datetime.fromisoformat(v)
        elif isinstance(v, datetime):
            dt = v
        else:
            raise TypeError(f"Timestamp must be datetime or ISO string, got {type(v).__name__}")
        if dt.tzinfo is None:
            raise ValueError("Timestamp must be timezone-aware (e.g. UTC)")
        return dt

    @classmethod
    def create(
        cls,
        record_id: str,
        transaction_id: str,
        intent: IntentContract,
        events: List[CanonicalEvent],
        evidence: List[Evidence],
        reference_time: datetime,
        recorded_result: IntegrityResult,
        rules_version: str = DEFAULT_RULES_VERSION,
        policy_version: str = DEFAULT_POLICY_VERSION,
        state_transitions: Optional[List[StateTransitionRecord]] = None,
        recorded_final_state: Optional[TransactionState] = None,
        created_at: Optional[datetime] = None,
    ) -> "ReproducibilityRecord":
        """
        Factory to compute the deterministic input_snapshot_hash over:
        - intent
        - events (ordered by canonical event_id)
        - evidence (ordered by canonical evidence_id)
        - rules_version
        - policy_version
        - reference_time
        """
        sorted_events = sorted(events, key=lambda e: (e.timestamp, e.event_id))
        sorted_evidence = sorted(evidence, key=lambda ev: (ev.observed_at, ev.evidence_id))
        transitions = state_transitions or []

        snapshot_payload = {
            "intent": intent.model_dump(),
            "events": [e.model_dump() for e in sorted_events],
            "evidence": [ev.model_dump() for ev in sorted_evidence],
            "rules_version": rules_version.strip(),
            "policy_version": policy_version.strip(),
            "reference_time": reference_time.astimezone(timezone.utc).isoformat(),
        }
        input_hash = compute_deterministic_hash(snapshot_payload)

        return cls(
            record_id=record_id.strip(),
            transaction_id=transaction_id.strip(),
            intent=intent,
            events=sorted_events,
            evidence=sorted_evidence,
            state_transitions=transitions,
            rules_version=rules_version.strip(),
            policy_version=policy_version.strip(),
            reference_time=reference_time,
            input_snapshot_hash=input_hash,
            recorded_result=recorded_result,
            recorded_final_state=recorded_final_state,
            created_at=created_at or datetime.now(timezone.utc),
        )

    def verify_input_hash(self) -> bool:
        """Verifies if the current record contents match its computed input_snapshot_hash."""
        sorted_events = sorted(self.events, key=lambda e: (e.timestamp, e.event_id))
        sorted_evidence = sorted(self.evidence, key=lambda ev: (ev.observed_at, ev.evidence_id))
        snapshot_payload = {
            "intent": self.intent.model_dump(),
            "events": [e.model_dump() for e in sorted_events],
            "evidence": [ev.model_dump() for ev in sorted_evidence],
            "rules_version": self.rules_version,
            "policy_version": self.policy_version,
            "reference_time": self.reference_time.astimezone(timezone.utc).isoformat(),
        }
        expected_hash = compute_deterministic_hash(snapshot_payload)
        return self.input_snapshot_hash == expected_hash
