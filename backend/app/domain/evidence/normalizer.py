"""
Provider-neutral evidence normalization layer for TarkaRaksha.
Converts heterogeneous observation sources into canonical, immutable Evidence records
and assemblies them into an EvidenceBundle.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
import uuid

from backend.app.domain.models.enums import EvidenceAuthority, EvidenceSource
from backend.app.domain.models.evidence import (
    CanonicalEvent,
    Evidence,
    EvidenceBundle,
    SOURCE_DEFAULT_AUTHORITY_MAP,
)
from backend.app.domain.models.money import Money


# Known monetary field names for automatic canonical Money normalization
MONETARY_FIELDS = {
    "total_amount",
    "amount",
    "captured_amount",
    "refunded_amount",
    "authorized_amount",
    "fee",
    "tax",
}


def normalize_source(source_input: Union[str, EvidenceSource]) -> EvidenceSource:
    """
    Normalizes string or enum into a canonical EvidenceSource.
    Rejects unknown sources.
    """
    if isinstance(source_input, EvidenceSource):
        return source_input
    if isinstance(source_input, str):
        cleaned = source_input.strip().upper()
        try:
            return EvidenceSource(cleaned)
        except ValueError:
            raise ValueError(f"Unknown evidence source '{source_input}'")
    raise TypeError(f"Source must be EvidenceSource or str, got {type(source_input).__name__}")


def normalize_authority(
    authority_input: Optional[Union[str, EvidenceAuthority]],
    source: EvidenceSource,
) -> EvidenceAuthority:
    """
    Normalizes string or enum into a canonical EvidenceAuthority tier.
    If None, falls back to canonical default for the source category.
    """
    if authority_input is None:
        return SOURCE_DEFAULT_AUTHORITY_MAP.get(source, EvidenceAuthority.ADVISORY)
    if isinstance(authority_input, EvidenceAuthority):
        return authority_input
    if isinstance(authority_input, str):
        cleaned = authority_input.strip().upper()
        try:
            return EvidenceAuthority(cleaned)
        except ValueError:
            raise ValueError(f"Unknown evidence authority tier '{authority_input}'")
    raise TypeError(f"Authority must be EvidenceAuthority or str, got {type(authority_input).__name__}")


def normalize_monetary_value(val: Any, default_currency: str = "INR") -> Any:
    """
    Converts raw financial inputs into immutable Money value objects.
    Rejects floats, booleans, and malformed structures.
    """
    if isinstance(val, Money):
        return val
    if isinstance(val, dict):
        amt = val.get("amount")
        curr = val.get("currency", default_currency)
        if amt is None:
            raise ValueError("Monetary dictionary must include 'amount'")
        return Money(amount=int(amt), currency=str(curr))
    if isinstance(val, int) and not isinstance(val, bool):
        return Money(amount=val, currency=default_currency)
    if isinstance(val, float):
        raise ValueError(f"Floating point values are forbidden for monetary evidence: {val}")
    return val


def normalize_evidence_record(
    raw_record: Dict[str, Any],
    default_intent_id: Optional[str] = None,
    ingested_at: Optional[datetime] = None,
) -> Evidence:
    """
    Normalizes a single dictionary of observed evidence into an immutable Evidence item.
    Enforces timezone-aware timestamps, strict typing, and Money value conversion.
    """
    if not isinstance(raw_record, dict):
        raise TypeError(f"raw_record must be dict, got {type(raw_record).__name__}")

    # 1. Resolve source and authority
    raw_source = raw_record.get("source")
    if raw_source is None:
        raise ValueError("Evidence record missing required 'source'")
    source = normalize_source(raw_source)
    authority = normalize_authority(raw_record.get("authority"), source)

    # 2. Field name and value
    field_name = raw_record.get("field_name")
    if not field_name or not isinstance(field_name, str):
        raise ValueError("Evidence record missing or empty 'field_name'")
    
    raw_val = raw_record.get("field_value")
    if field_name in MONETARY_FIELDS:
        field_value = normalize_monetary_value(raw_val)
    else:
        field_value = raw_val

    # 3. Timestamps
    observed_at = raw_record.get("observed_at")
    if observed_at is None:
        raise ValueError("Evidence record missing required 'observed_at' timestamp")
    if isinstance(observed_at, str):
        observed_at = datetime.fromisoformat(observed_at)
    if not isinstance(observed_at, datetime):
        raise TypeError(f"observed_at must be datetime or ISO string, got {type(observed_at).__name__}")
    if observed_at.tzinfo is None:
        raise ValueError("observed_at timestamp must be timezone-aware (e.g., UTC)")

    # Ingested timestamp
    ingest_ts = raw_record.get("ingested_at") or ingested_at
    if isinstance(ingest_ts, str):
        ingest_ts = datetime.fromisoformat(ingest_ts)
    if ingest_ts is not None and ingest_ts.tzinfo is None:
        raise ValueError("ingested_at timestamp must be timezone-aware (e.g., UTC)")

    # 4. Identity & Correlation
    intent_id = raw_record.get("intent_id") or default_intent_id
    if not intent_id:
        raise ValueError("Evidence record missing required 'intent_id'")

    evidence_id = raw_record.get("evidence_id") or f"ev_{uuid.uuid4().hex[:12]}"
    transaction_id = raw_record.get("transaction_id")
    raw_ref = raw_record.get("raw_reference")
    provenance = raw_record.get("provenance", {})
    confidence_score = raw_record.get("confidence_score")

    is_authoritative = authority == EvidenceAuthority.AUTHORITATIVE

    return Evidence(
        evidence_id=str(evidence_id),
        intent_id=str(intent_id),
        transaction_id=str(transaction_id) if transaction_id else None,
        source=source,
        authority=authority,
        field_name=str(field_name),
        field_value=field_value,
        observed_at=observed_at,
        ingested_at=ingest_ts,
        is_authoritative=is_authoritative,
        raw_reference=str(raw_ref) if raw_ref else None,
        provenance=provenance if isinstance(provenance, dict) else {},
        confidence_score=float(confidence_score) if confidence_score is not None else None,
    )


def build_evidence_bundle(
    intent_id: str,
    raw_records: List[Dict[str, Any]],
    raw_events: Optional[List[Dict[str, Any]]] = None,
    transaction_id: Optional[str] = None,
    created_at: Optional[datetime] = None,
    bundle_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> EvidenceBundle:
    """
    Constructs a canonical, immutable EvidenceBundle from raw records and events.
    Applies deterministic ordering and validation across all entries.
    """
    if not intent_id or not intent_id.strip():
        raise ValueError("intent_id cannot be empty")

    b_created_at = created_at or datetime.now().astimezone()
    if b_created_at.tzinfo is None:
        raise ValueError("created_at must be timezone-aware (e.g., UTC)")

    # Normalize records
    normalized_records: List[Evidence] = []
    for r in raw_records:
        normalized_records.append(
            normalize_evidence_record(r, default_intent_id=intent_id, ingested_at=b_created_at)
        )

    # Sort records deterministically: authority rank desc, observed_at desc, evidence_id
    sorted_records = sorted(
        normalized_records,
        key=lambda e: (e.authority_rank, e.observed_at.isoformat(), e.evidence_id),
        reverse=True,
    )

    # Normalize events if supplied
    normalized_events: List[CanonicalEvent] = []
    if raw_events:
        for idx, ev in enumerate(raw_events, start=1):
            if isinstance(ev, CanonicalEvent):
                normalized_events.append(ev)
            elif isinstance(ev, dict):
                ev_amt = ev.get("amount")
                if ev_amt is not None and not isinstance(ev_amt, Money):
                    ev_amt = normalize_monetary_value(ev_amt)
                
                ev_ts = ev.get("timestamp")
                if isinstance(ev_ts, str):
                    ev_ts = datetime.fromisoformat(ev_ts)

                ev_source = normalize_source(ev.get("source", EvidenceSource.MERCHANT))
                normalized_events.append(
                    CanonicalEvent(
                        event_id=ev.get("event_id") or f"evt_{idx}",
                        transaction_id=ev.get("transaction_id") or (transaction_id or "tx_unknown"),
                        intent_id=intent_id,
                        event_type=ev.get("event_type", "OBSERVATION"),
                        timestamp=ev_ts,
                        sequence_number=ev.get("sequence_number", idx),
                        amount=ev_amt,
                        source=ev_source,
                        payload_summary=ev.get("payload_summary", {}),
                    )
                )

    b_id = bundle_id or f"bundle_{uuid.uuid4().hex[:12]}"

    return EvidenceBundle(
        bundle_id=b_id,
        intent_id=intent_id,
        transaction_id=transaction_id,
        created_at=b_created_at,
        records=sorted_records,
        events=normalized_events,
        metadata=metadata or {},
    )
