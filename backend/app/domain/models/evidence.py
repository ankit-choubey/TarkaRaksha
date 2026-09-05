"""
Event and Evidence models for TarkaRaksha.
Provides provider-neutral representations of observations and facts with explicit source authority.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, ConfigDict, Field, field_validator
from .enums import EvidenceAuthority, EvidenceSource
from .money import Money


# Canonical mapping from source category to default authoritative weight tier
SOURCE_DEFAULT_AUTHORITY_MAP = {
    EvidenceSource.RAZORPAY: EvidenceAuthority.AUTHORITATIVE,
    EvidenceSource.INTENT: EvidenceAuthority.PROTOCOL_TRUSTED,
    EvidenceSource.USER_INTENT: EvidenceAuthority.PROTOCOL_TRUSTED,
    EvidenceSource.MERCHANT: EvidenceAuthority.MERCHANT_ATTESTED,
    EvidenceSource.REPLAY: EvidenceAuthority.REPLAY_OBSERVED,
    EvidenceSource.SYSTEM: EvidenceAuthority.SYSTEM_DERIVED,
    EvidenceSource.SYNTHETIC: EvidenceAuthority.SYSTEM_DERIVED,
    EvidenceSource.AGENT: EvidenceAuthority.ADVISORY,
}

# Numeric authority ranking for deterministic conflict resolution
AUTHORITY_RANK_MAP = {
    EvidenceAuthority.AUTHORITATIVE: 100,
    EvidenceAuthority.PROTOCOL_TRUSTED: 90,
    EvidenceAuthority.MERCHANT_ATTESTED: 70,
    EvidenceAuthority.REPLAY_OBSERVED: 60,
    EvidenceAuthority.SYSTEM_DERIVED: 50,
    EvidenceAuthority.ADVISORY: 20,
}


class CanonicalEvent(BaseModel):
    """
    Provider-neutral representation of a transaction or execution lifecycle event.
    Shields domain models and deterministic engines from gateway-specific payload shapes.
    """
    event_id: str
    transaction_id: str
    intent_id: str
    event_type: str
    timestamp: datetime
    occurred_at: Optional[datetime] = None
    sequence_number: int = 1
    amount: Optional[Money] = None
    source: EvidenceSource = EvidenceSource.MERCHANT
    authority: Optional[EvidenceAuthority] = None
    payload_summary: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )

    @field_validator("timestamp", "occurred_at", mode="before")
    @classmethod
    def validate_timezone(cls, v: Any) -> Optional[datetime]:
        if v is None:
            return None
        if isinstance(v, str):
            dt = datetime.fromisoformat(v)
        elif isinstance(v, datetime):
            dt = v
        else:
            raise TypeError(f"Timestamp must be datetime or ISO string, got {type(v).__name__}")
        
        if dt.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware (e.g., UTC)")
        return dt

    @field_validator("sequence_number")
    @classmethod
    def validate_sequence(cls, v: int) -> int:
        if isinstance(v, bool) or v < 1:
            raise ValueError("sequence_number must be a positive integer >= 1")
        return v


class Evidence(BaseModel):
    """
    Normalized factual evidence item extracted from observed events or authoritative gateways.
    Explicitly distinguishes origin source (source) from authority weighting (authority).
    """
    evidence_id: str
    intent_id: str
    transaction_id: Optional[str] = None
    source: EvidenceSource
    authority: Optional[EvidenceAuthority] = None
    field_name: str
    field_value: Any
    observed_at: datetime
    ingested_at: Optional[datetime] = None
    is_authoritative: bool = False
    raw_reference: Optional[str] = None
    provenance: Dict[str, Any] = Field(default_factory=dict)
    confidence_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )

    @field_validator("observed_at", "ingested_at", mode="before")
    @classmethod
    def validate_timezone(cls, v: Any) -> Optional[datetime]:
        if v is None:
            return None
        if isinstance(v, str):
            dt = datetime.fromisoformat(v)
        elif isinstance(v, datetime):
            dt = v
        else:
            raise TypeError(f"Timestamp must be datetime or ISO string, got {type(v).__name__}")
        
        if dt.tzinfo is None:
            raise ValueError("Timestamp must be timezone-aware (e.g., UTC)")
        return dt

    @property
    def effective_authority(self) -> EvidenceAuthority:
        """Returns the explicit authority or derives the default authority from source."""
        if self.authority is not None:
            return self.authority
        return SOURCE_DEFAULT_AUTHORITY_MAP.get(self.source, EvidenceAuthority.ADVISORY)

    @property
    def authority_rank(self) -> int:
        """
        Numeric authority ranking for deterministic conflict resolution.
        Higher number = higher authority.
        """
        # If authority is explicitly provided, use its rank
        if self.authority is not None:
            return AUTHORITY_RANK_MAP.get(self.authority, 0)
        
        # Legacy/fallback source-based rank
        legacy_source_ranks = {
            EvidenceSource.RAZORPAY: 100,
            EvidenceSource.INTENT: 90,
            EvidenceSource.USER_INTENT: 90,
            EvidenceSource.MERCHANT: 70,
            EvidenceSource.REPLAY: 60,
            EvidenceSource.SYSTEM: 50,
            EvidenceSource.AGENT: 40,
            EvidenceSource.SYNTHETIC: 20,
        }
        return legacy_source_ranks.get(self.source, 0)


class EvidenceBundle(BaseModel):
    """
    Immutable container representing all factual evidence associated with a transaction.
    Provides deterministic querying, authority-ranked resolution, and conflict detection.
    """
    bundle_id: str
    intent_id: str
    transaction_id: Optional[str] = None
    created_at: datetime
    records: List[Evidence] = Field(default_factory=list)
    events: List[CanonicalEvent] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )

    @field_validator("created_at", mode="before")
    @classmethod
    def validate_timezone(cls, v: Any) -> datetime:
        if isinstance(v, str):
            dt = datetime.fromisoformat(v)
        elif isinstance(v, datetime):
            dt = v
        else:
            raise TypeError(f"Timestamp must be datetime or ISO string, got {type(v).__name__}")
        
        if dt.tzinfo is None:
            raise ValueError("created_at must be timezone-aware (e.g., UTC)")
        return dt

    def get_records_for_field(self, field_name: str) -> List[Evidence]:
        """Returns all evidence items recording the specified field_name."""
        return [r for r in self.records if r.field_name == field_name]

    def has_field(self, field_name: str) -> bool:
        """Checks if at least one evidence item exists for field_name."""
        return any(r.field_name == field_name for r in self.records)

    def get_authoritative_evidence(self, field_name: str) -> Optional[Evidence]:
        """
        Returns the winning authoritative Evidence item for field_name.
        If there is an unresolved conflict at the highest authority rank,
        returns None to preserve ambiguity (signaling UNKNOWN to downstream engines).
        """
        matching = self.get_records_for_field(field_name)
        if not matching:
            return None

        # Sort descending by authority_rank, then observed_at, then evidence_id
        sorted_records = sorted(
            matching,
            key=lambda e: (e.authority_rank, e.observed_at.isoformat(), e.evidence_id),
            reverse=True,
        )
        highest_rank = sorted_records[0].authority_rank
        top_tier = [r for r in sorted_records if r.authority_rank == highest_rank]

        first_val = top_tier[0].field_value
        for r in top_tier[1:]:
            if r.field_value != first_val:
                return None  # Unresolvable conflict at top authority rank
        
        return top_tier[0]

    def detect_conflicts(self) -> Dict[str, List[Evidence]]:
        """
        Identifies fields where contradictory values exist at the highest authority tier.
        Returns a mapping of field_name to the conflicting top-tier records.
        """
        conflicts: Dict[str, List[Evidence]] = {}
        fields = {r.field_name for r in self.records}
        for field in sorted(fields):
            matching = self.get_records_for_field(field)
            if len(matching) < 2:
                continue
            highest_rank = max(r.authority_rank for r in matching)
            top_tier = [r for r in matching if r.authority_rank == highest_rank]
            first_val = top_tier[0].field_value
            if any(r.field_value != first_val for r in top_tier[1:]):
                conflicts[field] = top_tier
        return conflicts

    def is_complete(self, required_fields: List[str]) -> bool:
        """Asserts whether all required fields are present with at least one record."""
        return all(self.has_field(f) for f in required_fields)

    @property
    def evidence_ids(self) -> List[str]:
        return [r.evidence_id for r in self.records]

    @property
    def unique_sources(self) -> Set[EvidenceSource]:
        return {r.source for r in self.records}
