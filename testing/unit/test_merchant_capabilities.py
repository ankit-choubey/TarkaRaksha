"""
Unit tests for Merchant Capability Declaration & Policy-as-Code (I4.2).
"""
import pytest

from backend.app.domain.merchant import (
    CommerceCapabilityType,
    MerchantCapability,
    MerchantCapabilityDeclaration,
    MerchantPolicyAsCode,
)
from backend.app.domain.models import Money


def test_merchant_capability_declaration():
    decl = MerchantCapabilityDeclaration.default_reference_declaration("merch-100")
    assert decl.merchant_id == "merch-100"
    assert decl.supports(CommerceCapabilityType.CATALOG) is True
    assert decl.supports(CommerceCapabilityType.PRICING) is True
    assert decl.supports(CommerceCapabilityType.ALTERNATIVE_OFFER) is True
    assert decl.supports(CommerceCapabilityType.REFUND) is True


def test_merchant_capability_declaration_disabled_capability():
    custom_caps = {
        CommerceCapabilityType.CATALOG: MerchantCapability(capability_type=CommerceCapabilityType.CATALOG, is_available=True),
        CommerceCapabilityType.REFUND: MerchantCapability(capability_type=CommerceCapabilityType.REFUND, is_available=False),
    }
    decl = MerchantCapabilityDeclaration(
        merchant_id="merch-no-refund",
        merchant_name="No Refund Store",
        capabilities=custom_caps,
    )
    assert decl.supports(CommerceCapabilityType.CATALOG) is True
    assert decl.supports(CommerceCapabilityType.REFUND) is False
    assert decl.supports(CommerceCapabilityType.SHIPPING) is False


def test_merchant_policy_as_code_compliance_success():
    policy = MerchantPolicyAsCode(
        policy_id="pol-001",
        merchant_id="merch-100",
        max_order_value=Money(amount=1000000, currency="INR"),  # ₹10,000 max
        max_discount_bps=1500,  # 15% max discount
        min_delivery_days=1,
        max_delivery_days=5,
    )

    subtotal = Money(amount=500000, currency="INR")
    discount = Money(amount=50000, currency="INR")  # 10% discount <= 15%
    is_valid, reason = policy.validate_offer_compliance(subtotal, discount, "SKU-BOOK", delivery_days=3)

    assert is_valid is True
    assert reason is None


def test_merchant_policy_as_code_order_ceiling_violation():
    policy = MerchantPolicyAsCode(
        policy_id="pol-001",
        merchant_id="merch-100",
        max_order_value=Money(amount=1000000, currency="INR"),
    )

    subtotal = Money(amount=1500000, currency="INR")  # Exceeds ₹10,000
    discount = Money(amount=0, currency="INR")
    is_valid, reason = policy.validate_offer_compliance(subtotal, discount, "SKU-BOOK", delivery_days=2)

    assert is_valid is False
    assert "exceeds policy ceiling" in reason


def test_merchant_policy_as_code_discount_ceiling_violation():
    policy = MerchantPolicyAsCode(
        policy_id="pol-001",
        merchant_id="merch-100",
        max_discount_bps=1000,  # 10%
    )

    subtotal = Money(amount=100000, currency="INR")
    discount = Money(amount=25000, currency="INR")  # 25% discount > 10%
    is_valid, reason = policy.validate_offer_compliance(subtotal, discount, "SKU-BOOK", delivery_days=2)

    assert is_valid is False
    assert "exceeds policy maximum" in reason


def test_merchant_policy_allowed_substitutions():
    policy = MerchantPolicyAsCode(
        policy_id="pol-001",
        merchant_id="merch-100",
        allowed_substitutions={
            "SKU-IPHONE-15-BLUE": ["SKU-IPHONE-15-BLACK", "SKU-IPHONE-15-WHITE"]
        },
    )

    subs = policy.get_allowed_substitutes("SKU-IPHONE-15-BLUE")
    assert "SKU-IPHONE-15-BLACK" in subs
    assert len(subs) == 2

    assert policy.get_allowed_substitutes("SKU-UNKNOWN") == []
