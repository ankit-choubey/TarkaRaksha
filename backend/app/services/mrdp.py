"""
Machine-Readable Drift Proof (MRDP) service for TarkaRaksha.
Constructs structured, auditable proofs of detected divergence between authorized intent and observed evidence.

Note: MRDP is TarkaRaksha's proposed Machine-Readable Drift Proof protocol, NOT an existing industry standard.
"""
from datetime import datetime, timezone
import hashlib
from typing import Any, List, Optional
import uuid

from backend.app.domain.models.enums import IntegrityStatus
from backend.app.domain.models.evidence import EvidenceBundle
from backend.app.domain.models.intent import IntentContract
from backend.app.domain.models.integrity import MRDP, MRDPErrorCode, IntegrityResult
from backend.app.domain.models.money import Money

from .canonicalization import canonicalize_mrdp_dict, compute_mrdp_digest


FORBIDDEN_REMEDIATION_PHRASES = [
    "increase budget",
    "ignore constraint",
    "bypass verifier",
    "force pass",
    "alter original authorization",
    "suppress evidence",
    "capture without authorization",
]


def _determine_error_code(violation_text: str, integrity_result: IntegrityResult) -> str:
    """Deterministically maps integrity violation strings to stable MRDPErrorCodes."""
    text_lower = violation_text.lower()
    if "currency mismatch" in text_lower:
        return MRDPErrorCode.ECONOMIC_CURRENCY_MISMATCH.value
    if "exceeded authorized" in text_lower or "amount" in text_lower:
        return MRDPErrorCode.ECONOMIC_AMOUNT_EXCEEDED.value
    if "sku mismatch" in text_lower or "unauthorized sku" in text_lower:
        return MRDPErrorCode.SEMANTIC_SKU_MISMATCH.value
    if "quantity" in text_lower:
        return MRDPErrorCode.SEMANTIC_QUANTITY_MISMATCH.value
    if "duplicate event" in text_lower:
        return MRDPErrorCode.TEMPORAL_DUPLICATE_EVENT.value
    if "capture count" in text_lower or "excessive captures" in text_lower:
        return MRDPErrorCode.TEMPORAL_EXCESSIVE_CAPTURES.value
    if "expired" in text_lower:
        return MRDPErrorCode.TEMPORAL_CONTRACT_EXPIRED.value
    if "conflict" in text_lower:
        return MRDPErrorCode.EVIDENCE_CONFLICT_UNRESOLVED.value
    return MRDPErrorCode.GENERAL_DRIFT.value


def _build_safe_remediation_hint(error_code: str) -> str:
    """Provides bounded, advisory remediation hints without authorization escalation."""
    if error_code == MRDPErrorCode.ECONOMIC_AMOUNT_EXCEEDED.value:
        return "Obtain compensatory refund for excess amount from merchant or void transaction."
    if error_code == MRDPErrorCode.ECONOMIC_CURRENCY_MISMATCH.value:
        return "Cancel transaction due to unauthorized currency and re-execute in authorized currency."
    if error_code in (MRDPErrorCode.SEMANTIC_SKU_MISMATCH.value, MRDPErrorCode.SEMANTIC_QUANTITY_MISMATCH.value):
        return "Request merchant item replacement for authorized SKU or initiate return/refund."
    if error_code == MRDPErrorCode.TEMPORAL_DUPLICATE_EVENT.value:
        return "Verify duplicate event idempotency with payment provider and void duplicate capture."
    if error_code == MRDPErrorCode.TEMPORAL_EXCESSIVE_CAPTURES.value:
        return "Initiate immediate refund for unauthorized duplicate capture attempt."
    if error_code == MRDPErrorCode.TEMPORAL_CONTRACT_EXPIRED.value:
        return "Transaction expired prior to execution; release hold and do not fulfill."
    if error_code == MRDPErrorCode.EVIDENCE_CONFLICT_UNRESOLVED.value:
        return "Poll authoritative payment gateway directly to resolve conflicting provider state."
    return "Revalidate transaction against authorized intent baseline."


def validate_remediation_safety(hint: Optional[str]) -> None:
    """Asserts that a remediation hint does not advise unauthorized budget increases or rule bypasses."""
    if not hint:
        return
    lower_hint = hint.lower()
    for phrase in FORBIDDEN_REMEDIATION_PHRASES:
        if phrase in lower_hint:
            raise ValueError(f"Remediation hint contains forbidden instruction: '{phrase}'")


