"""
Canonicalization and cryptographic digest utilities for TarkaRaksha's proposed
Machine-Readable Drift Proof (MRDP).

Guarantees:
- Tamper-evident integrity of the canonicalized proof representation under SHA-256.
- Deterministic serialization across identical semantic inputs.

Non-Guarantees (Explicit Boundary):
- Does NOT prove author identity or external authenticity.
- Does NOT provide digital signatures or legal non-repudiation (no public-key infrastructure).
"""
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Dict, List, Optional

from backend.app.domain.models.enums import IntegrityStatus
from backend.app.domain.models.money import Money


def _canonicalize_value(val: Any) -> Any:
    """Recursively normalizes arbitrary values into deterministic JSON-compatible primitives."""
    if isinstance(val, Money):
        return {"amount": val.amount, "currency": val.currency}
    if isinstance(val, datetime):
        utc_dt = val.astimezone(timezone.utc)
        return utc_dt.isoformat()
    if isinstance(val, (IntegrityStatus,)):
        return val.value
    if isinstance(val, (list, tuple, set)):
        return [_canonicalize_value(item) for item in val]
    if isinstance(val, dict):
        return {k: _canonicalize_value(v) for k, v in sorted(val.items())}
    return val


def canonicalize_mrdp_dict(
    protocol: str,
    version: str,
    mrdp_id: str,
    intent_id: str,
    error_code: str,
    status: IntegrityStatus,
    violation: str,
    drift_source: str,
    expected_value: Any,
    observed_value: Any,
    discrepancy_amount: Optional[Money],
    evidence_references: List[str],
    remediation: Optional[str],
    revalidation_required: bool,
    generated_at: datetime,
) -> Dict[str, Any]:
    """
    Constructs an explicitly ordered dictionary of proof attributes for canonicalization.
    Sorts evidence_references deterministically.
    """
    sorted_refs = sorted(str(ref) for ref in evidence_references)

    payload = {
        "protocol": str(protocol),
        "version": str(version),
        "mrdp_id": str(mrdp_id),
        "intent_id": str(intent_id),
        "error_code": str(error_code),
        "status": status.value if isinstance(status, IntegrityStatus) else str(status),
        "violation": str(violation),
        "drift_source": str(drift_source),
        "expected_value": _canonicalize_value(expected_value),
        "observed_value": _canonicalize_value(observed_value),
        "discrepancy_amount": _canonicalize_value(discrepancy_amount) if discrepancy_amount else None,
        "evidence_references": sorted_refs,
        "remediation": str(remediation) if remediation else None,
        "revalidation_required": bool(revalidation_required),
        "generated_at": _canonicalize_value(generated_at),
    }
    return payload


def serialize_canonical_mrdp_json(payload: Dict[str, Any]) -> str:
    """
    Produces a byte-deterministic canonical JSON string representation.
    Keys are strictly sorted with no extraneous whitespace separators.
    """
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def compute_mrdp_digest(payload: Dict[str, Any]) -> str:
    """
    Computes a SHA-256 cryptographic digest over the canonical JSON representation of an MRDP.
    Provides tamper-evident proof that the content representation has not been altered.
    """
    canonical_json = serialize_canonical_mrdp_json(payload)
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
