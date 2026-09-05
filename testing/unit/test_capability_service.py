"""Unit tests for MerchantCapabilityService registry and replanning integration."""
import pytest

from backend.app.domain.capability.contracts import (
    CapabilityConstraint,
    CapabilityEvaluationStatus,
    CapabilityTransactionContext,
    ConstraintType,
    CrossMerchantCapabilityReuseError,
)
from backend.app.domain.models.money import Money
from backend.app.services.capability.service import MerchantCapabilityService
from backend.app.services.merchant.catalog_service import MerchantCatalogService


@pytest.fixture
def catalog_service() -> MerchantCatalogService:
    return MerchantCatalogService(merchant_id="store_service_test")


def test_service_registration_from_catalog(catalog_service: MerchantCatalogService):
    """Verify service auto-registers graph from MerchantCatalogService."""
    svc = MerchantCapabilityService()
    graph = svc.register_from_merchant_catalog(catalog_service)

    assert graph.merchant_id == "store_service_test"
    retrieved_graph = svc.get_graph("store_service_test")
    assert retrieved_graph is not None
    assert retrieved_graph.merchant_id == "store_service_test"

    snapshot = svc.get_snapshot("store_service_test")
    assert snapshot is not None
    assert snapshot.graph_hash is not None


def test_service_evaluate_operation(catalog_service: MerchantCatalogService):
    """Verify evaluation via service query surface."""
    svc = MerchantCapabilityService()
    svc.register_from_merchant_catalog(catalog_service)

    ctx = CapabilityTransactionContext(
        merchant_id="store_service_test",
        amount=Money(amount=100000, currency="INR"),
    )
    result = svc.evaluate_operation(
        merchant_id="store_service_test",
        operation="QUOTE_PRICE",
        context=ctx,
    )

    assert result.status == CapabilityEvaluationStatus.SUPPORTED
    assert result.merchant_id == "store_service_test"


def test_service_generate_replanning_advice_for_negotiation(catalog_service: MerchantCatalogService):
    """Verify service formats actionable replanning advice when capability constraints are breached."""
    svc = MerchantCapabilityService()
    graph = svc.register_from_merchant_catalog(catalog_service)

    # Exceed discount ceiling (policy has 2000 bps)
    ctx = CapabilityTransactionContext(
        merchant_id="store_service_test",
        amount=Money(amount=100000, currency="INR"),
        requested_discount_bps=3500,  # 35%
    )
    eval_res = svc.evaluate_operation(
        merchant_id="store_service_test",
        operation="APPLY_DISCOUNT",
        context=ctx,
    )
    assert eval_res.status == CapabilityEvaluationStatus.CONSTRAINED

    advice = svc.generate_replanning_advice(eval_res)
    assert advice is not None
    assert advice["merchant_id"] == "store_service_test"
    assert advice["violations_count"] == 1
    assert len(advice["suggested_actions"]) == 1
    assert advice["suggested_actions"][0]["action"] == "REDUCE_REQUESTED_DISCOUNT"
    assert "policy ceiling" in advice["suggested_actions"][0]["suggestion"]
