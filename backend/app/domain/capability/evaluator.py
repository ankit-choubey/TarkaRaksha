"""Authoritative Deterministic Capability Evaluator for TarkaRaksha (I19).

Enforces:
- Deterministic verification of requested commerce operations against merchant capability graph (§11).
- Strict cross-merchant identity defense (§18).
- Fine-grained constraint verification (amount ceiling, discount bps, delivery window, regions, refund window, SKU substitutions).
- Distinction between DECLARED CAPABILITY and CURRENT TRANSACTION FACT (§12).
- Zero reputation score, zero trust scoring (§3, §34).
- Explainable CapabilityEvaluationResult with satisfied and violated constraints.
"""
from datetime import datetime, timezone
import hashlib
import uuid
from typing import Any, Dict, List, Optional

from backend.app.domain.capability.contracts import (
    CapabilityConstraint,
    CapabilityEvaluationResult,
    CapabilityEvaluationStatus,
    CapabilityTransactionContext,
    CapabilityViolation,
    ConstraintType,
    CrossMerchantCapabilityReuseError,
)
from backend.app.domain.capability.graph import MerchantCapabilityGraph


class CapabilityEvaluator:
    """
    Pure deterministic evaluator for merchant capabilities.
    Takes a CapabilityGraph, requested operation, and transaction context,
    and returns a structured, explainable evaluation result.
    """

    @classmethod
    def evaluate(
        cls,
        graph: MerchantCapabilityGraph,
        operation: str,
        context: CapabilityTransactionContext,
        reference_time: Optional[datetime] = None,
    ) -> CapabilityEvaluationResult:
        """
        Deterministically evaluates whether the requested operation is supported,
        constrained, unsupported, or unavailable under the merchant capability graph.
        """
        ref_time = reference_time or datetime.now(timezone.utc)
        op_clean = operation.strip().upper()

        # 1. Cross-Merchant Identity Defense (§18)
        if context.merchant_id != graph.merchant_id:
            raise CrossMerchantCapabilityReuseError(
                f"Cross-merchant capability reuse rejected: transaction requested for merchant '{context.merchant_id}', "
                f"but capability graph belongs to '{graph.merchant_id}'."
            )

        # 2. Capability Lookup
        enabling_caps = graph.find_capabilities_for_operation(op_clean)
        if not enabling_caps:
            eval_id = f"eval_{graph.merchant_id}_{op_clean}_{ref_time.strftime('%Y%m%d%H%M%S')}"
            return CapabilityEvaluationResult(
                evaluation_id=eval_id,
                merchant_id=graph.merchant_id,
                operation=op_clean,
                status=CapabilityEvaluationStatus.UNSUPPORTED,
                reason=f"Operation '{op_clean}' is not supported by merchant '{graph.merchant_id}'.",
                policy_version=graph.policy_version,
                timestamp=ref_time,
            )

        primary_cap = enabling_caps[0]
        cap_available = primary_cap.attributes.get("is_available", True)

        if not cap_available:
            eval_id = f"eval_{graph.merchant_id}_{op_clean}_{ref_time.strftime('%Y%m%d%H%M%S')}"
            return CapabilityEvaluationResult(
                evaluation_id=eval_id,
                merchant_id=graph.merchant_id,
                operation=op_clean,
                capability_id=primary_cap.node_id,
                status=CapabilityEvaluationStatus.UNAVAILABLE,
                reason=f"Capability '{primary_cap.label}' enabling operation '{op_clean}' is currently disabled/unavailable.",
                policy_version=graph.policy_version,
                timestamp=ref_time,
            )

        # 3. Retrieve and Evaluate Constraints
        constraints = graph.get_constraints_for_operation(op_clean)
        satisfied_constraints: List[str] = []
        violations: List[CapabilityViolation] = []

        for const in constraints:
            is_satisfied, violation = cls._evaluate_constraint(const, context)
            if is_satisfied:
                satisfied_constraints.append(const.constraint_id)
            else:
                if violation:
                    violations.append(violation)

        # 4. Gather Supporting Evidence references
        ev_nodes = graph.get_evidence_references(primary_cap.node_id)
        evidence_ids = [n.attributes.get("evidence_id", n.node_id) for n in ev_nodes]

        # 5. Determine Overall Status and Reason
        eval_id = f"eval_{graph.merchant_id}_{op_clean}_{ref_time.strftime('%Y%m%d%H%M%S')}"

        if violations:
            violation_msgs = "; ".join(v.message for v in violations)
            status = CapabilityEvaluationStatus.CONSTRAINED
            reason = (
                f"Operation '{op_clean}' is within declared capability '{primary_cap.label}', "
                f"but violated {len(violations)} constraint(s): {violation_msgs}."
            )
        else:
            status = CapabilityEvaluationStatus.SUPPORTED
            reason = (
                f"Operation '{op_clean}' is fully supported under capability '{primary_cap.label}' "
                f"and satisfies all {len(satisfied_constraints)} checked constraint(s)."
            )

        return CapabilityEvaluationResult(
            evaluation_id=eval_id,
            merchant_id=graph.merchant_id,
            operation=op_clean,
            capability_id=primary_cap.node_id,
            status=status,
            satisfied_constraints=satisfied_constraints,
            violations=violations,
            supporting_evidence_ids=evidence_ids,
            reason=reason,
            policy_version=graph.policy_version,
            timestamp=ref_time,
        )

    @classmethod
    def _evaluate_constraint(
        cls,
        constraint: CapabilityConstraint,
        context: CapabilityTransactionContext,
    ) -> tuple[bool, Optional[CapabilityViolation]]:
        """Evaluates a single constraint against the transaction context."""
        ctype = constraint.constraint_type
        params = constraint.parameters

        # 1. MAX_AMOUNT
        if ctype == ConstraintType.MAX_AMOUNT:
            if context.amount is not None:
                max_paise = params.get("max_amount_paise")
                expected_curr = params.get("currency", "INR")
                if expected_curr and context.amount.currency != expected_curr:
                    return False, CapabilityViolation(
                        constraint_id=constraint.constraint_id,
                        constraint_type=ctype,
                        expected=expected_curr,
                        observed=context.amount.currency,
                        message=f"Currency mismatch: expected {expected_curr}, observed {context.amount.currency}",
                    )
                if max_paise is not None and context.amount.amount > max_paise:
                    return False, CapabilityViolation(
                        constraint_id=constraint.constraint_id,
                        constraint_type=ctype,
                        expected=f"<= {max_paise} paise",
                        observed=f"{context.amount.amount} paise",
                        message=f"Transaction amount {context.amount.amount} paise exceeds maximum allowed {max_paise} paise",
                    )
            return True, None

        # 2. MAX_DISCOUNT_BPS
        if ctype == ConstraintType.MAX_DISCOUNT_BPS:
            if context.requested_discount_bps is not None:
                max_bps = params.get("max_discount_bps", 2000)
                if context.requested_discount_bps > max_bps:
                    return False, CapabilityViolation(
                        constraint_id=constraint.constraint_id,
                        constraint_type=ctype,
                        expected=f"<= {max_bps} bps",
                        observed=f"{context.requested_discount_bps} bps",
                        message=f"Requested discount {context.requested_discount_bps} bps exceeds policy maximum {max_bps} bps",
                    )
            return True, None

        # 3. DELIVERY_DAYS_WINDOW
        if ctype == ConstraintType.DELIVERY_DAYS_WINDOW:
            if context.delivery_days is not None:
                min_days = params.get("min_delivery_days", 1)
                max_days = params.get("max_delivery_days", 7)
                if context.delivery_days < min_days or context.delivery_days > max_days:
                    return False, CapabilityViolation(
                        constraint_id=constraint.constraint_id,
                        constraint_type=ctype,
                        expected=f"[{min_days}, {max_days}] days",
                        observed=f"{context.delivery_days} days",
                        message=f"Delivery timeline {context.delivery_days} days outside merchant window [{min_days}, {max_days}]",
                    )
            return True, None

        # 4. MAX_WINDOW_DAYS (e.g. refund window)
        if ctype == ConstraintType.MAX_WINDOW_DAYS:
            if context.refund_days_since_purchase is not None:
                max_window = params.get("max_window_days", 14)
                if context.refund_days_since_purchase > max_window:
                    return False, CapabilityViolation(
                        constraint_id=constraint.constraint_id,
                        constraint_type=ctype,
                        expected=f"<= {max_window} days",
                        observed=f"{context.refund_days_since_purchase} days",
                        message=f"Refund requested {context.refund_days_since_purchase} days after purchase exceeds {max_window}-day policy limit",
                    )
            return True, None

        # 5. ALLOWED_REGIONS
        if ctype == ConstraintType.ALLOWED_REGIONS:
            if context.destination_region is not None:
                allowed_regions = params.get("allowed_regions", [])
                if allowed_regions and context.destination_region not in allowed_regions:
                    return False, CapabilityViolation(
                        constraint_id=constraint.constraint_id,
                        constraint_type=ctype,
                        expected=allowed_regions,
                        observed=context.destination_region,
                        message=f"Destination region '{context.destination_region}' is not supported by merchant shipping policy",
                    )
            return True, None

        # 6. ALLOWED_SKUS (e.g. substitutions map)
        if ctype == ConstraintType.ALLOWED_SKUS:
            primary_sku = context.parameters.get("primary_sku")
            substitute_sku = context.sku
            if primary_sku and substitute_sku:
                substitutions_map = params.get("substitutions_map", {})
                allowed_list = substitutions_map.get(primary_sku, [])
                if substitute_sku != primary_sku and substitute_sku not in allowed_list:
                    return False, CapabilityViolation(
                        constraint_id=constraint.constraint_id,
                        constraint_type=ctype,
                        expected=allowed_list,
                        observed=substitute_sku,
                        message=f"Proposed substitute SKU '{substitute_sku}' is not pre-authorized for primary SKU '{primary_sku}'",
                    )
            return True, None

        # 7. MAX_QUANTITY
        if ctype == ConstraintType.MAX_QUANTITY:
            if context.quantity is not None:
                max_qty = params.get("max_quantity", 10)
                if context.quantity > max_qty:
                    return False, CapabilityViolation(
                        constraint_id=constraint.constraint_id,
                        constraint_type=ctype,
                        expected=f"<= {max_qty}",
                        observed=context.quantity,
                        message=f"Requested quantity {context.quantity} exceeds maximum allowable order quantity {max_qty}",
                    )
            return True, None

        # 8. ALLOWED_CURRENCIES
        if ctype == ConstraintType.ALLOWED_CURRENCIES:
            if context.amount is not None:
                allowed_currs = params.get("allowed_currencies", ["INR"])
                if context.amount.currency not in allowed_currs:
                    return False, CapabilityViolation(
                        constraint_id=constraint.constraint_id,
                        constraint_type=ctype,
                        expected=allowed_currs,
                        observed=context.amount.currency,
                        message=f"Currency '{context.amount.currency}' is not accepted by merchant",
                    )
            return True, None

        # Custom or unrecognized constraint defaults to satisfied unless explicit condition failed
        return True, None
