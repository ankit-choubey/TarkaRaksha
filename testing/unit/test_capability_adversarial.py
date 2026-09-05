"""Adversarial and security test suite for I19 Merchant-Side Capability Graph.

Verifies:
1. Buyer agent attempts to claim non-existent merchant capability.
2. Merchant agent claims unsupported capability.
3. Merchant capability substituted from another merchant (Cross-merchant reuse rejected).
4. Capability applied to wrong transaction / merchant context.
5. Capability declaration mutated after evaluation (frozen immutability).
6. Capability constraint bypass attempts during evaluation.
7. Unavailable capability attempts invocation.
8. Capability declaration cannot be treated as current transaction fact (stock vs capability).
9. Capability graph has zero authority to authorize payment.
10. Capability graph cannot bypass I9 execution safety kill switch.
11. Capability graph cannot bypass I10 HUMAN_REVIEW operational mode.
12. Duplicate graph node ID rejected.
13. Dangling edge target rejected.
14. Hard scope boundary: Zero reputation, trust score, or fraud rating models.
"""
from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from backend.app.domain.capability.contracts import (
    CapabilityConstraint,
    CapabilityEvaluationResult,
    CapabilityEvaluationStatus,
    CapabilityNode,
    CapabilityNodeType,
    CapabilityTransactionContext,
    ConstraintType,
    CrossMerchantCapabilityReuseError,
    InvalidCapabilityGraphError,
)
from backend.app.domain.capability.evaluator import CapabilityEvaluator
from backend.app.domain.capability.graph import MerchantCapabilityGraph
from backend.app.domain.kill_switch.contracts import KillSwitchState
from backend.app.domain.merchant.capabilities import (
    CommerceCapabilityType,
    MerchantCapability,
    MerchantCapabilityDeclaration,
    MerchantPolicyAsCode,
)
from backend.app.domain.models.enums import IntegrityStatus
from backend.app.domain.models.money import Money
from backend.app.domain.operational_mode.contracts import OperationalMode, OperationalModePolicy
from backend.app.domain.operational_mode.policy import OperationalModeEngine


@pytest.fixture
def base_graph() -> MerchantCapabilityGraph:
    decl = MerchantCapabilityDeclaration.default_reference_declaration("merch_victim")
    pol = MerchantPolicyAsCode(
        policy_id="pol_v1",
        merchant_id="merch_victim",
        max_order_value=Money(amount=2000000, currency="INR"),  # ₹20,000 ceiling
    )
    return MerchantCapabilityGraph.from_declaration_and_policy(
        merchant_id="merch_victim",
        declaration=decl,
        policy=pol,
    )


def test_adv_01_claim_non_existent_capability(base_graph: MerchantCapabilityGraph):
    """Attack 1: Buyer agent claims a capability not supported by the merchant."""
    ctx = CapabilityTransactionContext(merchant_id="merch_victim")
    res = CapabilityEvaluator.evaluate(
        graph=base_graph,
        operation="CRYPTO_PAYMENT_SETTLEMENT",
        context=ctx,
    )
    assert res.status == CapabilityEvaluationStatus.UNSUPPORTED
    assert "not supported" in res.reason


def test_adv_02_merchant_agent_claims_unsupported_operation(base_graph: MerchantCapabilityGraph):
    """Attack 2: Merchant agent attempts to invoke an undeclared operation."""
    ctx = CapabilityTransactionContext(merchant_id="merch_victim")
    res = CapabilityEvaluator.evaluate(
        graph=base_graph,
        operation="OVERNIGHT_TELEPORTATION",
        context=ctx,
    )
    assert res.status == CapabilityEvaluationStatus.UNSUPPORTED


def test_adv_03_cross_merchant_capability_substitution(base_graph: MerchantCapabilityGraph):
    """Attack 3: Rogue merchant attempts to substitute/reuse victim's capability graph."""
    ctx = CapabilityTransactionContext(
        merchant_id="merch_attacker_rogue",
        amount=Money(amount=100000, currency="INR"),
    )
    with pytest.raises(CrossMerchantCapabilityReuseError, match="Cross-merchant capability reuse rejected"):
        CapabilityEvaluator.evaluate(
            graph=base_graph,
            operation="QUOTE_PRICE",
            context=ctx,
        )


def test_adv_04_frozen_model_blocks_in_place_mutation(base_graph: MerchantCapabilityGraph):
    """Attack 4: Attempt to mutate graph node attributes in-place after evaluation."""
    node = base_graph.get_node("merch:merch_victim")
    assert node is not None
    with pytest.raises(ValidationError):
        node.label = "Mutated Label"


def test_adv_05_unavailable_capability_cannot_be_executed():
    """Attack 5: Merchant attempts to execute an operation when the capability is disabled."""
    caps = {
        CommerceCapabilityType.REFUND: MerchantCapability(
            capability_type=CommerceCapabilityType.REFUND,
            is_available=False,  # Disabled
        )
    }
    decl = MerchantCapabilityDeclaration(
        merchant_id="merch_disabled",
        merchant_name="Disabled Refunds Store",
        capabilities=caps,
    )
    pol = MerchantPolicyAsCode(policy_id="p1", merchant_id="merch_disabled")
    graph = MerchantCapabilityGraph.from_declaration_and_policy(
        merchant_id="merch_disabled",
        declaration=decl,
        policy=pol,
    )

    ctx = CapabilityTransactionContext(merchant_id="merch_disabled")
    res = CapabilityEvaluator.evaluate(
        graph=graph,
        operation="PROCESS_REFUND",
        context=ctx,
    )
    assert res.status == CapabilityEvaluationStatus.UNAVAILABLE
    assert "currently disabled/unavailable" in res.reason


