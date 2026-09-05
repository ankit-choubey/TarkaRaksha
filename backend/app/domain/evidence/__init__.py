"""
Evidence normalization and management package for TarkaRaksha.
Provides provider-neutral normalizers, conflict analysis, and deduplication utilities.
"""
from .normalizer import (
    normalize_source,
    normalize_authority,
    normalize_monetary_value,
    normalize_evidence_record,
    build_evidence_bundle,
)
from .deduplication import (
    deduplicate_evidence,
    deduplicate_events,
)
from .conflicts import (
    ConflictReport,
    resolve_field_evidence,
    analyze_bundle_conflicts,
)

__all__ = [
    "normalize_source",
    "normalize_authority",
    "normalize_monetary_value",
    "normalize_evidence_record",
    "build_evidence_bundle",
    "deduplicate_evidence",
    "deduplicate_events",
    "ConflictReport",
    "resolve_field_evidence",
    "analyze_bundle_conflicts",
]
