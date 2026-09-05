"""
Deterministic Recovery Policy & Classification for TarkaRaksha (T11).
Classifies transaction outcomes into:
- RECOVERABLE: A bounded action can plausibly restore integrity without expanding authorization.
- NON_RECOVERABLE: Recovery cannot safely restore the original intent -> forces ABSTAIN.
- UNKNOWN: Evidence is missing or ambiguous; requires re-observation or safe hold.
- ABSTAIN: Safety terminal state preventing financial loss.

Authority & Invariants:
- Pure deterministic function of explicit inputs.
- Zero AI dependencies, zero randomness, zero hidden state.
- Identical inputs yield identical classification.
"""
from datetime import datetime, timezone
from typing import Optional

from backend.app.domain.models import (
    ActionType,
    IntegrityResult,
    IntegrityStatus,
    IntentContract,
    Money,
    MRDP,
    MRDPErrorCode,
)
from .contracts import (
    MAX_RECOVERY_ATTEMPTS,
    RecoverabilityStatus,
    RecoveryClassification,
)


def classify_recovery(
    contract: IntentContract,
    integrity_result: IntegrityResult,
    mrdp: Optional[MRDP] = None,
    current_attempt: int = 1,
    reference_time: Optional[datetime] = None,
) -> RecoveryClassification:
    """
    Deterministically evaluates whether an integrity failure can be safely repaired.
    Strictly forbids expanding the original authorization envelope.
    """
    ts = reference_time or integrity_result.evaluated_at
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)

    # 1. Recovery Attempt Limit Check (§7.42, §9.50)
    # After MAX_RECOVERY_ATTEMPTS (3), control plane MUST abstain to prevent infinite loops.
    if current_attempt >= MAX_RECOVERY_ATTEMPTS:
        return RecoveryClassification(
            status=RecoverabilityStatus.ABSTAIN,
            is_recoverable=False,
            reason=f"Recovery attempts limit ({MAX_RECOVERY_ATTEMPTS}) reached. Escalating to ABSTAIN to prevent infinite side effects.",
            recommended_action=ActionType.HOLD,
            current_attempt=current_attempt,
            max_attempts=MAX_RECOVERY_ATTEMPTS,
        )

    # 2. Temporal Validity Check (§16)
    # If the contract is expired, new financial recovery actions cannot be executed.
    if ts > contract.expires_at:
        return RecoveryClassification(
            status=RecoverabilityStatus.ABSTAIN,
            is_recoverable=False,
            reason=f"IntentContract expired at {contract.expires_at.isoformat()}. Cannot execute compensatory actions post-expiry.",
            recommended_action=ActionType.HOLD,
            current_attempt=current_attempt,
            max_attempts=MAX_RECOVERY_ATTEMPTS,
        )

    # 3. Clean PASS Check
    if integrity_result.status == IntegrityStatus.PASS:
        return RecoveryClassification(
            status=RecoverabilityStatus.RECOVERABLE,
            is_recoverable=False,
            reason="Transaction is in verified PASS status. No recovery required.",
            current_attempt=current_attempt,
            max_attempts=MAX_RECOVERY_ATTEMPTS,
        )

    # 4. UNKNOWN State Classification (§5)
    # UNKNOWN remains UNKNOWN unless recovery obtains new authoritative evidence.
    if integrity_result.status == IntegrityStatus.UNKNOWN:
        explanation = integrity_result.explanation or ""
        violations = integrity_result.violations or []
        all_text = (explanation + " " + " ".join(violations)).lower()

        if "contradictory" in all_text or "conflict" in all_text:
            return RecoveryClassification(
                status=RecoverabilityStatus.ABSTAIN,
                is_recoverable=False,
                reason="Contradictory authoritative evidence cannot be reconciled safely. Escalating to ABSTAIN.",
                recommended_action=ActionType.HOLD,
                current_attempt=current_attempt,
                max_attempts=MAX_RECOVERY_ATTEMPTS,
            )

        # Missing or unconfirmed evidence -> safe to re-observe / query provider
        return RecoveryClassification(
            status=RecoverabilityStatus.UNKNOWN,
            is_recoverable=True,
            reason="Authoritative provider evidence is missing or delayed. Re-observation query recommended.",
            recommended_action=ActionType.NOTIFY,
            current_attempt=current_attempt,
            max_attempts=MAX_RECOVERY_ATTEMPTS,
        )

    # 5. DRIFT State Classification
    # Analyze rule results and violations
    error_code = mrdp.error_code if mrdp else None
    violations_text = " ".join(integrity_result.violations).lower()

    # Case A: Economic Drift (Overcharge)
    # If captured amount exceeded max_total, a compensatory refund of the discrepancy restores integrity.
    is_economic_overcharge = (
        error_code in (MRDPErrorCode.ECONOMIC_AMOUNT_EXCEEDED.value, "ECONOMIC_DRIFT_CEILING_EXCEEDED")
        or "exceeds authorized max_total" in violations_text
        or "observed amount" in violations_text
    )

    if is_economic_overcharge:
        discrepancy = mrdp.discrepancy_amount if mrdp else None
        if discrepancy is not None and discrepancy.amount > 0:
            return RecoveryClassification(
                status=RecoverabilityStatus.RECOVERABLE,
                is_recoverable=True,
                reason=f"Economic overcharge of {discrepancy} detected. Compensatory partial refund will restore budget ceiling.",
                recommended_action=ActionType.REFUND,
                max_allowed_amount=discrepancy,
                current_attempt=current_attempt,
                max_attempts=MAX_RECOVERY_ATTEMPTS,
            )
        # Full order cancellation/void if discrepancy cannot be bounded
        return RecoveryClassification(
            status=RecoverabilityStatus.NON_RECOVERABLE,
            is_recoverable=False,
            reason="Economic overcharge without explicit discrepancy calculation. Automatic partial refund impossible.",
            recommended_action=ActionType.VOID,
            current_attempt=current_attempt,
            max_attempts=MAX_RECOVERY_ATTEMPTS,
        )

    # Case B: Semantic Drift (Unauthorized SKU or Quantity Mismatch)
    is_semantic_drift = (
        error_code in (
            MRDPErrorCode.SEMANTIC_SKU_MISMATCH.value,
            MRDPErrorCode.SEMANTIC_UNAUTHORIZED_SUBSTITUTION.value,
            MRDPErrorCode.SEMANTIC_QUANTITY_MISMATCH.value,
        )
        or "unauthorizedsku" in violations_text
        or "quantity" in violations_text
        or "sku" in violations_text
    )

    if is_semantic_drift:
        # Check if unauthorized item is in allowed substitutions
        return RecoveryClassification(
            status=RecoverabilityStatus.NON_RECOVERABLE,
            is_recoverable=False,
            reason="Unauthorized SKU or quantity executed. Automatic substitution outside authorization envelope is forbidden.",
            recommended_action=ActionType.CANCEL,
            current_attempt=current_attempt,
            max_attempts=MAX_RECOVERY_ATTEMPTS,
        )

    # Case C: Temporal Drift (Double Capture or Expired Event)
    is_temporal_drift = (
        error_code in (
            MRDPErrorCode.TEMPORAL_CONTRACT_EXPIRED.value,
            MRDPErrorCode.TEMPORAL_DUPLICATE_EVENT.value,
            MRDPErrorCode.TEMPORAL_EXCESSIVE_CAPTURES.value,
            MRDPErrorCode.TEMPORAL_TIMEOUT_LATE_SUCCESS.value,
        )
        or "doubleexecutionrisk" in violations_text
        or "expiredexecution" in violations_text
        or "temporal" in violations_text
    )

    if is_temporal_drift:
        return RecoveryClassification(
            status=RecoverabilityStatus.ABSTAIN,
            is_recoverable=False,
            reason="Temporal divergence or double execution detected. Escalating to ABSTAIN to prevent financial loss.",
            recommended_action=ActionType.HOLD,
            current_attempt=current_attempt,
            max_attempts=MAX_RECOVERY_ATTEMPTS,
        )

    # Default fallback: non-recoverable drift
    return RecoveryClassification(
        status=RecoverabilityStatus.NON_RECOVERABLE,
        is_recoverable=False,
        reason=f"Unclassified integrity divergence: {integrity_result.violations}. Escalating to ABSTAIN.",
        recommended_action=ActionType.HOLD,
        current_attempt=current_attempt,
        max_attempts=MAX_RECOVERY_ATTEMPTS,
    )
