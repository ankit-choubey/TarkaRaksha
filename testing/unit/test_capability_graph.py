"""Unit tests for MerchantCapabilityGraph construction, indexing, and validation."""
from datetime import datetime, timezone
import pytest

from backend.app.domain.capability.contracts import (
    CapabilityConstraint,
    CapabilityEdge,
    CapabilityEdgeType,
    CapabilityNode,
    CapabilityNodeType,
    ConstraintType,
    InvalidCapabilityGraphError,
)
from backend.app.domain.capability.graph import MerchantCapabilityGraph
from backend.app.domain.merchant.capabilities import (
    CommerceCapabilityType,
    MerchantCapability,
    MerchantCapabilityDeclaration,
    MerchantPolicyAsCode,
)
from backend.app.domain.models.money import Money


@pytest.fixture
def default_declaration() -> MerchantCapabilityDeclaration:
    return MerchantCapabilityDeclaration.default_reference_declaration("merchant_test_1")


@pytest.fixture
def default_policy() -> MerchantPolicyAsCode:
    return MerchantPolicyAsCode(
        policy_id="pol_test_1",
        merchant_id="merchant_test_1",
        max_order_value=Money(amount=5000000, currency="INR"),
        max_discount_bps=2000,
        allowed_substitutions={"SKU-PRIMARY": ["SKU-SUB-1", "SKU-SUB-2"]},
    )


def test_graph_factory_from_declaration_and_policy(
    default_declaration: MerchantCapabilityDeclaration,
    default_policy: MerchantPolicyAsCode,
):
    """Verify graph builds completely with all nodes, operations, constraints, and edges."""
    ref_time = datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)
    graph = MerchantCapabilityGraph.from_declaration_and_policy(
        merchant_id="merchant_test_1",
        declaration=default_declaration,
        policy=default_policy,
        evidence_refs=["ev_decl_001"],
        reference_time=ref_time,
    )

    assert graph.merchant_id == "merchant_test_1"
    assert graph.policy_version == default_policy.policy_version

    # Check merchant root node
    merch_node = graph.get_node("merch:merchant_test_1")
    assert merch_node is not None
    assert merch_node.node_type == CapabilityNodeType.MERCHANT

    # Check capabilities are present
    caps = graph.get_capabilities()
    assert len(caps) >= 8  # CATALOG, INVENTORY, PRICING, SHIPPING, TAX, ALTERNATIVE_OFFER, REFUND, FULFILLMENT

    # Check operations enabled by SHIPPING
    shipping_ops = graph.get_operations_for_capability("cap:merchant_test_1:SHIPPING")
    op_labels = [op.attributes["operation"] for op in shipping_ops]
    assert "STANDARD_SHIPPING" in op_labels
    assert "EXPRESS_SHIPPING" in op_labels

    # Check reverse lookup: find capabilities for operation
    found_caps = graph.find_capabilities_for_operation("EXPRESS_SHIPPING")
    assert len(found_caps) == 1
    assert found_caps[0].node_id == "cap:merchant_test_1:SHIPPING"

    # Check constraints on PRICING
    pricing_constraints = graph.get_constraints_for_capability("cap:merchant_test_1:PRICING")
    const_names = [c.name for c in pricing_constraints]
    assert "Max Order Value Ceiling" in const_names
    assert "Max Discount Rate" in const_names


def test_graph_validation_detects_missing_merchant_root():
    """Verify validation fails if root merchant node is absent."""
    graph = MerchantCapabilityGraph(
        merchant_id="merchant_missing",
        policy_version="1.0.0",
    )
    with pytest.raises(InvalidCapabilityGraphError, match="missing root merchant node"):
        graph.validate()


def test_graph_validation_detects_dangling_edge():
    """Verify validation fails if an edge references a non-existent node."""
    graph = MerchantCapabilityGraph(
        merchant_id="merchant_1",
        policy_version="1.0.0",
    )
    graph.add_node(CapabilityNode(node_id="merch:merchant_1", node_type=CapabilityNodeType.MERCHANT, label="M1"))
    graph.add_node(CapabilityNode(node_id="cap:merchant_1:CATALOG", node_type=CapabilityNodeType.CAPABILITY, label="Cat"))

    # Attempt to add edge to non-existent node
    with pytest.raises(InvalidCapabilityGraphError, match="unknown to_node"):
        graph.add_edge(
            CapabilityEdge(
                edge_id="e_dangle",
                from_node_id="cap:merchant_1:CATALOG",
                to_node_id="op:NON_EXISTENT",
                edge_type=CapabilityEdgeType.ENABLES,
            )
        )


def test_graph_validation_detects_merchant_mismatch():
    """Verify validation fails if a capability node belongs to a different merchant."""
    graph = MerchantCapabilityGraph(
        merchant_id="merchant_alpha",
        policy_version="1.0.0",
    )
    graph.add_node(CapabilityNode(node_id="merch:merchant_alpha", node_type=CapabilityNodeType.MERCHANT, label="Alpha"))
    # Add capability with merchant_id = merchant_beta
    graph.add_node(
        CapabilityNode(
            node_id="cap:merchant_alpha:CATALOG",
            node_type=CapabilityNodeType.CAPABILITY,
            label="Catalog",
            attributes={"merchant_id": "merchant_beta"},
        )
    )

    with pytest.raises(InvalidCapabilityGraphError, match="does not match graph merchant"):
        graph.validate()


def test_graph_snapshot_export_and_reconstruction(
    default_declaration: MerchantCapabilityDeclaration,
    default_policy: MerchantPolicyAsCode,
):
    """Verify snapshot export and exact reconstruction from snapshot."""
    original_graph = MerchantCapabilityGraph.from_declaration_and_policy(
        merchant_id="merchant_test_1",
        declaration=default_declaration,
        policy=default_policy,
    )
    snapshot = original_graph.export_snapshot()

    reconstructed_graph = MerchantCapabilityGraph.from_snapshot(
        snapshot=snapshot,
        constraints=original_graph.constraints,
    )

    assert reconstructed_graph.merchant_id == original_graph.merchant_id
    assert reconstructed_graph.policy_version == original_graph.policy_version
    assert len(reconstructed_graph.nodes) == len(original_graph.nodes)
    assert len(reconstructed_graph.edges) == len(original_graph.edges)

    # Exporting snapshot from reconstructed graph produces identical hash
    new_snapshot = reconstructed_graph.export_snapshot()
    assert new_snapshot.graph_hash == snapshot.graph_hash
