"""
Economic Integrity Check for TarkaRaksha (T04).
Compares observed transaction economics against the authorized IntentContract.

Invariants:
- Uses integer minor units exclusively; zero floating-point arithmetic.
- Deterministic boundary:
    observed_amount <= max_total -> PASS
    observed_amount > max_total -> DRIFT
    (e.g., ₹49,999 -> PASS, ₹50,000 -> PASS, ₹50,001 -> DRIFT)
- Currency mismatch -> DRIFT.
- Missing or contradictory amount evidence -> UNKNOWN.
- Resolves evidence conflicts using deterministic authority ranking.
"""
from typing import List, Optional
from backend.app.domain.models import (
    Evidence,
    EvidenceSource,
    IntegrityStatus,
    IntentContract,
    Money,
)
from .base import RuleResult


def _extract_authoritative_money(
    evidence_items: List[Evidence],
    field_name: str,
) -> tuple[Optional[Money], List[str], Optional[str]]:
    """
    Finds and resolves the authoritative Money value for field_name across evidence items.
    Returns (money_value, evidence_ids_used, conflict_error).
    If contradictory evidence exists at the same highest authority rank, returns (None, ids, conflict_error).
    """
    matching = [e for e in evidence_items if e.field_name == field_name]
    if not matching:
        return None, [], "missing"

    # Sort matching by authority_rank descending, then observed_at descending, then evidence_id
    sorted_ev = sorted(
        matching,
        key=lambda e: (e.authority_rank, e.observed_at.isoformat(), e.evidence_id),
        reverse=True,
    )

    highest_rank = sorted_ev[0].authority_rank
    top_tier = [e for e in sorted_ev if e.authority_rank == highest_rank]

    # Check for contradiction within the top authority tier
    first_val = top_tier[0].field_value
    # Ensure value is Money or dict representable as Money
    if isinstance(first_val, dict):
        try:
            first_val = Money(**first_val)
        except Exception:
            return None, [top_tier[0].evidence_id], "malformed"
    elif not isinstance(first_val, Money):
        return None, [top_tier[0].evidence_id], "malformed"

    for ev in top_tier[1:]:
        val = ev.field_value
        if isinstance(val, dict):
            try:
                val = Money(**val)
            except Exception:
                return None, [e.evidence_id for e in top_tier], "malformed"
        if val != first_val:
            # Irreconcilable conflict at highest authority rank
            return None, [e.evidence_id for e in top_tier], "conflict"

    return first_val, [top_tier[0].evidence_id], None


def check_economic(
    contract: IntentContract,
    evidence_list: List[Evidence],
) -> RuleResult:
    """
    Deterministically evaluates economic integrity.
    Checks:
    1. Presence of observed amount.
    2. Currency matching.
    3. Maximum total amount constraint (integer minor units).
    """
    rule_name = "EconomicIntegrityRule"

    observed_money, ev_ids, err = _extract_authoritative_money(
        evidence_list, "total_amount"
    )

    if err == "missing":
        return RuleResult(
            rule_name=rule_name,
            status=IntegrityStatus.UNKNOWN,
            explanation="Missing authoritative observed payment amount evidence",
            expected=contract.max_total.model_dump(),
            observed=None,
            evidence_ids=[],
        )

    if err == "conflict":
        return RuleResult(
            rule_name=rule_name,
            status=IntegrityStatus.UNKNOWN,
            explanation="Conflicting amount evidence at highest authority tier",
            expected=contract.max_total.model_dump(),
            observed="CONFLICT",
            evidence_ids=ev_ids,
        )

    if err == "malformed" or observed_money is None:
        return RuleResult(
            rule_name=rule_name,
            status=IntegrityStatus.UNKNOWN,
            explanation="Observed payment amount evidence is malformed or invalid",
            expected=contract.max_total.model_dump(),
            observed=None,
            evidence_ids=ev_ids,
        )

    # 1. Currency Check
    if observed_money.currency != contract.currency:
        return RuleResult(
            rule_name=rule_name,
            status=IntegrityStatus.DRIFT,
            violation=(
                f"CurrencyMismatch: Observed {observed_money.currency} "
                f"does not match authorized {contract.currency}"
            ),
            expected=contract.currency,
            observed=observed_money.currency,
            evidence_ids=ev_ids,
            explanation="Observed transaction currency does not match authorized intent currency",
        )

    # 2. Maximum Total Limit Check (integer minor units)
    if observed_money.amount > contract.max_total.amount:
        overage = observed_money.amount - contract.max_total.amount
        return RuleResult(
            rule_name=rule_name,
            status=IntegrityStatus.DRIFT,
            violation=(
                f"EconomicDrift: Observed amount {observed_money.amount} {observed_money.currency} "
                f"exceeds authorized max_total {contract.max_total.amount} {contract.max_total.currency} "
                f"by {overage} minor units"
            ),
            expected=contract.max_total.model_dump(),
            observed=observed_money.model_dump(),
            evidence_ids=ev_ids,
            explanation="Transaction amount exceeded authorized maximum limit",
        )

    # 3. Valid Economic Integrity
    return RuleResult(
        rule_name=rule_name,
        status=IntegrityStatus.PASS,
        expected=contract.max_total.model_dump(),
        observed=observed_money.model_dump(),
        evidence_ids=ev_ids,
        explanation="Observed amount satisfies authorized maximum limit and currency constraints",
    )
