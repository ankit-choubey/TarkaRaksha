"""Unit tests for I19 Merchant-Side Capability Graph domain contracts."""
from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from backend.app.domain.capability.contracts import (
    CapabilityConstraint,
    CapabilityEdge,
    CapabilityEdgeType,
    CapabilityEvaluationResult,
    CapabilityEvaluationStatus,
    CapabilityGraphSnapshot,
    CapabilityNode,
    CapabilityNodeType,
    CapabilityTransactionContext,
    CapabilityViolation,
    ConstraintType,
    CrossMerchantCapabilityReuseError,
    InvalidCapabilityGraphError,
    compute_canonical_graph_hash,
)
from backend.app.domain.models.money import Money


def test_capability_node_types_and_edge_types():
    """Verify enum invariants for node and edge types."""
    assert CapabilityNodeType.MERCHANT == "MERCHANT"
    assert CapabilityNodeType.CAPABILITY == "CAPABILITY"
    assert CapabilityNodeType.OPERATION == "OPERATION"
    assert CapabilityNodeType.CONSTRAINT == "CONSTRAINT"
    assert CapabilityNodeType.POLICY == "POLICY"
    assert CapabilityNodeType.EVIDENCE == "EVIDENCE"

    assert CapabilityEdgeType.OFFERS_CAPABILITY == "OFFERS_CAPABILITY"
    assert CapabilityEdgeType.ENABLES == "ENABLES"
    assert CapabilityEdgeType.CONSTRAINED_BY == "CONSTRAINED_BY"
    assert CapabilityEdgeType.GOVERNED_BY == "GOVERNED_BY"
    assert CapabilityEdgeType.SUPPORTED_BY == "SUPPORTED_BY"
    assert CapabilityEdgeType.REQUIRES == "REQUIRES"


def test_capability_evaluation_statuses():
    """Verify 5-way evaluation status outcomes."""
    assert CapabilityEvaluationStatus.SUPPORTED == "SUPPORTED"
    assert CapabilityEvaluationStatus.CONSTRAINED == "CONSTRAINED"
    assert CapabilityEvaluationStatus.UNSUPPORTED == "UNSUPPORTED"
    assert CapabilityEvaluationStatus.UNAVAILABLE == "UNAVAILABLE"
    assert CapabilityEvaluationStatus.UNKNOWN == "UNKNOWN"


def test_capability_node_immutability():
    """Verify CapabilityNode is frozen and rejects mutation."""
    node = CapabilityNode(
        node_id="merch:store_1",
        node_type=CapabilityNodeType.MERCHANT,
        label="Store 1",
        attributes={"country": "IN"},
    )
    with pytest.raises(ValidationError):
        node.label = "Store 2"


def test_capability_node_empty_id_rejected():
    """Verify empty node_id is rejected."""
    with pytest.raises(ValidationError):
        CapabilityNode(
            node_id="   ",
            node_type=CapabilityNodeType.MERCHANT,
            label="Store",
        )


def test_capability_edge_immutability():
    """Verify CapabilityEdge is frozen and validates non-empty endpoints."""
    edge = CapabilityEdge(
        edge_id="e1",
        from_node_id="n1",
        to_node_id="n2",
        edge_type=CapabilityEdgeType.ENABLES,
    )
    with pytest.raises(ValidationError):
        edge.to_node_id = "n3"

    with pytest.raises(ValidationError):
        CapabilityEdge(
            edge_id="e2",
            from_node_id="   ",
            to_node_id="n2",
            edge_type=CapabilityEdgeType.ENABLES,
        )


def test_canonical_graph_hash_determinism():
    """Verify deterministic SHA-256 hash regardless of collection insertion order."""
    n1 = CapabilityNode(node_id="n1", node_type=CapabilityNodeType.MERCHANT, label="N1")
    n2 = CapabilityNode(node_id="n2", node_type=CapabilityNodeType.CAPABILITY, label="N2")
    e1 = CapabilityEdge(edge_id="e1", from_node_id="n1", to_node_id="n2", edge_type=CapabilityEdgeType.OFFERS_CAPABILITY)

    hash_1 = compute_canonical_graph_hash(
        merchant_id="m1",
        graph_version="1.0.0",
        policy_version="p1",
        nodes=[n1, n2],
        edges=[e1],
    )

    # Reversed node list order must produce the identical hash
    hash_2 = compute_canonical_graph_hash(
        merchant_id="m1",
        graph_version="1.0.0",
        policy_version="p1",
        nodes=[n2, n1],
        edges=[e1],
    )

    assert hash_1 == hash_2
    assert len(hash_1) == 64


def test_snapshot_schema_and_validation():
    """Verify CapabilityGraphSnapshot creation and field validation."""
    n1 = CapabilityNode(node_id="merch:m1", node_type=CapabilityNodeType.MERCHANT, label="M1")
    snapshot = CapabilityGraphSnapshot(
        merchant_id="m1",
        graph_version="1.0.0",
        policy_version="pol-1",
        nodes=[n1],
        edges=[],
        graph_hash="a" * 64,
        created_at=datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc),
    )
    assert snapshot.merchant_id == "m1"
    assert snapshot.graph_version == "1.0.0"


def test_transaction_context_merchant_id_mandatory():
    """Verify CapabilityTransactionContext requires merchant_id."""
    with pytest.raises(ValidationError):
        CapabilityTransactionContext(merchant_id="   ")