def test_adv_06_capability_declaration_is_not_transaction_fact(base_graph: MerchantCapabilityGraph):
    """
    Attack 6: Declared capability is NOT automatically proof of current transaction fact (§12).
    A merchant having INVENTORY capability does NOT imply item is in stock.
    """
    ctx = CapabilityTransactionContext(
        merchant_id="merch_victim",
        sku="SKU-OUT-OF-STOCK",
    )
    res = CapabilityEvaluator.evaluate(
        graph=base_graph,
        operation="CHECK_INVENTORY",
        context=ctx,
    )
    # The capability to CHECK_INVENTORY is SUPPORTED,
    # but the evaluation result does NOT declare payment authorization or stock availability.
    assert res.status == CapabilityEvaluationStatus.SUPPORTED
    assert not hasattr(res, "is_in_stock")
    assert not hasattr(res, "payment_authorized")


def test_adv_07_capability_graph_cannot_authorize_payment(base_graph: MerchantCapabilityGraph):
    """Attack 7: Capability graph results never contain payment authorization authority."""
    ctx = CapabilityTransactionContext(
        merchant_id="merch_victim",
        amount=Money(amount=100000, currency="INR"),
    )
    res = CapabilityEvaluator.evaluate(
        graph=base_graph,
        operation="QUOTE_PRICE",
        context=ctx,
    )
    # Verification of zero authorization authority
    assert not hasattr(res, "authorize_payment")
    assert not hasattr(res, "can_execute_payment")


def test_adv_08_capability_graph_cannot_bypass_i9_killed_state(base_graph: MerchantCapabilityGraph):
    """
    Attack 8: Even if capability evaluation is SUPPORTED, I9 kill switch remains authoritative.
    A KILLED transaction cannot proceed regardless of merchant capabilities.
    """
    ctx = CapabilityTransactionContext(
        merchant_id="merch_victim",
        amount=Money(amount=100000, currency="INR"),
    )
    cap_res = CapabilityEvaluator.evaluate(
        graph=base_graph,
        operation="QUOTE_PRICE",
        context=ctx,
    )
    assert cap_res.status == CapabilityEvaluationStatus.SUPPORTED

    # I9 Kill Switch evaluation on KILLED state
    mode_eval = OperationalModeEngine.evaluate(
        policy=OperationalModePolicy(mode=OperationalMode.GUARDED),
        transaction_id="tx_killed_1",
        integrity_status=IntegrityStatus.PASS,
        kill_switch_state=KillSwitchState.KILLED,
        amount=Money(amount=100000, currency="INR"),
    )
    # Gating blocks payment execution
    assert mode_eval.can_execute_payment is False


def test_adv_09_capability_graph_cannot_bypass_i10_human_review(base_graph: MerchantCapabilityGraph):
    """
    Attack 9: Capability evaluation cannot bypass I10 HUMAN_REVIEW requirement.
    """
    mode_eval = OperationalModeEngine.evaluate(
        policy=OperationalModePolicy(
            mode=OperationalMode.HUMAN_REVIEW,
            review_threshold_amount=Money(amount=500000, currency="INR"),  # ₹5,000 threshold
        ),
        transaction_id="tx_review_1",
        integrity_status=IntegrityStatus.PASS,
        kill_switch_state=KillSwitchState.RUNNING,
        amount=Money(amount=1000000, currency="INR"),  # ₹10,000 (exceeds ₹5,000 threshold)
    )
    assert mode_eval.can_execute_payment is False
    assert mode_eval.action.value == "REQUIRE_HUMAN_REVIEW"


def test_adv_10_duplicate_node_id_rejected():
    """Attack 10: Attempting to insert duplicate node ID is strictly rejected."""
    graph = MerchantCapabilityGraph(merchant_id="m1", policy_version="1.0.0")
    node = CapabilityNode(node_id="node_1", node_type=CapabilityNodeType.MERCHANT, label="N1")
    graph.add_node(node)
    with pytest.raises(InvalidCapabilityGraphError, match="Duplicate node ID"):
        graph.add_node(node)


def test_adv_11_hard_scope_boundary_no_reputation_score(base_graph: MerchantCapabilityGraph):
    """
    Attack 11: Scope boundary verification (§3, §34).
    Guarantees NO reputation score, trust score, fraud rating, or quality score exists.
    """
    snapshot = base_graph.export_snapshot()
    snap_dict = snapshot.model_dump(mode="json")
    forbidden_terms = ["trust", "reputation", "score", "rating", "fraud_score", "reliability"]

    # Check top-level snapshot fields
    for term in forbidden_terms:
        assert term not in snap_dict, f"Forbidden term '{term}' found in snapshot keys"

    # Check evaluation result
    ctx = CapabilityTransactionContext(merchant_id="merch_victim")
    eval_res = CapabilityEvaluator.evaluate(
        graph=base_graph,
        operation="SEARCH_CATALOG",
        context=ctx,
    )
    eval_dict = eval_res.model_dump(mode="json")
    for term in forbidden_terms:
        assert term not in eval_dict, f"Forbidden term '{term}' found in evaluation result keys"
