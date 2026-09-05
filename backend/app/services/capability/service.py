"""Authoritative Merchant Capability Service for TarkaRaksha (I19).

Manages:
- Registry of active, deterministic merchant capability graphs (§23).
- Lifecycle and snapshot registration from I4 MerchantCatalogService.
- Transaction-scoped capability evaluations (§11, §18).
- Replanning advice generation for I7 Bounded Negotiation (§20).
- Replay snapshot reconstruction (§26).
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.app.domain.capability.contracts import (
    CapabilityConstraint,
    CapabilityConstraintError,
    CapabilityEvaluationResult,
    CapabilityEvaluationStatus,
    CapabilityGraphSnapshot,
    CapabilityTransactionContext,
    CrossMerchantCapabilityReuseError,
)
from backend.app.domain.capability.evaluator import CapabilityEvaluator
from backend.app.domain.capability.graph import MerchantCapabilityGraph
from backend.app.domain.merchant.capabilities import MerchantCapabilityDeclaration, MerchantPolicyAsCode
from backend.app.services.merchant.catalog_service import MerchantCatalogService


class MerchantCapabilityService:
    """
    Control-plane service managing merchant capability graphs and deterministic evaluations.
    """

    def __init__(self):
        # Keyed by merchant_id
        self._graphs: Dict[str, MerchantCapabilityGraph] = {}
        # Keyed by (merchant_id, graph_version)
        self._historical_snapshots: Dict[tuple[str, str], CapabilityGraphSnapshot] = {}

    def register_graph(self, graph: MerchantCapabilityGraph) -> CapabilityGraphSnapshot:
        """Registers a merchant capability graph and records its snapshot."""
        graph.validate()
        snapshot = graph.export_snapshot()
        self._graphs[graph.merchant_id] = graph
        self._historical_snapshots[(graph.merchant_id, graph.graph_version)] = snapshot
        return snapshot

    def register_from_merchant_catalog(
        self,
        catalog_service: MerchantCatalogService,
        evidence_refs: Optional[List[str]] = None,
        graph_version: str = "1.0.0",
        reference_time: Optional[datetime] = None,
    ) -> MerchantCapabilityGraph:
        """
        Builds, registers, and returns a capability graph directly from a MerchantCatalogService instance.
        """
        graph = MerchantCapabilityGraph.from_declaration_and_policy(
            merchant_id=catalog_service.merchant_id,
            declaration=catalog_service.capabilities,
            policy=catalog_service.policy,
            evidence_refs=evidence_refs,
            graph_version=graph_version,
            reference_time=reference_time,
        )
        self.register_graph(graph)
        return graph

    def get_graph(self, merchant_id: str) -> Optional[MerchantCapabilityGraph]:
        """Retrieves the active capability graph for a merchant."""
        return self._graphs.get(merchant_id.strip())

    def get_snapshot(self, merchant_id: str, graph_version: Optional[str] = None) -> Optional[CapabilityGraphSnapshot]:
        """Retrieves a graph snapshot, optionally for a specific historical version."""
        m_id = merchant_id.strip()
        if graph_version:
            return self._historical_snapshots.get((m_id, graph_version.strip()))
        graph = self._graphs.get(m_id)
        if graph:
            return graph.export_snapshot()
        return None

    def evaluate_operation(
        self,
        merchant_id: str,
        operation: str,
        context: CapabilityTransactionContext,
        reference_time: Optional[datetime] = None,
        historical_snapshot: Optional[CapabilityGraphSnapshot] = None,
    ) -> CapabilityEvaluationResult:
        """
        Deterministically evaluates an operation against the merchant's capability graph.
        If historical_snapshot is provided (e.g. during T13 replay), evaluates against
        that historical snapshot rather than the current live runtime graph (§26).
        """
        ref_time = reference_time or datetime.now(timezone.utc)
        m_id = merchant_id.strip()

        # Replay mode: use historical snapshot if supplied
        if historical_snapshot is not None:
            if historical_snapshot.merchant_id != m_id:
                raise CrossMerchantCapabilityReuseError(
                    f"Historical snapshot merchant '{historical_snapshot.merchant_id}' does not match requested merchant '{m_id}'."
                )
            graph = MerchantCapabilityGraph.from_snapshot(historical_snapshot)
        else:
            graph = self._graphs.get(m_id)
            if not graph:
                # Unknown merchant in registry -> UNSUPPORTED
                return CapabilityEvaluationResult(
                    evaluation_id=f"eval_unk_{m_id}_{operation}_{ref_time.strftime('%Y%m%d%H%M%S')}",
                    merchant_id=m_id,
                    operation=operation.upper(),
                    status=CapabilityEvaluationStatus.UNSUPPORTED,
                    reason=f"No capability graph registered for merchant '{m_id}'.",
                    policy_version="unknown",
                    timestamp=ref_time,
                )

        return CapabilityEvaluator.evaluate(
            graph=graph,
            operation=operation,
            context=context,
            reference_time=ref_time,
        )

    def generate_replanning_advice(
        self,
        evaluation: CapabilityEvaluationResult,
    ) -> Optional[Dict[str, Any]]:
        """
        Translates a CONSTRAINED evaluation result into structured replanning guidance
        for Buyer Agent and I7 Bounded Negotiation (§20).
        """
        if evaluation.status != CapabilityEvaluationStatus.CONSTRAINED or not evaluation.violations:
            return None

        advice: Dict[str, Any] = {
            "operation": evaluation.operation,
            "merchant_id": evaluation.merchant_id,
            "violations_count": len(evaluation.violations),
            "suggested_actions": [],
        }

        for v in evaluation.violations:
            if v.constraint_type.value == "ALLOWED_REGIONS":
                advice["suggested_actions"].append({
                    "constraint": v.constraint_id,
                    "action": "CHANGE_SHIPPING_METHOD",
                    "suggestion": "Select standard shipping or provide an in-region delivery address.",
                    "allowed_regions": v.expected,
                })
            elif v.constraint_type.value == "MAX_AMOUNT":
                advice["suggested_actions"].append({
                    "constraint": v.constraint_id,
                    "action": "REDUCE_ORDER_TOTAL",
                    "suggestion": f"Reduce item quantities or split transaction to stay within {v.expected}.",
                })
            elif v.constraint_type.value == "MAX_DISCOUNT_BPS":
                advice["suggested_actions"].append({
                    "constraint": v.constraint_id,
                    "action": "REDUCE_REQUESTED_DISCOUNT",
                    "suggestion": f"Adjust requested discount to policy ceiling {v.expected}.",
                })
            elif v.constraint_type.value == "ALLOWED_SKUS":
                advice["suggested_actions"].append({
                    "constraint": v.constraint_id,
                    "action": "USE_AUTHORIZED_SUBSTITUTE",
                    "suggestion": f"Select from pre-authorized alternative SKUs: {v.expected}.",
                    "authorized_skus": v.expected,
                })
            elif v.constraint_type.value == "MAX_QUANTITY":
                advice["suggested_actions"].append({
                    "constraint": v.constraint_id,
                    "action": "REDUCE_QUANTITY",
                    "suggestion": f"Cap requested quantity to maximum allowed {v.expected}.",
                })
            else:
                advice["suggested_actions"].append({
                    "constraint": v.constraint_id,
                    "action": "ADJUST_PROPOSAL",
                    "suggestion": v.message,
                })

        return advice
