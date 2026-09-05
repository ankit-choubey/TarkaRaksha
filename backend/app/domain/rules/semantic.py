"""
Semantic Integrity Check for TarkaRaksha (T04).
Compares observed execution details (SKUs, quantities, items) against authorized IntentContract.

Invariants:
- Authorized SKU executed -> PASS.
- Unapproved SKU executed -> DRIFT.
- Explicitly allowed substitute executed -> PASS.
- Quantity mismatch -> DRIFT.
- Missing required execution evidence -> UNKNOWN.
- No commercial similarity guessing; only explicit contract permissions authorized.
"""
from typing import Any, Dict, List, Optional
from backend.app.domain.models import (
    Evidence,
    IntegrityStatus,
    IntentContract,
)
from .base import RuleResult


def check_semantic(
    contract: IntentContract,
    evidence_list: List[Evidence],
) -> RuleResult:
    """
    Deterministically evaluates semantic integrity of executed items.
    Checks:
    1. Observed item SKUs match authorized items or allowed_substitutions.
    2. Observed item quantities match authorized quantities.
    3. Missing semantic evidence yields UNKNOWN.
    """
    rule_name = "SemanticIntegrityRule"

    matching = [e for e in evidence_list if e.field_name == "executed_items"]
    if not matching:
        return RuleResult(
            rule_name=rule_name,
            status=IntegrityStatus.UNKNOWN,
            explanation="Missing authoritative executed item details evidence",
            expected=[{"sku": item.sku, "quantity": item.quantity} for item in contract.items],
            observed=None,
            evidence_ids=[],
        )

    # Sort matching by authority_rank descending, then observed_at descending
    sorted_ev = sorted(
        matching,
        key=lambda e: (e.authority_rank, e.observed_at.isoformat(), e.evidence_id),
        reverse=True,
    )
    top_ev = sorted_ev[0]
    executed_items_data = top_ev.field_value

    if not isinstance(executed_items_data, list):
        return RuleResult(
            rule_name=rule_name,
            status=IntegrityStatus.UNKNOWN,
            explanation="Executed items evidence is malformed (expected list of item dicts)",
            expected=[item.sku for item in contract.items],
            observed=str(type(executed_items_data)),
            evidence_ids=[top_ev.evidence_id],
        )

    # Map authorized items by SKU
    authorized_skus = {item.sku: item for item in contract.items}
    allowed_substitutions = set(contract.allowed_substitutions)

    violations = []
    observed_summary = []

    # Map observed items by SKU
    observed_sku_counts: Dict[str, int] = {}
    for item_data in executed_items_data:
        if not isinstance(item_data, dict) or "sku" not in item_data:
            return RuleResult(
                rule_name=rule_name,
                status=IntegrityStatus.UNKNOWN,
                explanation="Observed item missing required 'sku' attribute",
                evidence_ids=[top_ev.evidence_id],
            )
        sku = str(item_data["sku"])
        qty = item_data.get("quantity", 1)
        if isinstance(qty, bool) or not isinstance(qty, int) or qty <= 0:
            return RuleResult(
                rule_name=rule_name,
                status=IntegrityStatus.UNKNOWN,
                explanation=f"Observed item '{sku}' has invalid quantity attribute",
                evidence_ids=[top_ev.evidence_id],
            )
        observed_sku_counts[sku] = observed_sku_counts.get(sku, 0) + qty
        observed_summary.append({"sku": sku, "quantity": qty})

    # Validate each observed SKU and quantity
    # For substitution: if an authorized item's SKU is replaced by an allowed substitute,
    # it is considered valid if the quantity aligns with the contract.
    for sku, qty in observed_sku_counts.items():
        if sku in authorized_skus:
            auth_item = authorized_skus[sku]
            if qty != auth_item.quantity:
                violations.append(
                    f"QuantityMismatch: SKU '{sku}' authorized quantity is {auth_item.quantity}, but observed {qty}"
                )
        elif sku in allowed_substitutions:
            # Explicitly allowed substitution: check if it replaces an authorized item
            # Single-item or matching item quantity check
            matched = False
            for auth_item in contract.items:
                if qty == auth_item.quantity:
                    matched = True
                    break
            if not matched:
                violations.append(
                    f"SubstitutionQuantityMismatch: Allowed substitute '{sku}' quantity {qty} does not match any authorized item quantity"
                )
        else:
            violations.append(
                f"UnauthorizedSKU: Observed SKU '{sku}' is neither an authorized item nor an allowed substitution"
            )

    # Check for missing items if partial execution is not authorized
    if not contract.allow_partial:
        # Check if every authorized item (or an allowed substitute) was present
        for auth_sku, auth_item in authorized_skus.items():
            if auth_sku not in observed_sku_counts:
                # Check if any allowed substitute covered this
                covered = any(
                    sub in observed_sku_counts and observed_sku_counts[sub] == auth_item.quantity
                    for sub in allowed_substitutions
                )
                if not covered:
                    violations.append(
                        f"MissingAuthorizedItem: Authorized SKU '{auth_sku}' was not executed"
                    )

    if violations:
        return RuleResult(
            rule_name=rule_name,
            status=IntegrityStatus.DRIFT,
            violation="; ".join(violations),
            expected=[{"sku": item.sku, "quantity": item.quantity} for item in contract.items],
            observed=observed_summary,
            evidence_ids=[top_ev.evidence_id],
            explanation="Executed items diverge semantically from authorized intent",
        )

    return RuleResult(
        rule_name=rule_name,
        status=IntegrityStatus.PASS,
        expected=[{"sku": item.sku, "quantity": item.quantity} for item in contract.items],
        observed=observed_summary,
        evidence_ids=[top_ev.evidence_id],
        explanation="Executed items and quantities strictly adhere to authorized intent and substitution rules",
    )
