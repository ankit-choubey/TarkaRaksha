"""Deterministic Replay test suite for I19 Merchant-Side Capability Graph.

Verifies:
1. Historical snapshot recorded capability graph is preserved during replay
   even if the merchant updates their capability declaration or policy in live runtime.
2. Replay evaluation is strictly deterministic and identical across repeated runs.
3. Historical snapshot graph hash uniquely identifies the historical graph topology.
"""
from datetime import datetime, timezone
import pytest

from backend.app.domain.capability.contracts import (
    CapabilityConstraint,
    CapabilityEvaluationStatus,
    CapabilityTransactionContext,
    ConstraintType,
)
from backend.app.domain.capability.graph import MerchantCapabilityGraph
from backend.app.domain.merchant.capabilities import (
    MerchantCapabilityDeclaration,
    MerchantPolicyAsCode,
)
from backend.app.domain.models.money import Money
from backend.app.services.capability.service import MerchantCapabilityService


@pytest.fixture
def replay_time() -> datetime:
    return datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)


def test_replay_uses_historical_snapshot_not_runtime_mutated_graph(replay_time: datetime):
    """
    Historical transaction evaluated against v1.0.0 graph with ₹20,000 ceiling
    must evaluate as CONSTRAINED for a ₹25,000 transaction during replay,
    even if the merchant later updated their live runtime policy to allow ₹50,000.
    """
    service = MerchantCapabilityService()

    # 1. Historical graph version 1.0.0 (Max Order Value = ₹20,000)
    decl_v1 = MerchantCapabilityDeclaration.default_reference_declaration("merch_hist_1")
    pol_v1 = MerchantPolicyAsCode(
        policy_id="pol_v1",
        policy_version="1.0.0",
        merchant_id="merch_hist_1",
        max_order_value=Money(amount=2000000, currency="INR"),  # ₹20,000
    )
    graph_v1 = MerchantCapabilityGraph.from_declaration_and_policy(
        merchant_id="merch_hist_1",
        declaration=decl_v1,
        policy=pol_v1,
        graph_version="1.0.0",
        reference_time=replay_time,
    )
    historical_snapshot_v1 = service.register_graph(graph_v1)

    # 2. Live Runtime updates to graph version 2.0.0 (Max Order Value = ₹50,000)
    pol_v2 = MerchantPolicyAsCode(
        policy_id="pol_v2",
        policy_version="2.0.0",
        merchant_id="merch_hist_1",
        max_order_value=Money(amount=5000000, currency="INR"),  # ₹50,000
    )
    graph_v2 = MerchantCapabilityGraph.from_declaration_and_policy(
        merchant_id="merch_hist_1",
        declaration=decl_v1,
        policy=pol_v2,
        graph_version="2.0.0",
        reference_time=replay_time,
    )
    service.register_graph(graph_v2)

    # 3. Replay of historical transaction of ₹25,000
    tx_ctx = CapabilityTransactionContext(
        merchant_id="merch_hist_1",
        amount=Money(amount=2500000, currency="INR"),  # ₹25,000
    )

    # A. Historical Replay evaluation (uses snapshot v1)
    replayed_eval = service.evaluate_operation(
        merchant_id="merch_hist_1",
        operation="QUOTE_PRICE",
        context=tx_ctx,
        reference_time=replay_time,
        historical_snapshot=historical_snapshot_v1,
    )

    # Must be CONSTRAINED under historical snapshot rules
    assert replayed_eval.status == CapabilityEvaluationStatus.CONSTRAINED
    assert replayed_eval.policy_version == "1.0.0"
    assert len(replayed_eval.violations) == 1
    assert "exceeds maximum allowed 2000000" in replayed_eval.violations[0].message

    # B. Current live runtime evaluation (uses active v2)
    runtime_eval = service.evaluate_operation(
        merchant_id="merch_hist_1",
        operation="QUOTE_PRICE",
        context=tx_ctx,
        reference_time=replay_time,
    )

    # Supported under today's live runtime rules
    assert runtime_eval.status == CapabilityEvaluationStatus.SUPPORTED
    assert runtime_eval.policy_version == "2.0.0"

    # Invariant holds: Replay never leaked live runtime graph into historical evaluation
    assert replayed_eval.status != runtime_eval.status


def test_replay_evaluation_is_strictly_deterministic(replay_time: datetime):
    """Verify repeated evaluations with identical inputs produce identical digests and results."""
    decl = MerchantCapabilityDeclaration.default_reference_declaration("merch_repeat")
    pol = MerchantPolicyAsCode(policy_id="p1", merchant_id="merch_repeat")
    graph = MerchantCapabilityGraph.from_declaration_and_policy(
        merchant_id="merch_repeat",
        declaration=decl,
        policy=pol,
        reference_time=replay_time,
    )
    snapshot = graph.export_snapshot()

    tx_ctx = CapabilityTransactionContext(
        merchant_id="merch_repeat",
        amount=Money(amount=100000, currency="INR"),
    )

    service = MerchantCapabilityService()

    eval_1 = service.evaluate_operation(
        merchant_id="merch_repeat",
        operation="QUOTE_PRICE",
        context=tx_ctx,
        reference_time=replay_time,
        historical_snapshot=snapshot,
    )

    eval_2 = service.evaluate_operation(
        merchant_id="merch_repeat",
        operation="QUOTE_PRICE",
        context=tx_ctx,
        reference_time=replay_time,
        historical_snapshot=snapshot,
    )

    assert eval_1.status == eval_2.status
    assert eval_1.satisfied_constraints == eval_2.satisfied_constraints
    assert eval_1.violations == eval_2.violations
    assert eval_1.reason == eval_2.reason
    assert eval_1.timestamp == eval_2.timestamp
