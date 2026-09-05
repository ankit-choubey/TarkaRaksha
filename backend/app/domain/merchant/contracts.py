"""
Merchant Agent Domain Contracts and Models for TarkaRaksha (I4.1).

Defines:
- CatalogItem: SKU, title, description, category, base_price, currency, tags, attributes
- InventoryRecord: SKU, quantity_available, quantity_reserved, restock_date, status
- ShippingOption: Option ID, method, cost, estimated_days, guaranteed_days
- TaxEstimate: Rate, amount, currency, jurisdiction
- BuyerCommerceRequest: Target items, max_budget, preferred_shipping, delivery_deadline, intent_id, transaction_id
- MerchantOfferDetails: Structured proposal linking catalog, pricing, tax, shipping, inventory, and policy version
- MerchantResponse: Envelope returning offers, alternatives, explanations, policy attestation, and capability refs
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.domain.models.money import Money


class InventoryStatus(str, Enum):
    """Authoritative inventory availability states."""
    AVAILABLE = "AVAILABLE"
    LOW_STOCK = "LOW_STOCK"
    BACKORDER = "BACKORDER"
    SOLD_OUT = "SOLD_OUT"
    DISCONTINUED = "DISCONTINUED"


class CatalogItem(BaseModel):
    """Individual product or service available in the merchant catalog."""
    sku: str
    title: str
    description: str
    category: str
    base_price: Money
    currency: str = "INR"
    is_active: bool = True
    tags: List[str] = Field(default_factory=list)
    attributes: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )

    @field_validator("sku", "title")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("String identifier cannot be empty or whitespace.")
        return v.strip()

    @property
    def price(self) -> Money:
        """Convenience property for base_price."""
        return self.base_price


class InventoryRecord(BaseModel):
    """Inventory tracking record for a specific SKU."""
    sku: str
    quantity_available: int
    quantity_reserved: int = 0
    status: InventoryStatus = InventoryStatus.AVAILABLE
    restock_expected_at: Optional[datetime] = None
    last_updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )

    @field_validator("quantity_available", "quantity_reserved")
    @classmethod
    def validate_non_negative(cls, v: int) -> int:
        if isinstance(v, bool) or not isinstance(v, int) or v < 0:
            raise ValueError("Inventory quantities must be non-negative integers >= 0")
        return v

    @field_validator("last_updated_at", "restock_expected_at", mode="before")
    @classmethod
    def validate_timezone(cls, v: Any) -> Optional[datetime]:
        if v is None:
            return None
        if isinstance(v, str):
            dt = datetime.fromisoformat(v)
        elif isinstance(v, datetime):
            dt = v
        else:
            raise TypeError(f"Timestamp must be datetime or ISO string, got {type(v).__name__}")
        if dt.tzinfo is None:
            raise ValueError("Timestamp must be timezone-aware (e.g. UTC)")
        return dt


class ShippingOption(BaseModel):
    """Merchant-provided shipping and fulfillment method."""
    option_id: str
    carrier: str
    method_name: str
    cost: Money
    estimated_days: int
    guaranteed_days: Optional[int] = None

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )

    @field_validator("estimated_days")
    @classmethod
    def validate_positive_days(cls, v: int) -> int:
        if isinstance(v, bool) or not isinstance(v, int) or v <= 0:
            raise ValueError("Shipping days must be a positive integer >= 1")
        return v


class TaxEstimate(BaseModel):
    """Calculated tax liability for a merchant offer."""
    tax_type: str = "GST"
    rate_bps: int = 1800  # 18.00% standard GST in basis points
    amount: Money
    jurisdiction: str = "IN"

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )


class BuyerItemRequest(BaseModel):
    """Item requested by the buyer or buyer agent."""
    sku: str
    quantity: int = 1
    max_acceptable_unit_price: Optional[Money] = None

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )

    @field_validator("quantity")
    @classmethod
    def validate_quantity(cls, v: int) -> int:
        if isinstance(v, bool) or not isinstance(v, int) or v <= 0:
            raise ValueError("Requested quantity must be positive integer >= 1")
        return v


class BuyerCommerceRequest(BaseModel):
    """
    Structured buyer-agent intent/request directed to the merchant agent.
    Includes target items, financial ceiling, temporal deadline, and protocol binding identifiers.
    """
    request_id: str
    buyer_agent_id: str
    intent_id: str
    transaction_id: str
    items: List[BuyerItemRequest]
    max_budget: Optional[Money] = None
    preferred_shipping_id: Optional[str] = None
    delivery_deadline_days: Optional[int] = None
    request_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )

    @field_validator("request_timestamp", mode="before")
    @classmethod
    def validate_timezone(cls, v: Any) -> datetime:
        if isinstance(v, str):
            dt = datetime.fromisoformat(v)
        elif isinstance(v, datetime):
            dt = v
        else:
            raise TypeError(f"Timestamp must be datetime or ISO string, got {type(v).__name__}")
        if dt.tzinfo is None:
            raise ValueError("Timestamp must be timezone-aware (e.g. UTC)")
        return dt


class MerchantOfferItem(BaseModel):
    """Line item in a merchant offer proposal."""
    sku: str
    title: str
    quantity: int
    unit_price: Money
    total_price: Money

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )


class FulfillmentTerms(BaseModel):
    """Fulfillment terms promised by the merchant."""
    carrier: str
    estimated_delivery_days: int
    guaranteed_delivery: bool = False

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )


class MerchantResponse(BaseModel):
    """
    Standard structured response from the Merchant Agent.
    Contains primary offer or alternatives, policy explanation, and fulfillment promises.
    Note: Merchant response is merchant-attested evidence; it cannot declare transaction PASS.
    """
    response_id: str
    merchant_id: str
    request_id: str
    intent_id: str
    transaction_id: str
    is_success: bool
    offer_id: Optional[str] = None
    items: List[MerchantOfferItem] = Field(default_factory=list)
    subtotal: Optional[Money] = None
    discount: Optional[Money] = None
    shipping: Optional[ShippingOption] = None
    tax: Optional[TaxEstimate] = None
    total_amount: Optional[Money] = None
    inventory_status: InventoryStatus = InventoryStatus.AVAILABLE
    estimated_delivery_days: int = 2
    offer_created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    offer_expires_at: datetime
    policy_version: str = "merchant-policy-1.0.0"
    rejection_reason: Optional[str] = None
    alternatives: List[Dict[str, Any]] = Field(default_factory=list)
    explanation: str = ""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )

    @field_validator("inventory_status", mode="before")
    @classmethod
    def validate_inventory_status(cls, v: Any) -> InventoryStatus:
        if isinstance(v, str):
            try:
                return InventoryStatus(v)
            except ValueError:
                raise ValueError(f"Invalid inventory status: {v}")
        return v

    @field_validator("offer_created_at", "offer_expires_at", mode="before")
    @classmethod
    def validate_timezone(cls, v: Any) -> datetime:
        if isinstance(v, str):
            dt = datetime.fromisoformat(v)
        elif isinstance(v, datetime):
            dt = v
        else:
            raise TypeError(f"Timestamp must be datetime or ISO string, got {type(v).__name__}")
        if dt.tzinfo is None:
            raise ValueError("Timestamp must be timezone-aware (e.g. UTC)")
        return dt

    def is_expired(self, as_of: Optional[datetime] = None) -> bool:
        """Check whether the offer is expired relative to as_of (default now UTC)."""
        ref = as_of or datetime.now(timezone.utc)
        if ref.tzinfo is None:
            ref = ref.replace(tzinfo=timezone.utc)
        return ref >= self.offer_expires_at

    @property
    def fulfillment(self) -> FulfillmentTerms:
        """Convenience property extracting fulfillment terms."""
        carrier = self.shipping.carrier if self.shipping else "Standard Courier"
        return FulfillmentTerms(
            carrier=carrier,
            estimated_delivery_days=self.estimated_delivery_days,
            guaranteed_delivery=False,
        )

    @property
    def total(self) -> Money:
        """Convenience property for total_amount."""
        if self.total_amount is not None:
            return self.total_amount
        if self.items:
            return self.items[0].total_price
        return Money(amount=0, currency="INR")


# Alias for semantic clarity across offer integrity workflows
MerchantOffer = MerchantResponse

