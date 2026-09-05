"""Unit tests for CapabilityEvaluator deterministic evaluation and constraint verification."""
from datetime import datetime, timezone
import pytest

from backend.app.domain.capability.contracts import (
    CapabilityConstraint,
    CapabilityEvaluationStatus,
    CapabilityTransactionContext,
    ConstraintType,
    CrossMerchantCapabilityReuseError,
)
from backend.app.domain.capability.evaluator import CapabilityEvaluator
from backend.app.domain.capability.graph import MerchantCapabilityGraph
from backend.app.domain.merchant.capabilities import (
    CommerceCapabilityType,
    MerchantCapability,
    MerchantCapabilityDeclaration,
    MerchantPolicyAsCode,
)
from backend.app.domain.models.money import Money


@pytest.fixture
def test_graph() -> MerchantCapabilityGraph:
    declaration = MerchantCapabilityDeclaration.default_reference_declaration("merch_eval_1")
    policy = MerchantPolicyAsCode(
        policy_id="pol_eval_1",
        merchant_id="merch_eval_1",
        max_order_value=Money(amount=5000000, currency="INR"),  # ₹50,000 max
        max_discount_bps=1500,  # 15.00% max discount
        allowed_substitutions={"SKU-BASE": ["SKU-ALT-1", "SKU-ALT-2"]},
        min_delivery_days=1,
        max_delivery_days=5,
    )
    graph = MerchantCapabilityGraph.from_declaration_and_policy(
        merchant_id="merch_eval_1",
        declaration=declaration,
        policy=policy,
        evidence_refs=["ev_pricing_001"],
    )

    # Add custom regional constraint for EXPRESS_SHIPPING
    c_region = CapabilityConstraint(
        constraint_id="const:merch_eval_1:express_regions",
        name="Express Shipping Allowed Regions",
        constraint_type=ConstraintType.ALLOWED_REGIONS,
        parameters={"allowed_regions": ["IN-DL", "IN-KA", "IN-MH"]},
        description="Express shipping available only in Delhi, Karnataka, and Maharashtra",
    )
    graph.add_constraint(c_region)
    return graph


def test_evaluator_supported_operation(test_graph: MerchantCapabilityGraph):
    """Verify standard supported operation returns SUPPORTED."""
    ctx = CapabilityTransactionContext(
        merchant_id="merch_eval_1",
        amount=Money(amount=200000, currency="INR"),  # ₹2,000
        requested_discount_bps=1000,  # 10%
    )
    res = CapabilityEvaluator.evaluate(
        graph=test_graph,
        operation="QUOTE_PRICE",
        context=ctx,
    )

    assert res.status == CapabilityEvaluationStatus.SUPPORTED
    assert res.merchant_id == "merch_eval_1"
    assert res.operation == "QUOTE_PRICE"
    assert len(res.violations) == 0
    assert len(res.satisfied_constraints) >= 2


def test_evaluator_unsupported_operation(test_graph: MerchantCapabilityGraph):
    """Verify non-existent operation returns UNSUPPORTED."""
    ctx = CapabilityTransactionContext(merchant_id="merch_eval_1")
    res = CapabilityEvaluator.evaluate(
        graph=test_graph,
        operation="INTERNATIONAL_AIR_FREIGHT",
        context=ctx,
    )

    assert res.status == CapabilityEvaluationStatus.UNSUPPORTED
    assert "not supported by merchant" in res.reason


def test_evaluator_amount_ceiling_constrained(test_graph: MerchantCapabilityGraph):
    """Verify amount exceeding policy ceiling returns CONSTRAINED with violation detail."""
    ctx = CapabilityTransactionContext(
        merchant_id="merch_eval_1",
        amount=Money(amount=6000000, currency="INR"),  # ₹60,000 (exceeds ₹50,000 ceiling)
    )
    res = CapabilityEvaluator.evaluate(
        graph=test_graph,
        operation="QUOTE_PRICE",
        context=ctx,
    )

    assert res.status == CapabilityEvaluationStatus.CONSTRAINED
    assert len(res.violations) == 1
    assert res.violations[0].constraint_type == ConstraintType.MAX_AMOUNT
    assert "exceeds maximum allowed 5000000" in res.violations[0].message


