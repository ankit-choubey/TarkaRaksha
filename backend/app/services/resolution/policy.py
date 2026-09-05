"""
Deterministic UNKNOWN Resolution Policy & Diagnosis for TarkaRaksha (T12).
Classifies UNKNOWN states into:
- RESOLVABLE: Additional authoritative observation or hierarchy reconciliation can resolve ambiguity.
- REMAINS_UNKNOWN: Authoritative evidence is missing and cannot be established safely.
- ABSTAIN: Unsafe state (expired contract, conflicting authoritative evidence, attempt budget exhausted).

Authority & Invariants:
- Pure deterministic function of explicit inputs.
- Zero AI dependencies, zero randomness, zero hidden assumptions.
- Identical inputs yield identical diagnosis.
"""
from datetime import datetime, timezone
from typing import List, Optional

from backend.app.domain.evidence import analyze_bundle_conflicts
from backend.app.domain.models import (
    EvidenceAuthority,
    EvidenceBundle,
    IntegrityResult,
    IntegrityStatus,
    IntentContract,
    MRDP,
)
from .contracts import (
    MAX_RESOLUTION_ATTEMPTS,
    ResolutionCategory,
    ResolutionDiagnosis,
    ResolutionStrategy,
)


def diagnose_unknown(
    contract: IntentContract,
    integrity_result: IntegrityResult,
    evidence_bundle: Optional[EvidenceBundle] = None,
    mrdp: Optional[MRDP] = None,
    current_attempt: int = 1,
    reference_time: Optional[datetime] = None,
) -> ResolutionDiagnosis:
    """
    Deterministically diagnoses why a transaction is in UNKNOWN state and identifies
    the appropriate safe, non-side-effecting observation strategy.
    """
    ts = reference_time or integrity_result.evaluated_at
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)

    # 1. Attempt Budget Bound Check (§9, §18)
    if current_attempt >= MAX_RESOLUTION_ATTEMPTS:
        return ResolutionDiagnosis(
            category=ResolutionCategory.ABSTAIN,
            strategy=ResolutionStrategy.HOLD_OBSERVATION,
            reason=f"Resolution attempt budget ({MAX_RESOLUTION_ATTEMPTS}) reached. Escalating to ABSTAIN to prevent infinite observation loops.",
            current_attempt=current_attempt,
            max_attempts=MAX_RESOLUTION_ATTEMPTS,
        )

    # 2. Temporal Expiration Check (§11, §16)
    # If the contract is expired, the system must not resolve or authorize actions
    if ts > contract.expires_at:
        return ResolutionDiagnosis(
            category=ResolutionCategory.ABSTAIN,
            strategy=ResolutionStrategy.HOLD_OBSERVATION,
            reason=f"IntentContract expired at {contract.expires_at.isoformat()}. Cannot resolve UNKNOWN post-expiration.",
            current_attempt=current_attempt,
            max_attempts=MAX_RESOLUTION_ATTEMPTS,
        )

    # 3. Non-UNKNOWN Status Guard
    if integrity_result.status == IntegrityStatus.PASS:
        return ResolutionDiagnosis(
            category=ResolutionCategory.RESOLVABLE,
            strategy=ResolutionStrategy.HOLD_OBSERVATION,
            reason="Transaction is in verified PASS status. No resolution required.",
            current_attempt=current_attempt,
            max_attempts=MAX_RESOLUTION_ATTEMPTS,
        )

    if integrity_result.status == IntegrityStatus.DRIFT:
        return ResolutionDiagnosis(
            category=ResolutionCategory.RESOLVABLE,
            strategy=ResolutionStrategy.HOLD_OBSERVATION,
            reason="Transaction is in confirmed DRIFT status. Hand over to T11 Recovery loop.",
            current_attempt=current_attempt,
            max_attempts=MAX_RESOLUTION_ATTEMPTS,
        )

    # 4. Check for Conflicting Authoritative Evidence (§12)
    # Using T06 conflict resolution engine
    conflicting_fields: List[str] = []
    if evidence_bundle and evidence_bundle.records:
        conflict_reports = analyze_bundle_conflicts(evidence_bundle.records)
        for field_name, report in conflict_reports.items():
            if not report.is_resolved:
                conflicting_fields.append(field_name)

    if conflicting_fields:
        return ResolutionDiagnosis(
            category=ResolutionCategory.ABSTAIN,
            strategy=ResolutionStrategy.HOLD_OBSERVATION,
            conflicting_fields=conflicting_fields,
            reason=(
                f"Irreconcilable conflict detected at top authority rank for fields: {conflicting_fields}. "
                "Control plane cannot guess between contradictory authoritative records. Escalating to ABSTAIN."
            ),
            current_attempt=current_attempt,
            max_attempts=MAX_RESOLUTION_ATTEMPTS,
        )

    # 5. Missing Evidence Assessment (§4, §7)
    records = evidence_bundle.records if evidence_bundle else []
    authoritative_records = [r for r in records if r.authority == EvidenceAuthority.AUTHORITATIVE]
    has_authoritative_amount = any(r.field_name == "total_amount" for r in authoritative_records)
    has_authoritative_status = any(r.field_name == "payment_status" for r in authoritative_records)

    missing_fields: List[str] = []
    if not has_authoritative_amount:
        missing_fields.append("total_amount")
    if not has_authoritative_status:
        missing_fields.append("payment_status")

    # If authoritative evidence is missing, safe observation can acquire it
    if missing_fields:
        explanation = (integrity_result.explanation or "").lower()
        violations_text = " ".join(integrity_result.violations).lower()
        all_text = explanation + " " + violations_text

        # Check if we have an explicit payment reference
        has_payment_ref = any(r.raw_reference and r.raw_reference.startswith("pay_") for r in records)
        
        if has_payment_ref:
            strategy = ResolutionStrategy.FETCH_PAYMENT
        else:
            strategy = ResolutionStrategy.FETCH_ORDER_PAYMENTS

        return ResolutionDiagnosis(
            category=ResolutionCategory.RESOLVABLE,
            strategy=strategy,
            missing_fields=missing_fields,
            reason="Authoritative provider payment evidence is missing or unconfirmed. Safe observation query recommended.",
            current_attempt=current_attempt,
            max_attempts=MAX_RESOLUTION_ATTEMPTS,
        )

    # 6. Default Fallback
    return ResolutionDiagnosis(
        category=ResolutionCategory.REMAINS_UNKNOWN,
        strategy=ResolutionStrategy.HOLD_OBSERVATION,
        reason="Transaction outcome cannot be deterministically established with available evidence. Remains UNKNOWN.",
        current_attempt=current_attempt,
        max_attempts=MAX_RESOLUTION_ATTEMPTS,
    )
