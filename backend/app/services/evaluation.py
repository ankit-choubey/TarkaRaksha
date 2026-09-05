"""
Deterministic Integrity Evaluation Service for TarkaRaksha (T04).
Coordinates economic, semantic, and temporal evaluation over an IntentContract and evidence bundle.

Authority & Invariants:
- Deterministic: same inputs -> exact same output.
- No LLM calls, no network, no database, no random values.
- Priority Semantics:
    1. If any sub-check yields DRIFT -> overall DRIFT (violations aggregated).
    2. If no DRIFT, but any required check yields UNKNOWN -> overall UNKNOWN (cannot guess PASS).
    3. Only if all applicable sub-checks yield PASS -> overall PASS.
- Explainable: maps rules to boolean results, violations, and supporting evidence references.
"""
from datetime import datetime
from typing import List, Optional
from backend.app.domain.models import (
    CanonicalEvent,
    Evidence,
    IntegrityResult,
    IntegrityStatus,
    IntentContract,
)
from backend.app.domain.rules import (
    check_economic,
    check_semantic,
    check_temporal,
)


def evaluate_integrity(
    contract: IntentContract,
    evidence_list: List[Evidence],
    events: Optional[List[CanonicalEvent]] = None,
    evaluation_id: Optional[str] = None,
    reference_time: Optional[datetime] = None,
) -> IntegrityResult:
    """
    Evaluates transaction integrity deterministically against an authorized IntentContract.

    Parameters:
    - contract: Immutable specification of authorized intent.
    - evidence_list: Normalized evidence items with source and authority rankings.
    - events: Optional chronological lifecycle events for temporal evaluation.
    - evaluation_id: Deterministic identifier for this evaluation (defaults to eval-{intent_id}).
    - reference_time: Explicit evaluation timestamp to preserve complete determinism.
    """
    if events is None:
        events = []

    eval_id = evaluation_id or f"eval-{contract.intent_id}"
    eval_time = reference_time or contract.issued_at

    # 1. Run the three core domain checks
    econ_result = check_economic(contract, evidence_list)
    semantic_result = check_semantic(contract, evidence_list)
    temporal_result = check_temporal(contract, events, evidence_list)

    # 2. Compile rule results and aggregated evidence
    rule_results = {
        econ_result.rule_name: econ_result.is_pass,
        semantic_result.rule_name: semantic_result.is_pass,
        temporal_result.rule_name: temporal_result.is_pass,
    }

    all_evidence_ids = sorted(
        list(
            set(
                econ_result.evidence_ids
                + semantic_result.evidence_ids
                + temporal_result.evidence_ids
            )
        )
    )

    violations = []
    if econ_result.violation:
        violations.append(econ_result.violation)
    if semantic_result.violation:
        violations.append(semantic_result.violation)
    if temporal_result.violation:
        violations.append(temporal_result.violation)

    # 3. Apply Decision Priority Semantics
    # DRIFT takes precedence because a confirmed violation cannot be ignored.
    # If no DRIFT, any UNKNOWN forces overall UNKNOWN (safety invariant: missing evidence is not PASS).
    # PASS is achieved only if all dimensions pass.
    sub_statuses = [econ_result.status, semantic_result.status, temporal_result.status]

    if IntegrityStatus.DRIFT in sub_statuses:
        overall_status = IntegrityStatus.DRIFT
        explanation = f"Transaction drifted from authorized intent: {'; '.join(violations)}"
        confidence_score = 1.0
    elif IntegrityStatus.UNKNOWN in sub_statuses:
        overall_status = IntegrityStatus.UNKNOWN
        reasons = []
        if econ_result.is_unknown:
            reasons.append(f"Economic: {econ_result.explanation}")
        if semantic_result.is_unknown:
            reasons.append(f"Semantic: {semantic_result.explanation}")
        if temporal_result.is_unknown:
            reasons.append(f"Temporal: {temporal_result.explanation}")
        explanation = f"Integrity could not be deterministically proven: {'; '.join(reasons)}"
        confidence_score = 0.5
    else:
        overall_status = IntegrityStatus.PASS
        explanation = "Transaction strictly conforms to authorized economic, semantic, and temporal constraints"
        confidence_score = 1.0

    return IntegrityResult(
        evaluation_id=eval_id,
        intent_id=contract.intent_id,
        status=overall_status,
        evaluated_at=eval_time,
        rule_results=rule_results,
        violations=violations,
        evidence_ids=all_evidence_ids,
        confidence_score=confidence_score,
        explanation=explanation,
    )
