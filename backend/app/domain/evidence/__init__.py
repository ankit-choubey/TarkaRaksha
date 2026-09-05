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

__all__ = [
    "normalize_source",
    "normalize_authority",
    "normalize_monetary_value",
    "normalize_evidence_record",
    "build_evidence_bundle",
]
