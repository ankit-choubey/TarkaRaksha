"""
Merchant Capability Declaration and Policy-as-Code for TarkaRaksha (I4.2).

Provides:
- MerchantCapability: Individual commerce capability advertisement (available, version, scope, constraints).
- MerchantCapabilityDeclaration: Complete capability manifesto of the synthetic/reference merchant agent.
- MerchantPolicyAsCode: Deterministic parameter bounds (MAX_ORDER_VALUE, MAX_DISCOUNT, ALLOWED_SUBSTITUTIONS, OFFER_TTL, etc.).
- Deterministic policy evaluator verifying compliance of proposals against policy rules.
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.domain.models.money import Money


class CommerceCapabilityType(str, Enum):
    """Standardized commerce capabilities recognized by TarkaRaksha."""
    CATALOG = "CATALOG"
    INVENTORY = "INVENTORY"
    PRICING = "PRICING"
    SHIPPING = "SHIPPING"
    TAX = "TAX"
    ALTERNATIVE_OFFER = "ALTERNATIVE_OFFER"
    REFUND = "REFUND"
    FULFILLMENT = "FULFILLMENT"


class MerchantCapability(BaseModel):
    """Specific capability advertised by the merchant agent."""
    capability_type: CommerceCapabilityType
    is_available: bool = True
    version: str = "1.0.0"
    scope: str = "FULL"
    constraints: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )


class MerchantCapabilityDeclaration(BaseModel):
    """
    Declaration manifesto detailing supported commerce capabilities of the merchant agent.
    Shields TarkaRaksha and buyer agents from making unsupported requests.
    """
    merchant_id: str
    merchant_name: str
    agent_version: str = "1.0.0"
    capabilities: Dict[CommerceCapabilityType, MerchantCapability]
    declared_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )

    def supports(self, capability: CommerceCapabilityType) -> bool:
        """Returns True if the merchant supports and currently enables the capability."""
        cap = self.capabilities.get(capability)
        return cap is not None and cap.is_available

    @classmethod
    def default_reference_declaration(cls, merchant_id: str = "merchant-reference-1") -> "MerchantCapabilityDeclaration":
        """Factory for the default synthetic/reference merchant agent capability set."""
        caps = {
            CommerceCapabilityType.CATALOG: MerchantCapability(capability_type=CommerceCapabilityType.CATALOG, is_available=True),
            CommerceCapabilityType.INVENTORY: MerchantCapability(capability_type=CommerceCapabilityType.INVENTORY, is_available=True),
            CommerceCapabilityType.PRICING: MerchantCapability(capability_type=CommerceCapabilityType.PRICING, is_available=True),
            CommerceCapabilityType.SHIPPING: MerchantCapability(capability_type=CommerceCapabilityType.SHIPPING, is_available=True),
            CommerceCapabilityType.TAX: MerchantCapability(capability_type=CommerceCapabilityType.TAX, is_available=True),
            CommerceCapabilityType.ALTERNATIVE_OFFER: MerchantCapability(capability_type=CommerceCapabilityType.ALTERNATIVE_OFFER, is_available=True),
            CommerceCapabilityType.REFUND: MerchantCapability(capability_type=CommerceCapabilityType.REFUND, is_available=True, constraints={"max_refund_window_days": 14}),
            CommerceCapabilityType.FULFILLMENT: MerchantCapability(capability_type=CommerceCapabilityType.FULFILLMENT, is_available=True),
        }
        return cls(
            merchant_id=merchant_id,
            merchant_name="TarkaRaksha Reference Merchant",
            capabilities=caps,
        )


class MerchantPolicyAsCode(BaseModel):
    """
    Deterministic merchant business policy rules (§11.4).
    Data-driven constraints, strictly evaluated without LLM interpretation.
    """
    policy_id: str
    policy_version: str = "merchant-policy-1.0.0"
    merchant_id: str
    max_order_value: Money = Field(default_factory=lambda: Money(amount=5000000, currency="INR"))  # ₹50,000.00 max
    max_discount_bps: int = 2000  # 20.00% max discount
    allowed_substitutions: Dict[str, List[str]] = Field(default_factory=dict)
    max_negotiation_rounds: int = 3
    offer_ttl_seconds: int = 900  # 15 minutes TTL
    refund_limit: Money = Field(default_factory=lambda: Money(amount=5000000, currency="INR"))
    min_delivery_days: int = 1
    max_delivery_days: int = 7

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )

    def validate_offer_compliance(
        self,
        subtotal: Money,
        discount: Money,
        sku: str,
        delivery_days: int,
    ) -> tuple[bool, Optional[str]]:
        """
        Deterministically evaluates whether an offer satisfies merchant policy.
        Returns (is_compliant, violation_reason).
        """
        # 1. Total order value ceiling
        if subtotal.amount > self.max_order_value.amount:
            return False, f"Order subtotal {subtotal.amount} exceeds policy ceiling {self.max_order_value.amount}"

        # 2. Maximum discount percentage
        if subtotal.amount > 0:
            discount_bps = int((discount.amount * 10000) / subtotal.amount)
            if discount_bps > self.max_discount_bps:
                return False, f"Discount {discount_bps} bps exceeds policy maximum {self.max_discount_bps} bps"

        # 3. Delivery timeline bounds
        if delivery_days < self.min_delivery_days or delivery_days > self.max_delivery_days:
            return False, f"Delivery estimate {delivery_days} days outside policy window [{self.min_delivery_days}, {self.max_delivery_days}]"

        return True, None

    def get_allowed_substitutes(self, sku: str) -> List[str]:
        """Returns pre-authorized substitute SKUs for a given item."""
        return self.allowed_substitutions.get(sku, [])
