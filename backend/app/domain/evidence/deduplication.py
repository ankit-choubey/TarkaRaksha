"""
Deterministic evidence and event deduplication for TarkaRaksha.
Removes idempotent duplicate deliveries while preserving deterministic ordering.
"""
from typing import List, Set
from backend.app.domain.models.evidence import CanonicalEvent, Evidence
from backend.app.domain.models.money import Money


def _make_evidence_identity_key(e: Evidence) -> str:
    """Generates a composite content identity key for semantic deduplication."""
    val_repr = f"{e.field_value.amount}_{e.field_value.currency}" if isinstance(e.field_value, Money) else str(e.field_value)
    return f"{e.evidence_id}|{e.intent_id}|{e.source.value}|{e.field_name}|{val_repr}|{e.observed_at.isoformat()}"


def deduplicate_evidence(records: List[Evidence]) -> List[Evidence]:
    """
    Deduplicates evidence records deterministically.
    Removes records that share the same evidence_id or semantic composite content key.
    Preserves original relative order.
    """
    seen_ids: Set[str] = set()
    seen_content_keys: Set[str] = set()
    unique_records: List[Evidence] = []

    for r in records:
        content_key = _make_evidence_identity_key(r)
        if r.evidence_id in seen_ids or content_key in seen_content_keys:
            continue
        seen_ids.add(r.evidence_id)
        seen_content_keys.add(content_key)
        unique_records.append(r)

    return unique_records


def deduplicate_events(events: List[CanonicalEvent]) -> List[CanonicalEvent]:
    """
    Deduplicates canonical events deterministically by event_id.
    Preserves original relative order.
    """
    seen_event_ids: Set[str] = set()
    unique_events: List[CanonicalEvent] = []

    for ev in events:
        if ev.event_id in seen_event_ids:
            continue
        seen_event_ids.add(ev.event_id)
        unique_events.append(ev)

    return unique_events