def test_evaluator_discount_exceeded_constrained(test_graph: MerchantCapabilityGraph):
    """Verify discount exceeding policy ceiling returns CONSTRAINED."""
    ctx = CapabilityTransactionContext(
        merchant_id="merch_eval_1",
        amount=Money(amount=100000, currency="INR"),
        requested_discount_bps=2500,  # 25% (exceeds 15% max)
    )
    res = CapabilityEvaluator.evaluate(
        graph=test_graph,
        operation="APPLY_DISCOUNT",
        context=ctx,
    )

    assert res.status == CapabilityEvaluationStatus.CONSTRAINED
    assert len(res.violations) == 1
    assert res.violations[0].constraint_type == ConstraintType.MAX_DISCOUNT_BPS


def test_evaluator_regional_constraint_violation(test_graph: MerchantCapabilityGraph):
    """Verify delivery destination outside allowed regions returns CONSTRAINED."""
    # Link express_regions constraint to EXPRESS_SHIPPING operation node
    from backend.app.domain.capability.contracts import CapabilityEdge, CapabilityEdgeType, CapabilityNode, CapabilityNodeType
    test_graph.add_node(
        CapabilityNode(
            node_id="const:merch_eval_1:express_regions",
            node_type=CapabilityNodeType.CONSTRAINT,
            label="Express Regions",
            attributes={"constraint_id": "const:merch_eval_1:express_regions"},
        )
    )
    test_graph.add_edge(
        CapabilityEdge(
            edge_id="edge:op:EXPRESS_SHIPPING->constrained_by->const:express_regions",
            from_node_id="op:EXPRESS_SHIPPING",
            to_node_id="const:merch_eval_1:express_regions",
            edge_type=CapabilityEdgeType.CONSTRAINED_BY,
        )
    )

    # Test destination in unsupported region "IN-KL"
    ctx = CapabilityTransactionContext(
        merchant_id="merch_eval_1",
        destination_region="IN-KL",
    )
    res = CapabilityEvaluator.evaluate(
        graph=test_graph,
        operation="EXPRESS_SHIPPING",
        context=ctx,
    )

    assert res.status == CapabilityEvaluationStatus.CONSTRAINED
    assert len(res.violations) == 1
    assert res.violations[0].constraint_type == ConstraintType.ALLOWED_REGIONS
    assert "Destination region 'IN-KL' is not supported" in res.violations[0].message

    # Test destination in supported region "IN-DL"
    ctx_valid = CapabilityTransactionContext(
        merchant_id="merch_eval_1",
        destination_region="IN-DL",
    )
    res_valid = CapabilityEvaluator.evaluate(
        graph=test_graph,
        operation="EXPRESS_SHIPPING",
        context=ctx_valid,
    )
    assert res_valid.status == CapabilityEvaluationStatus.SUPPORTED


def test_evaluator_unauthorized_sku_substitution(test_graph: MerchantCapabilityGraph):
    """Verify unauthorized SKU substitution returns CONSTRAINED."""
    ctx = CapabilityTransactionContext(
        merchant_id="merch_eval_1",
        sku="SKU-UNAUTHORIZED-99",
        parameters={"primary_sku": "SKU-BASE"},
    )
    res = CapabilityEvaluator.evaluate(
        graph=test_graph,
        operation="SUBSTITUTE_SKU",
        context=ctx,
    )

    assert res.status == CapabilityEvaluationStatus.CONSTRAINED
    assert len(res.violations) == 1
    assert res.violations[0].constraint_type == ConstraintType.ALLOWED_SKUS
    assert "is not pre-authorized" in res.violations[0].message


def test_evaluator_cross_merchant_reuse_rejected(test_graph: MerchantCapabilityGraph):
    """Verify cross-merchant capability application raises CrossMerchantCapabilityReuseError."""
    ctx = CapabilityTransactionContext(
        merchant_id="rogue_merchant_99",
    )
    with pytest.raises(CrossMerchantCapabilityReuseError, match="Cross-merchant capability reuse rejected"):
        CapabilityEvaluator.evaluate(
            graph=test_graph,
            operation="QUOTE_PRICE",
            context=ctx,
        )
