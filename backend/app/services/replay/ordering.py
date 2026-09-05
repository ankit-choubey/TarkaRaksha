"""
Deterministic ordering logic for events and evidence in the TarkaRaksha Replay Engine (T13).

Requirements (§6):
1. Establish a deterministic event order using explicit canonical ordering rules:
   - event timestamp (chronological)
   - event sequence/order information where available
   - stable event_id as deterministic tie-breaker
2. Do not rely on Python dict/set iteration or database insertion order.
3. Do not silently rewrite timestamps.
4. Do not mutate original events/evidence.
5. If two events have genuinely conflicting ordering information (e.g. conflicting duplicate IDs with differing contents,
   or conflicting sequence numbers), replay should raise an explicit ReplayAmbiguityError.
"""
from typing import List, Tuple
from backend.app.domain.models import CanonicalEvent, Evidence
from backend.app.services.replay.contracts import ReplayAmbiguityError


def order_canonical_events(events: List[CanonicalEvent]) -> List[CanonicalEvent]:
    """
    Sorts canonical events deterministically and verifies ordering validity.
    
    Sorting key:
    1. timestamp (ISO format / chronological)
    2. sequence_number if present in payload/metadata (tie-breaker)
    3. event_id (stable deterministic string tie-breaker)
    
    Detects ambiguities:
    - Duplicate event_id with differing event details (tampering / conflicting history).
    """
    if not events:
        return []

    # Check for duplicate event IDs with divergent content
    seen_events: dict[str, CanonicalEvent] = {}
    for ev in events:
        if ev.event_id in seen_events:
            existing = seen_events[ev.event_id]
            # If two events share an event_id but differ in type, timestamp, or payload_summary, it's ambiguous/tampered
            if (
                existing.event_type != ev.event_type
                or existing.timestamp != ev.timestamp
                or existing.payload_summary != ev.payload_summary
            ):
                raise ReplayAmbiguityError(
                    f"Conflicting canonical events detected with identical event_id '{ev.event_id}' "
                    f"but divergent content ({existing.event_type} vs {ev.event_type})."
                )
        else:
            seen_events[ev.event_id] = ev

    def sort_key(ev: CanonicalEvent) -> Tuple[str, int, str]:
        # Sequence number extraction
        seq = ev.sequence_number or 0
        ts_str = ev.timestamp.isoformat()
        return (ts_str, seq, ev.event_id)

    # Return pure sorted list without mutating the original
    return sorted(events, key=sort_key)


def order_evidence_records(evidence: List[Evidence]) -> List[Evidence]:
    """
    Sorts evidence records deterministically and checks for integrity.
    
    Sorting key:
    1. authority rank (highest authority first: AUTHORITATIVE = 100, etc.)
    2. observed_at timestamp (chronological)
    3. evidence_id (stable deterministic string tie-breaker)
    
    Detects ambiguities:
    - Conflicting duplicate evidence IDs with differing values or authority.
    """
    if not evidence:
        return []

    seen_evidence: dict[str, Evidence] = {}
    for ev in evidence:
        if ev.evidence_id in seen_evidence:
            existing = seen_evidence[ev.evidence_id]
            if (
                existing.source != ev.source
                or existing.effective_authority != ev.effective_authority
                or existing.observed_at != ev.observed_at
                or existing.field_name != ev.field_name
                or existing.field_value != ev.field_value
            ):
                raise ReplayAmbiguityError(
                    f"Conflicting evidence records detected with identical evidence_id '{ev.evidence_id}' "
                    f"but divergent content ({existing.source} vs {ev.source})."
                )
        else:
            seen_evidence[ev.evidence_id] = ev

    def sort_key(ev: Evidence) -> Tuple[int, str, str]:
        # Higher authority_rank first -> negate for ascending sort
        rank_neg = -ev.authority_rank
        ts_str = ev.observed_at.isoformat()
        return (rank_neg, ts_str, ev.evidence_id)

    return sorted(evidence, key=sort_key)