def build_mrdp(
    contract: IntentContract,
    integrity_result: IntegrityResult,
    evidence_bundle: EvidenceBundle,
    generated_at: Optional[datetime] = None,
    mrdp_id: Optional[str] = None,
    protocol: str = "TarkaRaksha-MRDP",
    version: str = "1.0.0",
) -> MRDP:
    """
    Constructs a verifiable, immutable Machine-Readable Drift Proof (MRDP).
    Encapsulates exact divergence between authorized intent and observed reality.
    Computes a cryptographic SHA-256 tamper-evident digest over the canonical representation.
    """
    # 1. Status Guard: MRDP is only generated for non-passing outcomes (DRIFT or UNKNOWN)
    if integrity_result.status == IntegrityStatus.PASS:
        raise ValueError(
            "Cannot build MRDP for passing transaction; MRDP is strictly generated for DRIFT or UNKNOWN verification outcomes."
        )

    # 2. Intent ID alignment
    if contract.intent_id != integrity_result.intent_id:
        raise ValueError(
            f"Intent ID mismatch: contract {contract.intent_id} != integrity_result {integrity_result.intent_id}"
        )
    if evidence_bundle.intent_id != contract.intent_id:
        raise ValueError(
            f"Intent ID mismatch: contract {contract.intent_id} != evidence_bundle {evidence_bundle.intent_id}"
        )

    # 3. Deterministic timestamp
    ts = generated_at or integrity_result.evaluated_at
    if ts.tzinfo is None:
        raise ValueError("generated_at timestamp must be timezone-aware (e.g. UTC)")

    # 4. Primary violation & error code
    primary_violation = (
        integrity_result.violations[0]
        if integrity_result.violations
        else (integrity_result.explanation or f"Integrity divergence detected: {integrity_result.status.value}")
    )
    error_code = _determine_error_code(primary_violation, integrity_result)

    # 5. Extract expected vs observed values
    expected_value: Any = None
    observed_value: Any = None
    discrepancy_amount: Optional[Money] = None
    drift_source = "UNKNOWN"

    if error_code == MRDPErrorCode.ECONOMIC_AMOUNT_EXCEEDED.value:
        expected_value = contract.max_total
        ev_amt = evidence_bundle.get_authoritative_evidence("total_amount")
        if ev_amt and isinstance(ev_amt.field_value, Money):
            observed_value = ev_amt.field_value
            drift_source = ev_amt.source.value
            if observed_value.amount > contract.max_total.amount:
                discrepancy_amount = Money(
                    amount=observed_value.amount - contract.max_total.amount,
                    currency=contract.max_total.currency,
                )
        else:
            observed_value = "Amount exceeded authorized maximum"
            drift_source = "PAYMENT_GATEWAY"
    elif error_code == MRDPErrorCode.ECONOMIC_CURRENCY_MISMATCH.value:
        expected_value = contract.currency
        ev_amt = evidence_bundle.get_authoritative_evidence("total_amount")
        if ev_amt and isinstance(ev_amt.field_value, Money):
            observed_value = ev_amt.field_value.currency
            drift_source = ev_amt.source.value
        else:
            observed_value = "Currency mismatch"
            drift_source = "PAYMENT_GATEWAY"
    elif error_code == MRDPErrorCode.SEMANTIC_SKU_MISMATCH.value:
        expected_value = [item.sku for item in contract.items]
        ev_sku = evidence_bundle.get_authoritative_evidence("sku")
        if ev_sku:
            observed_value = str(ev_sku.field_value)
            drift_source = ev_sku.source.value
        else:
            observed_value = "Unauthorized SKU observed"
            drift_source = "MERCHANT"
    else:
        expected_value = "Authorized transaction constraints satisfied"
        observed_value = primary_violation
        if integrity_result.evidence_ids and evidence_bundle.records:
            ev_first = evidence_bundle.records[0]
            drift_source = ev_first.source.value

    # 6. Evidence references (only IDs from evidence_bundle and integrity_result)
    raw_refs = integrity_result.evidence_ids or evidence_bundle.evidence_ids
    evidence_references = sorted(list(set(raw_refs)))

    # 7. Remediation hint
    remediation_hint = _build_safe_remediation_hint(error_code)
    validate_remediation_safety(remediation_hint)

    # 8. Deterministic ID if not supplied
    proof_id = mrdp_id or f"mrdp_{hashlib.sha256((contract.intent_id + ts.isoformat()).encode()).hexdigest()[:16]}"

    # 9. Compute tamper-evident digest
    canonical_payload = canonicalize_mrdp_dict(
        protocol=protocol,
        version=version,
        mrdp_id=proof_id,
        intent_id=contract.intent_id,
        error_code=error_code,
        status=integrity_result.status,
        violation=primary_violation,
        drift_source=drift_source,
        expected_value=expected_value,
        observed_value=observed_value,
        discrepancy_amount=discrepancy_amount,
        evidence_references=evidence_references,
        remediation=remediation_hint,
        revalidation_required=True,
        generated_at=ts,
    )
    digest = compute_mrdp_digest(canonical_payload)

    return MRDP(
        protocol=protocol,
        version=version,
        mrdp_id=proof_id,
        intent_id=contract.intent_id,
        error_code=error_code,
        status=integrity_result.status,
        violation=primary_violation,
        drift_source=drift_source,
        expected_value=expected_value,
        observed_value=observed_value,
        discrepancy_amount=discrepancy_amount,
        evidence_references=evidence_references,
        remediation=remediation_hint,
        revalidation_required=True,
        generated_at=ts,
        proof_digest=digest,
    )


def verify_mrdp_integrity(mrdp: MRDP) -> bool:
    """
    Verifies the tamper-evident integrity of an MRDP instance.
    Re-serializes the canonical proof payload and checks if the resulting SHA-256 digest
    matches the embedded proof_digest.
    
    Guarantees:
    - Returns True if and only if every field in the proof payload matches the original digest.
    - Returns False if any field (amount, status, violation, evidence_ref) has been modified.
    """
    if not mrdp.proof_digest:
        return False

    canonical_payload = canonicalize_mrdp_dict(
        protocol=mrdp.protocol,
        version=mrdp.version,
        mrdp_id=mrdp.mrdp_id,
        intent_id=mrdp.intent_id,
        error_code=mrdp.error_code,
        status=mrdp.status,
        violation=mrdp.violation,
        drift_source=mrdp.drift_source,
        expected_value=mrdp.expected_value,
        observed_value=mrdp.observed_value,
        discrepancy_amount=mrdp.discrepancy_amount,
        evidence_references=mrdp.evidence_references,
        remediation=mrdp.remediation,
        revalidation_required=mrdp.revalidation_required,
        generated_at=mrdp.generated_at,
    )
    expected_digest = compute_mrdp_digest(canonical_payload)
    return expected_digest == mrdp.proof_digest
