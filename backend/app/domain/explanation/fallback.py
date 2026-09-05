"""Deterministic fallback generator for I21 Evidence-Aware AI Explanation.

Synthesizes structured, fully verifiable, and evidence-grounded explanations
directly from an ExplanationContext without invoking external LLMs.
Used whenever an LLM is unavailable, times out, or produces ungrounded output.
"""
from datetime import datetime, timezone
import uuid
from typing import Any, Dict, List

from backend.app.domain.explanation.contracts import (
    ClaimType,
    EvidenceReference,
    ExplanationClaim,
    ExplanationContext,
    ExplanationResult,
    ExplanationValidationResult,
    FindingCategory,
)
from backend.app.domain.kill_switch.contracts import KillSwitchState
from backend.app.domain.models.enums import EvidenceAuthority, IntegrityStatus


def build_deterministic_fallback(
    context: ExplanationContext,
    fallback_reason: str = "Deterministic fallback invoked",
    generation_time: datetime = None,
) -> ExplanationResult:
    """
    Constructs a deterministic, evidence-grounded ExplanationResult directly
    from an ExplanationContext.
    Guarantees 100% decision and evidence consistency without AI hallucination.
    """
    gen_time = generation_time or datetime.now(timezone.utc)
    explanation_id = f"exp_fallback_{uuid.uuid4().hex[:12]}"

    # 1. Synthesize Summary
    if context.deterministic_decision == IntegrityStatus.PASS:
        summary = (
            f"Transaction '{context.transaction_id}' strictly conforms to authorized "
            f"economic, semantic, temporal, and binding constraints. "
            f"Deterministic integrity check PASSED."
        )
    elif context.deterministic_decision == IntegrityStatus.DRIFT:
        violations_str = "; ".join(context.integrity_violations + context.binding_violations)
        summary = (
            f"Transaction '{context.transaction_id}' diverged from authorized intent: {violations_str}. "
            f"Execution safety state: {context.kill_switch_state.value}."
        )
    else:  # UNKNOWN
        uncertainty_str = "; ".join(context.uncertainty_notes) if context.uncertainty_notes else "Required evidence unavailable"
        summary = (
            f"Transaction '{context.transaction_id}' integrity cannot be deterministically verified: "
            f"{uncertainty_str}. Status remains UNKNOWN."
        )

    # 2. Build Grounded Claims from Context EvidenceReferences
    claims: List[ExplanationClaim] = []
    for idx, ref in enumerate(context.evidence_references):
        claim_id = f"claim_{idx + 1}"
        category = _map_field_to_category(ref.field_name)

        if ref.expected_value is not None:
            if ref.observed_value == ref.expected_value:
                claim_text = (
                    f"Verified field '{ref.field_name}': observed value '{ref.observed_value}' "
                    f"matched expected authorized value '{ref.expected_value}'."
                )
            else:
                claim_text = (
                    f"Discrepancy in field '{ref.field_name}': observed value '{ref.observed_value}' "
                    f"did not match expected authorized value '{ref.expected_value}'."
                )
        else:
            claim_text = f"Observed factual field '{ref.field_name}' with value '{ref.observed_value}'."

        claims.append(
            ExplanationClaim(
                claim_id=claim_id,
                claim_text=claim_text,
                evidence_refs=[ref.evidence_id],
                authority_tier=ref.authority,
                claim_type=ClaimType.FACT,
                category=category,
            )
        )

    # If no evidence references exist, provide a baseline context claim
    if not claims:
        claims.append(
            ExplanationClaim(
                claim_id="claim_1",
                claim_text=f"Deterministic evaluation recorded status '{context.deterministic_decision.value}' for transaction.",
                evidence_refs=[],
                authority_tier=EvidenceAuthority.SYSTEM_DERIVED,
                claim_type=ClaimType.FACT,
                category=FindingCategory.SYSTEM,
            )
        )

    # 3. Build Mismatches
    mismatches: List[Dict[str, Any]] = []
    for v in context.integrity_violations:
        mismatches.append({"type": "INTEGRITY_DRIFT", "violation": v})
    for bv in context.binding_violations:
        mismatches.append({"type": "BINDING_MISMATCH", "violation": bv})

    # 4. Determine Recommended Next Action
    if context.kill_switch_state == KillSwitchState.KILLED:
        recommended_action = (
            "Execution is terminated by the Kill Switch. "
            "Perform authorized revalidation or administrative remediation before retrying."
        )
    elif context.kill_switch_state == KillSwitchState.REQUIRES_REVALIDATION:
        recommended_action = (
            "Execution is held pending revalidation. Submit authoritative evidence "
            "matching transaction, intent, and agent identifiers to resume."
        )
    elif context.kill_switch_state == KillSwitchState.PAUSED:
        recommended_action = "Transaction is paused under administrative observation hold."
    elif context.deterministic_decision == IntegrityStatus.PASS:
        recommended_action = "No remediation needed; transaction is verified and execution is permitted."
    elif context.deterministic_decision == IntegrityStatus.UNKNOWN:
        recommended_action = "Await authoritative payment gateway evidence or trigger reconciliation query."
    else:
        recommended_action = "Review drift proof and initiate compensation or refund workflow."

    # 5. Build Result
    validation_res = ExplanationValidationResult(
        is_valid=True,
        violations=[],
        validated_at=gen_time,
    )

    return ExplanationResult(
        explanation_id=explanation_id,
        transaction_id=context.transaction_id,
        deterministic_decision=context.deterministic_decision,
        execution_state=context.kill_switch_state,
        summary=summary,
        claims=claims,
        mismatches=mismatches,
        missing_evidence=list(context.missing_evidence_fields),
        uncertainties=list(context.uncertainty_notes),
        recommended_next_action=recommended_action,
        validation_result=validation_res,
        is_fallback=True,
        model_metadata={
            "engine": "deterministic_fallback",
            "reason": fallback_reason,
        },
        generated_at=gen_time,
    )


def _map_field_to_category(field_name: str) -> FindingCategory:
    """Helper to map field names to canonical FindingCategories."""
    field_lower = field_name.lower()
    if "amount" in field_lower or "currency" in field_lower or "price" in field_lower:
        return FindingCategory.ECONOMIC
    elif "sku" in field_lower or "quantity" in field_lower or "item" in field_lower:
        return FindingCategory.SEMANTIC
    elif "time" in field_lower or "date" in field_lower or "expired" in field_lower:
        return FindingCategory.TEMPORAL
    elif "binding" in field_lower or "order" in field_lower or "agent" in field_lower or "merchant" in field_lower:
        return FindingCategory.BINDING
    elif "kill" in field_lower or "safety" in field_lower:
        return FindingCategory.KILL_SWITCH
    elif "policy" in field_lower:
        return FindingCategory.POLICY
    return FindingCategory.SYSTEM
