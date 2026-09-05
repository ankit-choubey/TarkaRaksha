"""
Merchant integrity models and deterministic verifiers for TarkaRaksha (I4).

Validates:
1. Dynamic offer expiry (expired offers rejected, refresh requested)
2. Inventory integrity (detecting stock depletion and state transitions)
3. Fulfillment integrity (detecting temporal delivery drift and constraint breaches)
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from backend.app.domain.models.enums import IntegrityStatus
from backend.app.domain.rules.base import RuleResult
from backend.app.domain.merchant.contracts import MerchantOffer, InventoryStatus


class OfferVerificationStatus(str, Enum):
    """Status classification for offer verification."""
    VALID = "VALID"
    EXPIRED = "EXPIRED"
    INVENTORY_DEPLETED = "INVENTORY_DEPLETED"
    FULFILLMENT_BREACH = "FULFILLMENT_BREACH"
    PRICE_TAMPERED = "PRICE_TAMPERED"


class OfferVerificationResult(BaseModel):
    """
    Deterministic result of validating a merchant offer against constraints and state.
    """
    verification_type: str
    status: OfferVerificationStatus
    is_valid: bool
    integrity_status: IntegrityStatus
    action_recommended: str
    violation: Optional[str] = None
    expected: Optional[Any] = None
    observed: Optional[Any] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    rule_result: Optional[RuleResult] = None

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )


class MerchantIntegrityVerifier:
    """
    Deterministic verification engine for merchant-side offers, inventory, and fulfillment.
    
    Adheres to core safety principles:
    - Never converts DRIFT or UNKNOWN into PASS.
    - Expired offers cannot silently become valid.
    - Preserves deterministic rule results.
    """

    @staticmethod
    def verify_offer_expiry(
        offer: MerchantOffer,
        current_time: Optional[datetime] = None,
    ) -> OfferVerificationResult:
        """
        Verify if a merchant offer is still within its validity window.
        If expired, rejects the offer and signals REQUEST_REFRESH.
        """
        if current_time is None:
            current_time = datetime.now(timezone.utc)
        elif current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)

        if offer.is_expired(as_of=current_time):
            rule_res = RuleResult(
                rule_name="MerchantOfferExpiryRule",
                status=IntegrityStatus.DRIFT,
                violation="EXPIRED_OFFER_REJECTED",
                expected=f"valid_until > {current_time.isoformat()}",
                observed=offer.offer_expires_at.isoformat(),
                explanation="Merchant offer has expired. Old offers must not be accepted; request refresh.",
            )
            return OfferVerificationResult(
                verification_type="OFFER_EXPIRY",
                status=OfferVerificationStatus.EXPIRED,
                is_valid=False,
                integrity_status=IntegrityStatus.DRIFT,
                action_recommended="REQUEST_REFRESH",
                violation="EXPIRED_OFFER_REJECTED",
                expected=f"> {current_time.isoformat()}",
                observed=offer.offer_expires_at.isoformat(),
                details={"offer_id": offer.offer_id, "expired_at": offer.offer_expires_at.isoformat()},
                rule_result=rule_res,
            )

        rule_res = RuleResult(
            rule_name="MerchantOfferExpiryRule",
            status=IntegrityStatus.PASS,
            explanation="Merchant offer is currently valid and unexpired.",
        )
        return OfferVerificationResult(
            verification_type="OFFER_EXPIRY",
            status=OfferVerificationStatus.VALID,
            is_valid=True,
            integrity_status=IntegrityStatus.PASS,
            action_recommended="PROCEED",
            rule_result=rule_res,
        )

    @staticmethod
    def verify_inventory_integrity(
        offer: MerchantOffer,
        current_stock: Optional[int] = None,
        required_quantity: int = 1,
        authoritative_evidence_available: bool = True,
    ) -> OfferVerificationResult:
        """
        Verify inventory integrity against current stock and availability states.
        Detects transitions from AVAILABLE to SOLD_OUT or insufficient stock.
        """
        if not authoritative_evidence_available or current_stock is None:
            rule_res = RuleResult(
                rule_name="MerchantInventoryIntegrityRule",
                status=IntegrityStatus.UNKNOWN,
                violation="INSUFFICIENT_STOCK_EVIDENCE",
                explanation="No authoritative stock evidence available to verify merchant inventory claims.",
            )
            return OfferVerificationResult(
                verification_type="INVENTORY_INTEGRITY",
                status=OfferVerificationStatus.INVENTORY_DEPLETED,
                is_valid=False,
                integrity_status=IntegrityStatus.UNKNOWN,
                action_recommended="VERIFY_INVENTORY_AUTHORITATIVE",
                violation="INSUFFICIENT_STOCK_EVIDENCE",
                rule_result=rule_res,
            )

        # Check if offer stated available but stock is insufficient
        is_depleted = current_stock < required_quantity or offer.inventory_status == InventoryStatus.SOLD_OUT

        if is_depleted:
            rule_res = RuleResult(
                rule_name="MerchantInventoryIntegrityRule",
                status=IntegrityStatus.DRIFT,
                violation="INVENTORY_STATE_DRIFT",
                expected=f">= {required_quantity} available",
                observed=f"{current_stock} available (status={offer.inventory_status.value})",
                explanation="Observed inventory state contradicts offer availability. Stock depleted or sold out.",
            )
            return OfferVerificationResult(
                verification_type="INVENTORY_INTEGRITY",
                status=OfferVerificationStatus.INVENTORY_DEPLETED,
                is_valid=False,
                integrity_status=IntegrityStatus.DRIFT,
                action_recommended="RE_EVALUATE_INVENTORY",
                violation="INVENTORY_STATE_DRIFT",
                expected=f">= {required_quantity}",
                observed=current_stock,
                details={
                    "offer_id": offer.offer_id,
                    "claimed_inventory_status": offer.inventory_status.value,
                    "current_stock": current_stock,
                    "required_quantity": required_quantity,
                },
                rule_result=rule_res,
            )

        rule_res = RuleResult(
            rule_name="MerchantInventoryIntegrityRule",
            status=IntegrityStatus.PASS,
            explanation="Inventory is available and satisfies required quantity.",
        )
        return OfferVerificationResult(
            verification_type="INVENTORY_INTEGRITY",
            status=OfferVerificationStatus.VALID,
            is_valid=True,
            integrity_status=IntegrityStatus.PASS,
            action_recommended="PROCEED",
            details={"current_stock": current_stock, "required_quantity": required_quantity},
            rule_result=rule_res,
        )

    @staticmethod
    def verify_fulfillment_integrity(
        offer: MerchantOffer,
        buyer_max_delivery_days: Optional[int] = None,
        buyer_required_carrier: Optional[str] = None,
    ) -> OfferVerificationResult:
        """
        Verify fulfillment terms against buyer intent constraints.
        Detects TEMPORAL_FULFILLMENT_DRIFT or carrier mismatches.
        """
        # Check delivery window constraint
        if buyer_max_delivery_days is not None:
            if offer.fulfillment.estimated_delivery_days > buyer_max_delivery_days:
                rule_res = RuleResult(
                    rule_name="MerchantFulfillmentIntegrityRule",
                    status=IntegrityStatus.DRIFT,
                    violation="TEMPORAL_FULFILLMENT_DRIFT",
                    expected=f"delivery_days <= {buyer_max_delivery_days}",
                    observed=f"delivery_days = {offer.fulfillment.estimated_delivery_days}",
                    explanation=f"Estimated delivery time ({offer.fulfillment.estimated_delivery_days} days) exceeds buyer constraint ({buyer_max_delivery_days} days).",
                )
                return OfferVerificationResult(
                    verification_type="FULFILLMENT_INTEGRITY",
                    status=OfferVerificationStatus.FULFILLMENT_BREACH,
                    is_valid=False,
                    integrity_status=IntegrityStatus.DRIFT,
                    action_recommended="RENEGOTIATE_FULFILLMENT",
                    violation="TEMPORAL_FULFILLMENT_DRIFT",
                    expected=buyer_max_delivery_days,
                    observed=offer.fulfillment.estimated_delivery_days,
                    details={
                        "buyer_max_delivery_days": buyer_max_delivery_days,
                        "offered_delivery_days": offer.fulfillment.estimated_delivery_days,
                    },
                    rule_result=rule_res,
                )

        # Check carrier requirement
        if buyer_required_carrier is not None:
            if offer.fulfillment.carrier.strip().lower() != buyer_required_carrier.strip().lower():
                rule_res = RuleResult(
                    rule_name="MerchantFulfillmentIntegrityRule",
                    status=IntegrityStatus.DRIFT,
                    violation="CARRIER_MISMATCH",
                    expected=buyer_required_carrier,
                    observed=offer.fulfillment.carrier,
                    explanation=f"Offered carrier '{offer.fulfillment.carrier}' does not match required carrier '{buyer_required_carrier}'.",
                )
                return OfferVerificationResult(
                    verification_type="FULFILLMENT_INTEGRITY",
                    status=OfferVerificationStatus.FULFILLMENT_BREACH,
                    is_valid=False,
                    integrity_status=IntegrityStatus.DRIFT,
                    action_recommended="RENEGOTIATE_FULFILLMENT",
                    violation="CARRIER_MISMATCH",
                    expected=buyer_required_carrier,
                    observed=offer.fulfillment.carrier,
                    details={
                        "buyer_required_carrier": buyer_required_carrier,
                        "offered_carrier": offer.fulfillment.carrier,
                    },
                    rule_result=rule_res,
                )

        rule_res = RuleResult(
            rule_name="MerchantFulfillmentIntegrityRule",
            status=IntegrityStatus.PASS,
            explanation="Fulfillment terms satisfy buyer delivery constraints.",
        )
        return OfferVerificationResult(
            verification_type="FULFILLMENT_INTEGRITY",
            status=OfferVerificationStatus.VALID,
            is_valid=True,
            integrity_status=IntegrityStatus.PASS,
            action_recommended="PROCEED",
            details={
                "estimated_delivery_days": offer.fulfillment.estimated_delivery_days,
                "carrier": offer.fulfillment.carrier,
            },
            rule_result=rule_res,
        )

    @classmethod
    def verify_all(
        cls,
        offer: MerchantOffer,
        current_time: Optional[datetime] = None,
        buyer_max_delivery_days: Optional[int] = None,
        buyer_required_carrier: Optional[str] = None,
        current_stock: Optional[int] = None,
        required_quantity: int = 1,
        authoritative_evidence_available: bool = True,
    ) -> List[OfferVerificationResult]:
        """
        Perform all integrity verifications on a merchant offer.
        """
        results = [
            cls.verify_offer_expiry(offer, current_time=current_time),
            cls.verify_inventory_integrity(
                offer,
                current_stock=current_stock,
                required_quantity=required_quantity,
                authoritative_evidence_available=authoritative_evidence_available,
            ),
            cls.verify_fulfillment_integrity(
                offer,
                buyer_max_delivery_days=buyer_max_delivery_days,
                buyer_required_carrier=buyer_required_carrier,
            ),
        ]
        return results
