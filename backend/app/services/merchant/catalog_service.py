"""
Deterministic Catalog, Inventory, and Offer Service for TarkaRaksha (I4.3).

Responsibilities:
- In-memory deterministic product catalog repository.
- Inventory tracking with reservation and availability validation.
- Offer calculation: pricing, policy-bounded discount, shipping selection, tax calculation.
- Suggestion of pre-authorized alternatives when primary SKU is unavailable.
- Generating merchant-side evidence without asserting transaction PASS authority.
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import uuid

from backend.app.domain.evidence.extensions import MerchantOffer
from backend.app.domain.merchant.capabilities import (
    CommerceCapabilityType,
    MerchantCapabilityDeclaration,
    MerchantPolicyAsCode,
)
from backend.app.domain.merchant.contracts import (
    BuyerCommerceRequest,
    BuyerItemRequest,
    CatalogItem,
    InventoryRecord,
    InventoryStatus,
    MerchantOfferItem,
    MerchantResponse,
    ShippingOption,
    TaxEstimate,
)
from backend.app.domain.models.enums import EvidenceAuthority, EvidenceSource
from backend.app.domain.models.evidence import Evidence
from backend.app.domain.models.money import Money


class MerchantCatalogService:
    """
    Deterministic reference merchant catalog, inventory, and offer engine.
    Pure functional/in-memory implementation for the prototype.
    """

    def __init__(
        self,
        merchant_id: str = "merchant-reference-1",
        merchant_name: str = "TarkaRaksha Reference Store",
        capabilities: Optional[MerchantCapabilityDeclaration] = None,
        policy: Optional[MerchantPolicyAsCode] = None,
    ):
        self.merchant_id = merchant_id
        self.merchant_name = merchant_name
        self.capabilities = capabilities or MerchantCapabilityDeclaration.default_reference_declaration(merchant_id)
        self.policy = policy or MerchantPolicyAsCode(policy_id="pol-ref-1", merchant_id=merchant_id)

        # In-memory catalog database
        self._catalog: Dict[str, CatalogItem] = {}
        # In-memory inventory database
        self._inventory: Dict[str, InventoryRecord] = {}
        # Pre-configured shipping options
        self._shipping_options: Dict[str, ShippingOption] = {}
        self._capability_graph = None

        self._seed_default_catalog()

    @property
    def capability_graph(self):
        """Returns the deterministic MerchantCapabilityGraph for this merchant."""
        if self._capability_graph is None:
            from backend.app.domain.capability.graph import MerchantCapabilityGraph
            self._capability_graph = MerchantCapabilityGraph.from_declaration_and_policy(
                merchant_id=self.merchant_id,
                declaration=self.capabilities,
                policy=self.policy,
            )
        return self._capability_graph

    def _seed_default_catalog(self) -> None:
        """Seeds initial synthetic/reference merchandise."""
        items = [
            CatalogItem(
                sku="SKU-BOOK-001",
                title="Agentic Systems & Deterministic Control",
                description="Engineering reference textbook on verifiable AI architectures",
                category="Books",
                base_price=Money(amount=500000, currency="INR"),  # ₹5,000.00
                tags=["books", "ai", "engineering"],
            ),
            CatalogItem(
                sku="SKU-MOUSE-001",
                title="Ergonomic Optical Mouse",
                description="Precision wireless optical mouse with USB-C dongle",
                category="Electronics",
                base_price=Money(amount=250000, currency="INR"),  # ₹2,500.00
                tags=["electronics", "peripherals"],
            ),
            CatalogItem(
                sku="SKU-MOUSE-ALT",
                title="Ergonomic Optical Mouse (Standard Gray)",
                description="Alternative color edition of the precision wireless optical mouse",
                category="Electronics",
                base_price=Money(amount=240000, currency="INR"),  # ₹2,400.00
                tags=["electronics", "peripherals", "alternative"],
            ),
        ]
        for it in items:
            self._catalog[it.sku] = it
            self._inventory[it.sku] = InventoryRecord(
                sku=it.sku,
                quantity_available=50,
                status=InventoryStatus.AVAILABLE,
            )

        # Pre-authorized substitution mapping in policy
        self.policy = self.policy.model_copy(
            update={"allowed_substitutions": {"SKU-MOUSE-001": ["SKU-MOUSE-ALT"]}}
        )

        # Shipping tiers
        self._shipping_options["ship-standard"] = ShippingOption(
            option_id="ship-standard",
            carrier="ExpressPost",
            method_name="Standard Ground",
            cost=Money(amount=10000, currency="INR"),  # ₹100.00
            estimated_days=3,
        )
        self._shipping_options["ship-express"] = ShippingOption(
            option_id="ship-express",
            carrier="BlueDart",
            method_name="Overnight Priority",
            cost=Money(amount=30000, currency="INR"),  # ₹300.00
            estimated_days=1,
            guaranteed_days=2,
        )

    def add_catalog_item(self, item: CatalogItem, initial_stock: int = 10) -> None:
        """Registers a new item in the catalog and inventory."""
        self._catalog[item.sku] = item
        self._inventory[item.sku] = InventoryRecord(
            sku=item.sku,
            quantity_available=initial_stock,
            status=InventoryStatus.AVAILABLE if initial_stock > 0 else InventoryStatus.SOLD_OUT,
        )

    def set_inventory_status(self, sku: str, quantity: int, status: Optional[InventoryStatus] = None) -> None:
        """Updates inventory quantity and status for a SKU."""
        if sku not in self._catalog:
            raise KeyError(f"SKU '{sku}' does not exist in merchant catalog")
        derived_status = status or (InventoryStatus.AVAILABLE if quantity > 0 else InventoryStatus.SOLD_OUT)
        self._inventory[sku] = InventoryRecord(
            sku=sku,
            quantity_available=quantity,
            status=derived_status,
        )

    def get_catalog_item(self, sku: str) -> Optional[CatalogItem]:
        """Retrieves a catalog item by SKU."""
        return self._catalog.get(sku)

    def get_inventory_record(self, sku: str) -> Optional[InventoryRecord]:
        """Retrieves inventory availability for a SKU."""
        return self._inventory.get(sku)

    def process_buyer_request(
        self,
        request: BuyerCommerceRequest,
        discount_percentage_bps: int = 0,
        reference_time: Optional[datetime] = None,
    ) -> MerchantResponse:
        """
        Deterministically evaluates a BuyerCommerceRequest and generates a structured MerchantResponse.
        
        Steps:
        1. Validates merchant capability availability.
        2. Checks catalog and inventory status for each requested item.
        3. If item is unavailable, proposes pre-authorized alternatives if available.
        4. Calculates subtotal, policy-compliant discount, shipping, and tax.
        5. Verifies offer compliance against MerchantPolicyAsCode.
        6. Generates response envelope with explicit expiration timestamp.
        """
        now = reference_time or datetime.now(timezone.utc)
        offer_expires = now + timedelta(seconds=self.policy.offer_ttl_seconds)

        # 1. Capability check
        if not self.capabilities.supports(CommerceCapabilityType.CATALOG):
            return MerchantResponse(
                response_id=f"resp-{uuid.uuid4().hex[:8]}",
                merchant_id=self.merchant_id,
                request_id=request.request_id,
                intent_id=request.intent_id,
                transaction_id=request.transaction_id,
                is_success=False,
                rejection_reason="Merchant does not currently support catalog/ordering capabilities",
                offer_created_at=now,
                offer_expires_at=offer_expires,
                explanation="Capability CATALOG disabled in merchant manifesto",
            )

        # 2. Process requested items
        offer_items: List[MerchantOfferItem] = []
        subtotal_amount = 0
        currency = "INR"

        for req_item in request.items:
            catalog_item = self._catalog.get(req_item.sku)
            if not catalog_item or not catalog_item.is_active:
                return self._handle_item_unavailable(request, req_item, now, offer_expires, reason="Item not found or inactive")

            inv = self._inventory.get(req_item.sku)
            if not inv or inv.quantity_available < req_item.quantity:
                return self._handle_item_unavailable(request, req_item, now, offer_expires, reason=f"Insufficient stock for {req_item.sku}")

            line_total = catalog_item.base_price * req_item.quantity
            currency = catalog_item.currency
            offer_items.append(
                MerchantOfferItem(
                    sku=catalog_item.sku,
                    title=catalog_item.title,
                    quantity=req_item.quantity,
                    unit_price=catalog_item.base_price,
                    total_price=line_total,
                )
            )
            subtotal_amount += line_total.amount

        # 3. Calculate financial breakdown
        subtotal_money = Money(amount=subtotal_amount, currency=currency)

        # Bound discount by policy
        effective_bps = min(discount_percentage_bps, self.policy.max_discount_bps)
        discount_amount = int((subtotal_amount * effective_bps) / 10000)
        discount_money = Money(amount=discount_amount, currency=currency)

        # 4. Shipping selection
        shipping_choice = self._shipping_options.get(
            request.preferred_shipping_id or "ship-standard",
            self._shipping_options["ship-standard"],
        )

        # 5. Tax estimation (18% GST standard on discounted subtotal + shipping)
        taxable_base = subtotal_amount - discount_amount + shipping_choice.cost.amount
        tax_amount = int((taxable_base * 1800) / 10000)
        tax_est = TaxEstimate(
            tax_type="GST",
            rate_bps=1800,
            amount=Money(amount=tax_amount, currency=currency),
            jurisdiction="IN",
        )

        total_amount = taxable_base + tax_amount
        total_money = Money(amount=total_amount, currency=currency)

        # 6. Policy compliance verification
        is_compliant, policy_reason = self.policy.validate_offer_compliance(
            subtotal=subtotal_money,
            discount=discount_money,
            sku=offer_items[0].sku if offer_items else "",
            delivery_days=shipping_choice.estimated_days,
        )
        if not is_compliant:
            return MerchantResponse(
                response_id=f"resp-{uuid.uuid4().hex[:8]}",
                merchant_id=self.merchant_id,
                request_id=request.request_id,
                intent_id=request.intent_id,
                transaction_id=request.transaction_id,
                is_success=False,
                rejection_reason=f"Policy violation: {policy_reason}",
                offer_created_at=now,
                offer_expires_at=offer_expires,
                explanation=str(policy_reason),
            )

        # 7. Deadline satisfaction
        if request.delivery_deadline_days is not None:
            if shipping_choice.estimated_days > request.delivery_deadline_days:
                return MerchantResponse(
                    response_id=f"resp-{uuid.uuid4().hex[:8]}",
                    merchant_id=self.merchant_id,
                    request_id=request.request_id,
                    intent_id=request.intent_id,
                    transaction_id=request.transaction_id,
                    is_success=False,
                    rejection_reason=f"Cannot fulfill within deadline ({shipping_choice.estimated_days}d > {request.delivery_deadline_days}d)",
                    offer_created_at=now,
                    offer_expires_at=offer_expires,
                    explanation="Fulfillment deadline unsatisfied",
                )

        return MerchantResponse(
            response_id=f"resp-{uuid.uuid4().hex[:8]}",
            merchant_id=self.merchant_id,
            request_id=request.request_id,
            intent_id=request.intent_id,
            transaction_id=request.transaction_id,
            is_success=True,
            offer_id=f"off-{uuid.uuid4().hex[:8]}",
            items=offer_items,
            subtotal=subtotal_money,
            discount=discount_money,
            shipping=shipping_choice,
            tax=tax_est,
            total_amount=total_money,
            inventory_status=InventoryStatus.AVAILABLE,
            estimated_delivery_days=shipping_choice.estimated_days,
            offer_created_at=now,
            offer_expires_at=offer_expires,
            policy_version=self.policy.policy_version,
            explanation="Deterministic commercial offer generated by reference merchant agent",
        )

    def _handle_item_unavailable(
        self,
        request: BuyerCommerceRequest,
        req_item: BuyerItemRequest,
        now: datetime,
        offer_expires: datetime,
        reason: str,
    ) -> MerchantResponse:
        """Proposes pre-authorized alternatives if available, otherwise rejects cleanly."""
        alternatives: List[Dict[str, Any]] = []
        if self.capabilities.supports(CommerceCapabilityType.ALTERNATIVE_OFFER):
            allowed_subs = self.policy.get_allowed_substitutes(req_item.sku)
            for sub_sku in allowed_subs:
                sub_item = self._catalog.get(sub_sku)
                sub_inv = self._inventory.get(sub_sku)
                if sub_item and sub_inv and sub_inv.quantity_available >= req_item.quantity:
                    alternatives.append({
                        "sku": sub_sku,
                        "title": sub_item.title,
                        "unit_price": sub_item.base_price.model_dump(),
                        "quantity_available": sub_inv.quantity_available,
                    })

        return MerchantResponse(
            response_id=f"resp-{uuid.uuid4().hex[:8]}",
            merchant_id=self.merchant_id,
            request_id=request.request_id,
            intent_id=request.intent_id,
            transaction_id=request.transaction_id,
            is_success=False,
            rejection_reason=reason,
            alternatives=alternatives,
            offer_created_at=now,
            offer_expires_at=offer_expires,
            inventory_status=InventoryStatus.SOLD_OUT,
            explanation=f"Item {req_item.sku} unavailable; {len(alternatives)} alternatives proposed",
        )

    @classmethod
    def convert_response_to_merchant_offer(cls, response: MerchantResponse) -> Optional[MerchantOffer]:
        """
        Converts a successful MerchantResponse into an additive MerchantOffer evidence domain model.
        """
        if not response.is_success or not response.offer_id or not response.items:
            return None

        first_item = response.items[0]
        return MerchantOffer(
            offer_id=response.offer_id,
            merchant_id=response.merchant_id,
            sku=first_item.sku,
            quantity=first_item.quantity,
            unit_price=first_item.unit_price,
            discount=response.discount or Money(amount=0, currency=first_item.unit_price.currency),
            shipping=response.shipping.cost if response.shipping else Money(amount=0, currency=first_item.unit_price.currency),
            tax=response.tax.amount if response.tax else Money(amount=0, currency=first_item.unit_price.currency),
            total=response.total_amount or first_item.total_price,
            currency=first_item.unit_price.currency,
            inventory_status=response.inventory_status.value,
            delivery_estimate=f"{response.estimated_delivery_days} days",
            offer_created_at=response.offer_created_at,
            offer_expires_at=response.offer_expires_at,
            merchant_policy_version=response.policy_version,
            evidence_refs=[f"merchant_response_{response.response_id}"],
        )
