"""
Evidence Extension Layer for TarkaRaksha (I1).
Provides additive extensions for:
1. Evidence Freshness Metadata & Deterministic Freshness Evaluation.
2. Merchant Offer Object representation with provenance.
3. Deterministic Integrity Delta calculation (Money subunit safe, zero float).
4. Freshness-aware deterministic evidence inspection.
"""
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.domain.models.enums import EvidenceAuthority, EvidenceSource
from backend.app.domain.models.evidence import Evidence
from backend.app.domain.models.money import Money


class FreshnessStatus(str, Enum):
    """
    Deterministic freshness status of an evidence record.
    FRESH: Current reference time is within valid_until (or source observed within freshness window).
    STALE: Evidence is beyond expected freshness threshold but not yet expired.
    EXPIRED: Reference time is strictly beyond valid_until.
    UNKNOWN: Timestamps are missing, ambiguous, or unverifiable.
    """
    FRESH = "FRESH"
    STALE = "STALE"
    EXPIRED = "EXPIRED"
    UNKNOWN = "UNKNOWN"


class EvidenceFreshnessMetadata(BaseModel):
    """
    Additive metadata container recording temporal validity and freshness of evidence.
    Deterministic: status is calculated from explicit reference timestamps, never AI confidence.
    """
    observed_at: datetime
    valid_until: Optional[datetime] = None
    source_timestamp: Optional[datetime] = None
    freshness_status: FreshnessStatus = FreshnessStatus.UNKNOWN

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )

    @field_validator("observed_at", "valid_until", "source_timestamp", mode="before")
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


def evaluate_evidence_freshness(
    observed_at: datetime,
    valid_until: Optional[datetime] = None,
    source_timestamp: Optional[datetime] = None,
    reference_time: Optional[datetime] = None,
    stale_threshold_seconds: Optional[int] = None,
) -> EvidenceFreshnessMetadata:
    """
    Deterministically computes FreshnessStatus for given timestamps and an explicit reference time.

    Invariants:
    - If reference_time > valid_until -> EXPIRED
    - If valid_until is provided and reference_time <= valid_until:
        - If stale_threshold_seconds is specified and (reference_time - observed_at) > stale_threshold -> STALE
        - Otherwise -> FRESH
    - If valid_until is missing:
        - If stale_threshold_seconds is specified:
            - If (reference_time - observed_at) > stale_threshold -> STALE
            - Otherwise -> FRESH
        - Otherwise -> UNKNOWN (cannot infer expiry without valid_until or explicit threshold)
    - If reference_time is None, defaults to observed_at (or raises if caller requires explicit clock).
    """
    ref = reference_time or observed_at
    if ref.tzinfo is None:
        raise ValueError("reference_time must be timezone-aware (e.g. UTC)")
    if observed_at.tzinfo is None:
        raise ValueError("observed_at must be timezone-aware (e.g. UTC)")
    if valid_until is not None and valid_until.tzinfo is None:
        raise ValueError("valid_until must be timezone-aware (e.g. UTC)")
    if source_timestamp is not None and source_timestamp.tzinfo is None:
        raise ValueError("source_timestamp must be timezone-aware (e.g. UTC)")

    # 1. Check expiration if valid_until is explicitly provided
    if valid_until is not None:
        if ref > valid_until:
            status = FreshnessStatus.EXPIRED
        elif stale_threshold_seconds is not None:
            age = (ref - observed_at).total_seconds()
            if age > stale_threshold_seconds:
                status = FreshnessStatus.STALE
            else:
                status = FreshnessStatus.FRESH
        else:
            status = FreshnessStatus.FRESH
    elif stale_threshold_seconds is not None:
        age = (ref - observed_at).total_seconds()
        if age < 0:
            status = FreshnessStatus.UNKNOWN
        elif age > stale_threshold_seconds:
            status = FreshnessStatus.STALE
        else:
            status = FreshnessStatus.FRESH
    else:
        status = FreshnessStatus.UNKNOWN

    return EvidenceFreshnessMetadata(
        observed_at=observed_at,
        valid_until=valid_until,
        source_timestamp=source_timestamp,
        freshness_status=status,
    )


