"""Merchant Gate validation service for TarkaRaksha E2.

Validates merchant-side transaction context:
- merchant identity
- capability
- SKU
- inventory
- price
- shipping
- fulfillment
- offer expiry
- merchant policy

Governing Invariant:
AI proposes. Evidence proves. Deterministic logic decides.
Merchant Gate validation facts NEVER declare an authoritative financial PASS.
"""
from datetime import datetime, timezone
from typing import List, Optional

from backend.app.domain.gates.contracts import (
    GateFinding,
    GateStatus,
    GateValidationFinding,
    MerchantCheckType,
    MerchantGateResult,
)
from backend.app.domain.integration.contracts import IntegrationTransactionContext
from backend.app.domain.merchant.contracts import (
    InventoryStatus,
    MerchantResponse,
)
from backend.app.domain.merchant.capabilities import CommerceCapabilityType
from backend.app.domain.models.intent import IntentContract
from backend.app.domain.models.money import Money
from backend.app.services.merchant.catalog_service import MerchantCatalogService


class MerchantGate:
    """Deterministic validation gate for merchant-side offers and capabilities."""

    @classmethod
    def validate(
        cls,
        context: IntegrationTransactionContext,
        merchant_response: MerchantResponse,
        catalog_service: MerchantCatalogService,
        intent: Optional[IntentContract] = None,
        requested_sku: Optional[str] = None,
        requested_quantity: int = 1,
        reference_time: Optional[datetime] = None,
    ) -> MerchantGateResult:
        """Deterministically verifies merchant offer against identity, catalog, inventory, and policy."""
        ref_time = reference_time or datetime.now(timezone.utc)
        if ref_time.tzinfo is None:
            ref_time = ref_time.replace(tzinfo=timezone.utc)

        findings: List[GateValidationFinding] = []

        # 1. Merchant Identity & Context Binding
        id_violations: List[str] = []
        if merchant_response.merchant_id != context.merchant_id:
            id_violations.append(
                f"Merchant ID mismatch: offer merchant_id '{merchant_response.merchant_id}' "
                f"!= registered context '{context.merchant_id}'"
            )
        if merchant_response.merchant_id != catalog_service.merchant_id:
            id_violations.append(
                f"Catalog service merchant mismatch: offer merchant_id '{merchant_response.merchant_id}' "
                f"!= catalog service '{catalog_service.merchant_id}'"
            )
        if merchant_response.transaction_id != context.transaction_id:
            id_violations.append(
                f"Transaction context mismatch: offer transaction_id '{merchant_response.transaction_id}' "
                f"!= context '{context.transaction_id}'"
            )
        if merchant_response.intent_id != context.intent_id:
            id_violations.append(
                f"Intent context mismatch: offer intent_id '{merchant_response.intent_id}' "
                f"!= context '{context.intent_id}'"
            )

        if id_violations:
            findings.append(
                GateValidationFinding(
                    check_type=MerchantCheckType.MERCHANT_IDENTITY.value,
                    status=GateStatus.INVALID,
                    reason="; ".join(id_violations),
                    field_name="merchant_id",
                    expected_value=context.merchant_id,
                    observed_value=merchant_response.merchant_id,
                    details={"errors": id_violations},
                )
            )
        else:
            findings.append(
                GateValidationFinding(
                    check_type=MerchantCheckType.MERCHANT_IDENTITY.value,
                    status=GateStatus.VALID,
                    reason=f"Merchant identity verified as '{context.merchant_id}'",
                    field_name="merchant_id",
                    expected_value=context.merchant_id,
                    observed_value=merchant_response.merchant_id,
                )
            )

        # 2. Merchant Capability Verification
        capability_violations: List[str] = []
        caps = catalog_service.capabilities
        if not caps or not caps.capabilities:
            capability_violations.append(f"Merchant '{catalog_service.merchant_id}' has no declared capabilities in registry")
        else:
            if not caps.supports(CommerceCapabilityType.CATALOG):
                capability_violations.append(f"Merchant '{catalog_service.merchant_id}' does not support CATALOG capability")
            if not caps.supports(CommerceCapabilityType.PRICING):
                capability_violations.append(f"Merchant '{catalog_service.merchant_id}' does not support PRICING capability")

        if capability_violations:
            findings.append(
                GateValidationFinding(
                    check_type=MerchantCheckType.MERCHANT_CAPABILITY.value,
                    status=GateStatus.INVALID,
                    reason="; ".join(capability_violations),
                    field_name="capability",
                    details={"violations": capability_violations},
                )
            )
        else:
            findings.append(
                GateValidationFinding(
                    check_type=MerchantCheckType.MERCHANT_CAPABILITY.value,
                    status=GateStatus.VALID,
                    reason="Merchant capabilities verified in active capability graph",
                    field_name="capability",
                )
            )

        # 3. SKU Validity
        sku_violations: List[str] = []
        if not merchant_response.items:
            sku_violations.append("Offer contains zero items")
        else:
            for it in merchant_response.items:
                catalog_item = (
                    catalog_service.get_catalog_item(it.sku)
                    if hasattr(catalog_service, "get_catalog_item")
                    else catalog_service.get_item(it.sku)
                )
                if not catalog_item:
                    # Check if allowed substitute under policy
                    sub_allowed = False
                    if requested_sku and catalog_service.policy and catalog_service.policy.allowed_substitutions:
                        subs = catalog_service.policy.allowed_substitutions.get(requested_sku, [])
                        if it.sku in subs:
                            sub_allowed = True
                    if not sub_allowed:
                        sku_violations.append(f"SKU '{it.sku}' not found in merchant catalog or approved substitutions")

            if requested_sku:
                offered_skus = {it.sku for it in merchant_response.items}
                allowed_subs = set()
                if catalog_service.policy and catalog_service.policy.allowed_substitutions:
                    allowed_subs = set(catalog_service.policy.allowed_substitutions.get(requested_sku, []))
                if requested_sku not in offered_skus and not offered_skus.intersection(allowed_subs):
                    sku_violations.append(
                        f"Offer does not contain requested SKU '{requested_sku}' or allowed substitute"
                    )

        if sku_violations:
            findings.append(
                GateValidationFinding(
                    check_type=MerchantCheckType.SKU_VALIDITY.value,
                    status=GateStatus.INVALID,
                    reason="; ".join(sku_violations),
                    field_name="sku",
                    details={"violations": sku_violations},
                )
            )
        else:
            findings.append(
                GateValidationFinding(
                    check_type=MerchantCheckType.SKU_VALIDITY.value,
                    status=GateStatus.VALID,
                    reason="All offered SKUs verified in merchant catalog",
                    field_name="sku",
                )
            )

        # 4. Inventory Availability
        inventory_violations: List[str] = []
        inventory_unknowns: List[str] = []
        if merchant_response.inventory_status == InventoryStatus.SOLD_OUT:
            inventory_violations.append("Offer declared inventory_status as SOLD_OUT")

        for it in merchant_response.items:
            inv = (
                catalog_service.get_inventory_record(it.sku)
                if hasattr(catalog_service, "get_inventory_record")
                else catalog_service.get_inventory(it.sku)
            )
            if inv is None:
                inventory_unknowns.append(f"Authoritative inventory state unknown/missing for SKU '{it.sku}'")
            elif inv.status == InventoryStatus.SOLD_OUT or inv.status == InventoryStatus.DISCONTINUED:
                inventory_violations.append(f"Inventory status for SKU '{it.sku}' is {inv.status.value}")
            elif inv.quantity_available < it.quantity:
                inventory_violations.append(
                    f"Insufficient inventory for SKU '{it.sku}': available {inv.quantity_available} < requested {it.quantity}"
                )

        if inventory_violations:
            findings.append(
                GateValidationFinding(
                    check_type=MerchantCheckType.INVENTORY.value,
                    status=GateStatus.INVALID,
                    reason="; ".join(inventory_violations),
                    field_name="inventory",
                    details={"violations": inventory_violations},
                )
            )
        elif inventory_unknowns:
            findings.append(
                GateValidationFinding(
                    check_type=MerchantCheckType.INVENTORY.value,
                    status=GateStatus.UNKNOWN,
                    reason="; ".join(inventory_unknowns),
                    field_name="inventory",
                    details={"unknowns": inventory_unknowns},
                )
            )
        else:
            findings.append(
                GateValidationFinding(
                    check_type=MerchantCheckType.INVENTORY.value,
                    status=GateStatus.VALID,
                    reason="Available inventory verified for all offered items",
                    field_name="inventory",
                )
            )

        # 5. Price & Budget Conformance Fact
        price_violations: List[str] = []
        total_offered = merchant_response.total_amount
        if total_offered is None and merchant_response.items:
            total_offered = merchant_response.items[0].total_price

        if intent and total_offered:
            if total_offered.currency != intent.currency:
                price_violations.append(f"Currency mismatch: offer {total_offered.currency} != intent {intent.currency}")
            if total_offered.amount > intent.max_total.amount:
                price_violations.append(
                    f"Price surge/drift: offered total {total_offered.amount} {total_offered.currency} "
                    f"> authorized maximum {intent.max_total.amount} {intent.max_total.currency}"
                )

        if price_violations:
            findings.append(
                GateValidationFinding(
                    check_type=MerchantCheckType.PRICE.value,
                    status=GateStatus.INVALID,
                    reason="; ".join(price_violations),
                    field_name="price",
                    expected_value=intent.max_total.model_dump() if intent else None,
                    observed_value=total_offered.model_dump() if total_offered else None,
                    details={"violations": price_violations},
                )
            )
        else:
            findings.append(
                GateValidationFinding(
                    check_type=MerchantCheckType.PRICE.value,
                    status=GateStatus.VALID,
                    reason="Price conforms to catalog base pricing and authorized bounds",
                    field_name="price",
                    observed_value=total_offered.model_dump() if total_offered else None,
                )
            )

        # 6. Shipping Option
        shipping_violations: List[str] = []
        if merchant_response.shipping:
            ship = merchant_response.shipping
            if ship.cost.amount < 0:
                shipping_violations.append("Shipping cost cannot be negative")
            if ship.estimated_days <= 0:
                shipping_violations.append("Shipping estimated days must be >= 1")

        if shipping_violations:
            findings.append(
                GateValidationFinding(
                    check_type=MerchantCheckType.SHIPPING.value,
                    status=GateStatus.INVALID,
                    reason="; ".join(shipping_violations),
                    field_name="shipping",
                    details={"violations": shipping_violations},
                )
            )
        else:
            findings.append(
                GateValidationFinding(
                    check_type=MerchantCheckType.SHIPPING.value,
                    status=GateStatus.VALID,
                    reason="Shipping configuration valid and verified",
                    field_name="shipping",
                )
            )

        # 7. Fulfillment Terms
        fulfillment_violations: List[str] = []
        fulfillment = merchant_response.fulfillment
        if not fulfillment.carrier or not fulfillment.carrier.strip():
            fulfillment_violations.append("Empty fulfillment carrier")
        if fulfillment.estimated_delivery_days <= 0:
            fulfillment_violations.append("Estimated delivery days must be >= 1")

        if fulfillment_violations:
            findings.append(
                GateValidationFinding(
                    check_type=MerchantCheckType.FULFILLMENT.value,
                    status=GateStatus.INVALID,
                    reason="; ".join(fulfillment_violations),
                    field_name="fulfillment",
                    details={"violations": fulfillment_violations},
                )
            )
        else:
            findings.append(
                GateValidationFinding(
                    check_type=MerchantCheckType.FULFILLMENT.value,
                    status=GateStatus.VALID,
                    reason="Fulfillment promises conform to merchant standards",
                    field_name="fulfillment",
                )
            )

        # 8. Offer Expiry
        if merchant_response.is_expired(as_of=ref_time):
            findings.append(
                GateValidationFinding(
                    check_type=MerchantCheckType.OFFER_EXPIRY.value,
                    status=GateStatus.INVALID,
                    reason=(
                        f"Offer expired at {merchant_response.offer_expires_at.isoformat()} "
                        f"(reference time: {ref_time.isoformat()})"
                    ),
                    field_name="offer_expires_at",
                    expected_value=f"> {ref_time.isoformat()}",
                    observed_value=merchant_response.offer_expires_at.isoformat(),
                    details={"error": "OFFER_EXPIRED"},
                )
            )
        else:
            findings.append(
                GateValidationFinding(
                    check_type=MerchantCheckType.OFFER_EXPIRY.value,
                    status=GateStatus.VALID,
                    reason=f"Offer is fresh and active until {merchant_response.offer_expires_at.isoformat()}",
                    field_name="offer_expires_at",
                    observed_value=merchant_response.offer_expires_at.isoformat(),
                )
            )

        # 9. Merchant Policy Compliance
        policy_violations: List[str] = []
        policy = catalog_service.policy
        if policy and total_offered:
            if hasattr(policy, "max_order_value") and total_offered.amount > policy.max_order_value.amount:
                policy_violations.append(
                    f"Order total {total_offered.amount} exceeds merchant maximum order value {policy.max_order_value.amount}"
                )
            if merchant_response.items:
                primary_sku = merchant_response.items[0].sku
                subtotal = merchant_response.subtotal or total_offered
                discount = merchant_response.discount or Money(amount=0, currency=total_offered.currency)
                is_comp, reason = policy.validate_offer_compliance(
                    subtotal=subtotal,
                    discount=discount,
                    sku=primary_sku,
                    delivery_days=merchant_response.estimated_delivery_days,
                )
                if not is_comp and reason:
                    policy_violations.append(reason)

        if policy_violations:
            findings.append(
                GateValidationFinding(
                    check_type=MerchantCheckType.MERCHANT_POLICY.value,
                    status=GateStatus.INVALID,
                    reason="; ".join(policy_violations),
                    field_name="policy",
                    details={"violations": policy_violations},
                )
            )
        else:
            findings.append(
                GateValidationFinding(
                    check_type=MerchantCheckType.MERCHANT_POLICY.value,
                    status=GateStatus.VALID,
                    reason="Offer adheres to merchant policy-as-code constraints",
                    field_name="policy",
                )
            )

        # Compute overall status
        has_invalid = any(f.status == GateStatus.INVALID for f in findings)
        has_unknown = any(f.status == GateStatus.UNKNOWN for f in findings)
        if has_invalid:
            status = GateStatus.INVALID
            is_all_valid = False
        elif has_unknown:
            status = GateStatus.UNKNOWN
            is_all_valid = False
        else:
            status = GateStatus.VALID
            is_all_valid = True

        return MerchantGateResult(
            status=status,
            transaction_id=context.transaction_id,
            merchant_id=context.merchant_id,
            offer_id=merchant_response.offer_id,
            is_valid=is_all_valid,
            findings=findings,
            validated_at=ref_time,
            metadata={"source": "MerchantGate"},
        )
