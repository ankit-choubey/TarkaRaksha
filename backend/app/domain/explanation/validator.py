"""Deterministic post-generation validator for I21 Evidence-Aware AI Explanation.

Ensures that AI-generated explanations strictly adhere to deterministic decisions,
execution safety states, actual evidence references, and uncertainty invariants.
Rejects any hallucinated evidence, contradictory decisions, or safety bypass attempts.
"""
from datetime import datetime, timezone
import re
from typing import Any, Dict, List

from backend.app.domain.explanation.contracts import (
    ExplanationClaim,
    ExplanationContext,
    ExplanationValidationResult,
)
from backend.app.domain.kill_switch.contracts import KillSwitchState
from backend.app.domain.models.enums import IntegrityStatus


FORBIDDEN_INJECTION_PATTERNS = [
    r"ignore\s+(previous|all)\s+instructions",
    r"system\s*:\s*override",
    r"override\s+(the\s+)?kill\s*switch",
    r"force\s+(pass|approval)",
    r"authorize\s+payment\s+anyway",
    r"bypass\s+(verification|checks|rules)",
]

PASS_ASSERTION_KEYWORDS = [
    "transaction approved",
    "payment approved",
    "transaction passed",
    "payment passed",
    "verified as safe",
    "definitely fraud-free",
    "no violations found",
    "no drift detected",
]


def validate_explanation(
    context: ExplanationContext,
    candidate_data: Dict[str, Any],
    validation_time: datetime = None,
) -> ExplanationValidationResult:
    """
    Validates candidate explanation data against authoritative context.
    Returns an ExplanationValidationResult detailing is_valid and any violations.
    """
    v_time = validation_time or datetime.now(timezone.utc)
    violations: List[str] = []

    # 1. Structural check: summary and claims must exist
    summary = str(candidate_data.get("summary", "")).strip()
    if not summary:
        violations.append("Explanation summary is missing or empty")

    raw_claims = candidate_data.get("claims", [])
    if not isinstance(raw_claims, list):
        violations.append("Explanation claims must be a list")
        raw_claims = []

    # 2. Decision Consistency
    claimed_decision = candidate_data.get("deterministic_decision")
    if claimed_decision is not None:
        claimed_decision_str = str(claimed_decision).upper().strip()
        expected_decision_str = context.deterministic_decision.value.upper()
        if claimed_decision_str != expected_decision_str:
            violations.append(
                f"Contradictory decision: explanation claimed '{claimed_decision_str}' "
                f"but deterministic decision is '{expected_decision_str}'"
            )

    # Check for illicit PASS claims when deterministic decision is DRIFT or UNKNOWN
    summary_lower = summary.lower()
    if context.deterministic_decision in (IntegrityStatus.DRIFT, IntegrityStatus.UNKNOWN):
        for keyword in PASS_ASSERTION_KEYWORDS:
            if keyword in summary_lower:
                violations.append(
                    f"Illicit pass assertion: summary contains '{keyword}' "
                    f"while deterministic decision is {context.deterministic_decision.value}"
                )

    # 3. Execution State Consistency
    claimed_exec_state = candidate_data.get("execution_state")
    if claimed_exec_state is not None:
        claimed_exec_str = str(claimed_exec_state).upper().strip()
        expected_exec_str = context.kill_switch_state.value.upper()
        if claimed_exec_str != expected_exec_str:
            violations.append(
                f"Contradictory execution state: explanation claimed '{claimed_exec_str}' "
                f"but authoritative state is '{expected_exec_str}'"
            )

    if context.kill_switch_state in (KillSwitchState.KILLED, KillSwitchState.PAUSED, KillSwitchState.REQUIRES_REVALIDATION):
        if "execution allowed" in summary_lower or "execution permitted" in summary_lower:
            violations.append(
                f"Illicit execution permission: explanation claims execution allowed "
                f"while safety state is {context.kill_switch_state.value}"
            )

    # 4. Evidence Reference Consistency (Anti-Hallucination)
    valid_ids = context.valid_evidence_ids
    for idx, claim_dict in enumerate(raw_claims):
        if not isinstance(claim_dict, dict):
            violations.append(f"Claim #{idx} is not a valid dictionary")
            continue

        c_text = str(claim_dict.get("claim_text", "")).strip()
        if not c_text:
            violations.append(f"Claim #{idx} text is missing or empty")

        refs = claim_dict.get("evidence_refs", [])
        if not isinstance(refs, list):
            violations.append(f"Claim #{idx} evidence_refs must be a list")
            continue

        for ref_id in refs:
            if not isinstance(ref_id, str) or not ref_id.strip():
                violations.append(f"Claim #{idx} contains invalid non-string evidence_ref")
                continue
            ref_clean = ref_id.strip()
            if ref_clean not in valid_ids:
                violations.append(
                    f"Hallucinated evidence reference '{ref_clean}' in claim #{idx}: "
                    f"does not exist in authoritative context"
                )

        # Check claim text for illicit pass assertions when DRIFT/UNKNOWN
        c_text_lower = c_text.lower()
        if context.deterministic_decision in (IntegrityStatus.DRIFT, IntegrityStatus.UNKNOWN):
            for keyword in PASS_ASSERTION_KEYWORDS:
                if keyword in c_text_lower:
                    violations.append(
                        f"Claim #{idx} illicitly asserts '{keyword}' "
                        f"while deterministic decision is {context.deterministic_decision.value}"
                    )

    # 5. Uncertainty Preservation Check
    if context.deterministic_decision == IntegrityStatus.UNKNOWN:
        uncertainties = candidate_data.get("uncertainties", [])
        missing_ev = candidate_data.get("missing_evidence", [])
        if not uncertainties and not missing_ev and not context.uncertainty_notes:
            violations.append("Explanation failed to articulate required uncertainty for UNKNOWN decision")

    # 6. Prompt Injection Defense
    full_text = f"{summary} {' '.join(str(c.get('claim_text', '')) for c in raw_claims if isinstance(c, dict))}"
    for pat in FORBIDDEN_INJECTION_PATTERNS:
        if re.search(pat, full_text, re.IGNORECASE):
            violations.append(f"Adversarial instruction detected matching pattern: {pat}")

    return ExplanationValidationResult(
        is_valid=(len(violations) == 0),
        violations=violations,
        validated_at=v_time,
    )