def assess_evidence_freshness_for_constraint(
    evidence: Evidence,
    reference_time: datetime,
    max_age_seconds: Optional[int] = None,
    require_fresh: bool = True,
) -> tuple[FreshnessStatus, bool, Optional[str]]:
    """
    Evaluates evidence freshness against an explicit reference timestamp for a required constraint.
    
    Safety Guarantee:
    - If require_fresh is True, STALE or EXPIRED evidence cannot silently produce an accepted observation.
    - Returns (freshness_status, is_acceptable, rejection_reason).
    - EXPIRED -> is_acceptable=False, reason="Evidence is EXPIRED"
    - STALE -> is_acceptable=False (if require_fresh), reason="Evidence is STALE"
    - UNKNOWN -> is_acceptable=False (if require_fresh and no unverified evidence allowed), reason="Evidence freshness is UNKNOWN"
    - FRESH -> is_acceptable=True, reason=None
    """
    # Extract metadata from evidence provenance if present
    prov = evidence.provenance or {}
    valid_until = prov.get("valid_until")
    if isinstance(valid_until, str):
        valid_until = datetime.fromisoformat(valid_until)
    source_ts = prov.get("source_timestamp")
    if isinstance(source_ts, str):
        source_ts = datetime.fromisoformat(source_ts)

    meta = evaluate_evidence_freshness(
        observed_at=evidence.observed_at,
        valid_until=valid_until,
        source_timestamp=source_ts,
        reference_time=reference_time,
        stale_threshold_seconds=max_age_seconds,
    )

    if meta.freshness_status == FreshnessStatus.EXPIRED:
        return (FreshnessStatus.EXPIRED, False, f"Evidence '{evidence.evidence_id}' is EXPIRED at reference time {reference_time.isoformat()}")
    if meta.freshness_status == FreshnessStatus.STALE and require_fresh:
        return (FreshnessStatus.STALE, False, f"Evidence '{evidence.evidence_id}' is STALE at reference time {reference_time.isoformat()}")
    if meta.freshness_status == FreshnessStatus.UNKNOWN and require_fresh:
        return (FreshnessStatus.UNKNOWN, False, f"Evidence '{evidence.evidence_id}' freshness cannot be proven (UNKNOWN)")

    return (meta.freshness_status, True, None)



class MerchantOffer(BaseModel):
    """
    Structured domain representation of a merchant commercial offer.
    Input to deterministic integrity evaluation; does NOT constitute proof of payment.
    Monetary values use Money integer minor units (paise/cents).
    """
    offer_id: str
    merchant_id: str
    sku: str
    quantity: int
    unit_price: Money
    discount: Money
    shipping: Money
    tax: Money
    total: Money
    currency: str = "INR"
    inventory_status: str
    delivery_estimate: str
    offer_created_at: datetime
    offer_expires_at: datetime
    merchant_policy_version: str = "1.0.0"
    evidence_refs: List[str] = Field(default_factory=list)

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )

    @field_validator("quantity")
    @classmethod
    def validate_positive_quantity(cls, v: Any) -> int:
        if isinstance(v, bool) or not isinstance(v, int) or v <= 0:
            raise ValueError("MerchantOffer quantity must be a positive integer >= 1")
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
            raise ValueError("MerchantOffer timestamps must be timezone-aware (e.g. UTC)")
        return dt

    @field_validator("total")
    @classmethod
    def validate_total_math(cls, v: Money, info: Any) -> Money:
        # In Pydantic v2 info.data contains previously validated fields
        data = info.data
        if "unit_price" in data and "quantity" in data and "discount" in data and "shipping" in data and "tax" in data:
            unit_price: Money = data["unit_price"]
            qty: int = data["quantity"]
            discount: Money = data["discount"]
            shipping: Money = data["shipping"]
            tax: Money = data["tax"]
            
            subtotal = unit_price * qty
            expected_total_amount = subtotal.amount - discount.amount + shipping.amount + tax.amount
            if v.amount != expected_total_amount:
                raise ValueError(
                    f"MerchantOffer total {v.amount} does not match computed breakdown "
                    f"(subtotal {subtotal.amount} - discount {discount.amount} + shipping {shipping.amount} + tax {tax.amount} = {expected_total_amount})"
                )
            if v.currency != unit_price.currency:
                raise ValueError(f"Currency mismatch in MerchantOffer total ({v.currency} vs {unit_price.currency})")
        return v

    def to_evidence(self) -> List[Evidence]:
        """
        Converts the MerchantOffer into normalized Evidence records with provenance.
        Authority is MERCHANT_ATTESTED (cannot override AUTHORITATIVE payment gateway truth).
        """
        ev_offer = Evidence(
            evidence_id=f"ev_offer_{self.offer_id}",
            intent_id="N/A",  # Bound during session ingestion
            source=EvidenceSource.MERCHANT,
            authority=EvidenceAuthority.MERCHANT_ATTESTED,
            field_name="merchant_offer",
            field_value=self.model_dump(),
            observed_at=self.offer_created_at,
            raw_reference=self.offer_id,
            provenance={
                "merchant_id": self.merchant_id,
                "policy_version": self.merchant_policy_version,
                "evidence_refs": self.evidence_refs,
            },
        )
        ev_total = Evidence(
            evidence_id=f"ev_offer_total_{self.offer_id}",
            intent_id="N/A",
            source=EvidenceSource.MERCHANT,
            authority=EvidenceAuthority.MERCHANT_ATTESTED,
            field_name="total_amount",
            field_value=self.total,
            observed_at=self.offer_created_at,
            raw_reference=self.offer_id,
            provenance={"offer_id": self.offer_id, "evidence_refs": self.evidence_refs},
        )
        ev_items = Evidence(
            evidence_id=f"ev_offer_items_{self.offer_id}",
            intent_id="N/A",
            source=EvidenceSource.MERCHANT,
            authority=EvidenceAuthority.MERCHANT_ATTESTED,
            field_name="executed_items",
            field_value=[{"sku": self.sku, "quantity": self.quantity}],
            observed_at=self.offer_created_at,
            raw_reference=self.offer_id,
            provenance={"offer_id": self.offer_id, "evidence_refs": self.evidence_refs},
        )
        return [ev_offer, ev_total, ev_items]


