"""
Evidence conflict detection and deterministic resolution for TarkaRaksha.
Enforces authority hierarchy without guessing:
- When authority ranks differ, the higher-authority record dominates.
- When contradictory evidence exists at the highest rank, returns an unresolved report
  preserving ambiguity for downstream UNKNOWN integrity evaluation.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from backend.app.domain.models.evidence import Evidence


class ConflictReport(BaseModel):
    """
    Structured outcome of evidence conflict analysis for a specific field.
    """
    field_name: str
    is_resolved: bool
    winning_evidence: Optional[Evidence] = None
    conflicting_records: List[Evidence] = Field(default_factory=list)
    resolution_reason: str

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )


def resolve_field_evidence(
    field_name: str,
    records: List[Evidence],
) -> ConflictReport:
    """
    Evaluates all evidence records for a single field_name.
    Deterministically resolves authority dominance or records unresolved conflict.
    """
    matching = [r for r in records if r.field_name == field_name]
    if not matching:
        return ConflictReport(
            field_name=field_name,
            is_resolved=False,
            winning_evidence=None,
            conflicting_records=[],
            resolution_reason="No evidence records found for field",
        )

    if len(matching) == 1:
        return ConflictReport(
            field_name=field_name,
            is_resolved=True,
            winning_evidence=matching[0],
            conflicting_records=[],
            resolution_reason="Single uncontested evidence record",
        )

    # Sort descending by authority rank, then observed_at, then evidence_id
    sorted_records = sorted(
        matching,
        key=lambda e: (e.authority_rank, e.observed_at.isoformat(), e.evidence_id),
        reverse=True,
    )

    highest_rank = sorted_records[0].authority_rank
    top_tier = [r for r in sorted_records if r.authority_rank == highest_rank]

    # Check for contradiction within top tier
    first_val = top_tier[0].field_value
    contradictions = [r for r in top_tier[1:] if r.field_value != first_val]

    if contradictions:
        # Irreconcilable conflict at highest authority rank
        return ConflictReport(
            field_name=field_name,
            is_resolved=False,
            winning_evidence=None,
            conflicting_records=top_tier,
            resolution_reason=(
                f"Irreconcilable conflict at top authority rank ({highest_rank}): "
                f"multiple records disagree on {field_name}"
            ),
        )

    # Top tier is internally consistent; check if lower tiers had differing values (provenance)
    winning = top_tier[0]
    subordinate_contradictions = [
        r for r in sorted_records if r.authority_rank < highest_rank and r.field_value != first_val
    ]

    reason = (
        f"Resolved via authority dominance: rank {highest_rank} overrides lower-tier records"
        if subordinate_contradictions
        else "All evidence records in agreement"
    )

    return ConflictReport(
        field_name=field_name,
        is_resolved=True,
        winning_evidence=winning,
        conflicting_records=subordinate_contradictions,
        resolution_reason=reason,
    )


def analyze_bundle_conflicts(records: List[Evidence]) -> Dict[str, ConflictReport]:
    """
    Runs conflict analysis across all distinct fields present in records.
    Returns mapping of field_name to its ConflictReport.
    """
    fields = sorted({r.field_name for r in records})
    reports: Dict[str, ConflictReport] = {}
    for f in fields:
        reports[f] = resolve_field_evidence(f, records)
    return reports