class IntegrityDelta(BaseModel):
    """
    Deterministic difference representation between authorized baseline constraint and observed reality.
    Uses strict integer minor units for Money values (zero floating-point arithmetic).
    """
    violated_constraint: str
    baseline: Any
    observed: Any
    delta: Any
    is_violation: bool
    explanation: str

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )


def compute_economic_delta(
    authorized_limit: Money,
    observed_amount: Money,
    constraint_name: str = "max_total",
) -> IntegrityDelta:
    """
    Deterministically computes the financial delta between authorized limit and observed amount.
    Strictly integer-based; returns Money delta.
    """
    if authorized_limit.currency != observed_amount.currency:
        return IntegrityDelta(
            violated_constraint=constraint_name,
            baseline=authorized_limit.model_dump(),
            observed=observed_amount.model_dump(),
            delta=None,
            is_violation=True,
            explanation=f"Currency mismatch: authorized {authorized_limit.currency} vs observed {observed_amount.currency}",
        )

    diff_amount = observed_amount.amount - authorized_limit.amount
    delta_money = Money(amount=diff_amount, currency=authorized_limit.currency)
    is_violation = diff_amount > 0

    if is_violation:
        explanation = f"Observed amount exceeds authorized baseline by {diff_amount} {authorized_limit.currency} minor units"
    else:
        explanation = f"Observed amount is within authorized baseline (diff: {diff_amount} minor units)"

    return IntegrityDelta(
        violated_constraint=constraint_name,
        baseline=authorized_limit.model_dump(),
        observed=observed_amount.model_dump(),
        delta=delta_money.model_dump(),
        is_violation=is_violation,
        explanation=explanation,
    )


def compute_quantity_delta(
    authorized_qty: int,
    observed_qty: int,
    sku: str,
) -> IntegrityDelta:
    """
    Deterministically computes quantity delta for an item SKU.
    """
    diff = observed_qty - authorized_qty
    is_violation = diff != 0

    if diff > 0:
        explanation = f"Observed quantity for SKU '{sku}' exceeds authorized by +{diff}"
    elif diff < 0:
        explanation = f"Observed quantity for SKU '{sku}' is deficient by {diff}"
    else:
        explanation = f"Observed quantity matches authorized quantity ({authorized_qty})"

    return IntegrityDelta(
        violated_constraint=f"item_quantity:{sku}",
        baseline=authorized_qty,
        observed=observed_qty,
        delta=diff,
        is_violation=is_violation,
        explanation=explanation,
    )
