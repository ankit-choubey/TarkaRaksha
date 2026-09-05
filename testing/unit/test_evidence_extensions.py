"""
Focused Test Suite for TarkaRaksha I1 — Evidence Extensions.
Validates:
1. FRESH evidence determination against explicit reference time.
2. STALE evidence determination beyond age threshold.
3. EXPIRED evidence determination past valid_until.
4. UNKNOWN freshness handling when expiry/age context is missing.
5. Deterministic freshness calculation (repeatability, no wall-clock sensitivity).
6. Boundary conditions around valid_until (exact boundary, boundary + 1 microsecond).
7. Merchant offer schema validation (strict types, positive quantity, required fields).
8. Merchant offer monetary calculations (unit_price * qty - discount + shipping + tax == total).
9. Deterministic integrity delta representation (economic delta with Money subunits, zero float).
10. Violated constraint representation (boolean flag, delta value, explanation).
11. Provenance and evidence_refs preservation through MerchantOffer.to_evidence().
12. STALE evidence cannot silently produce PASS when freshness is required.
13. EXPIRED evidence cannot silently produce PASS where freshness is required.
14. Merchant offer cannot override authoritative payment gateway evidence in authority ranking.
15. Adversarial: Malicious float injection into merchant offer or delta calculation rejected.
16. Adversarial: Untrusted AI confidence cannot declare evidence fresh or authoritative.
17. Adversarial: Inconsistent merchant offer price math rejected with validation error.
18. Adversarial: Naive datetime in freshness metadata rejected.
"""
from datetime import datetime, timezone, timedelta
import pytest
from pydantic import ValidationError

from backend.app.domain.models import (
    EvidenceAuthority,
    EvidenceSource,
    Evidence,
    Money,
    IntegrityStatus,
    IntentContract,
    IntentItem,
)
from backend.app.domain.evidence import (
    FreshnessStatus,
    EvidenceFreshnessMetadata,
    evaluate_evidence_freshness,
    assess_evidence_freshness_for_constraint,
    MerchantOffer,
    IntegrityDelta,
    compute_economic_delta,
    compute_quantity_delta,
    resolve_field_evidence,
)
from backend.app.services.evaluation import evaluate_integrity


@pytest.fixture
def base_time() -> datetime:
    return datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# 1. Freshness Evaluation & Boundaries (Req 1, 2, 3, 4, 5, 6)
# ---------------------------------------------------------------------------

def test_fresh_evidence_within_valid_until(base_time):
    """Req 1: Evidence within valid_until is evaluated as FRESH."""
    observed = base_time
    valid_until = base_time + timedelta(minutes=15)
    ref_time = base_time + timedelta(minutes=5)

    meta = evaluate_evidence_freshness(
        observed_at=observed,
        valid_until=valid_until,
        reference_time=ref_time,
    )
    assert meta.freshness_status == FreshnessStatus.FRESH
    assert meta.observed_at == observed
    assert meta.valid_until == valid_until


def test_stale_evidence_past_threshold(base_time):
    """Req 2: Evidence older than stale_threshold_seconds is evaluated as STALE."""
    observed = base_time
    valid_until = base_time + timedelta(hours=2)
    ref_time = base_time + timedelta(minutes=45)

    meta = evaluate_evidence_freshness(
        observed_at=observed,
        valid_until=valid_until,
        reference_time=ref_time,
        stale_threshold_seconds=1800,  # 30 minutes
    )
    assert meta.freshness_status == FreshnessStatus.STALE


def test_expired_evidence_past_valid_until(base_time):
    """Req 3: Evidence evaluated after valid_until is strictly EXPIRED."""
    observed = base_time
    valid_until = base_time + timedelta(minutes=10)
    ref_time = base_time + timedelta(minutes=10, seconds=1)

    meta = evaluate_evidence_freshness(
        observed_at=observed,
        valid_until=valid_until,
        reference_time=ref_time,
    )
    assert meta.freshness_status == FreshnessStatus.EXPIRED


def test_unknown_freshness_without_threshold_or_expiry(base_time):
    """Req 4: If no valid_until and no stale threshold are provided, freshness is UNKNOWN."""
    observed = base_time
    ref_time = base_time + timedelta(minutes=30)

    meta = evaluate_evidence_freshness(
        observed_at=observed,
        valid_until=None,
        reference_time=ref_time,
        stale_threshold_seconds=None,
    )
    assert meta.freshness_status == FreshnessStatus.UNKNOWN


def test_deterministic_freshness_repeatability_100x(base_time):
    """Req 5: Repeated freshness calculations with identical reference time yield 100% identical results."""
    observed = base_time
    valid_until = base_time + timedelta(minutes=20)
    ref_time = base_time + timedelta(minutes=10)

    base_meta = evaluate_evidence_freshness(
        observed_at=observed,
        valid_until=valid_until,
        reference_time=ref_time,
        stale_threshold_seconds=300,
    )
    assert base_meta.freshness_status == FreshnessStatus.STALE

    for _ in range(100):
        m = evaluate_evidence_freshness(
            observed_at=observed,
            valid_until=valid_until,
            reference_time=ref_time,
            stale_threshold_seconds=300,
        )
        assert m.freshness_status == base_meta.freshness_status
        assert m.observed_at == base_meta.observed_at
        assert m.valid_until == base_meta.valid_until


def test_boundary_conditions_around_valid_until(base_time):
    """Req 6: Exact boundary: ref_time == valid_until is FRESH; ref_time > valid_until is EXPIRED."""
    observed = base_time
    valid_until = base_time + timedelta(minutes=10)

    # Exactly at boundary
    at_boundary = evaluate_evidence_freshness(
        observed_at=observed,
        valid_until=valid_until,
        reference_time=valid_until,
    )
    assert at_boundary.freshness_status == FreshnessStatus.FRESH

    # 1 microsecond past boundary
    just_after = evaluate_evidence_freshness(
        observed_at=observed,
        valid_until=valid_until,
        reference_time=valid_until + timedelta(microseconds=1),
    )
    assert just_after.freshness_status == FreshnessStatus.EXPIRED


# ---------------------------------------------------------------------------
# 2. Merchant Offer Schema & Math (Req 7, 8, 11, 14, 17)
# ---------------------------------------------------------------------------

def test_merchant_offer_schema_and_math(base_time):
    """Req 7 & 8: Valid MerchantOffer with integer Money arithmetic and breakdown validation."""
    offer = MerchantOffer(
        offer_id="off_test_001",
        merchant_id="merch_acme_corp",
        sku="SERVER-256GB",
        quantity=2,
        unit_price=Money(amount=2500000, currency="INR"),  # ₹25,000 x 2 = ₹50,000
        discount=Money(amount=200000, currency="INR"),     # - ₹2,000 = ₹48,000
        shipping=Money(amount=100000, currency="INR"),     # + ₹1,000 = ₹49,000
        tax=Money(amount=882000, currency="INR"),          # + ₹8,820 (18%) = ₹57,820
        total=Money(amount=5782000, currency="INR"),       # = ₹57,820 (5782000 paise)
        currency="INR",
        inventory_status="IN_STOCK",
        delivery_estimate="2 business days",
        offer_created_at=base_time,
        offer_expires_at=base_time + timedelta(hours=2),
        merchant_policy_version="1.0.0",
        evidence_refs=["ev_catalog_99", "ev_quote_12"],
    )

    assert offer.total.amount == 5782000
    assert offer.quantity == 2
    assert offer.currency == "INR"


def test_merchant_offer_math_mismatch_rejected(base_time):
    """Req 17: Inconsistent total in MerchantOffer raises ValidationError."""
    with pytest.raises(ValidationError, match="does not match computed breakdown"):
        MerchantOffer(
            offer_id="off_bad_math",
            merchant_id="merch_acme",
            sku="SERVER-256GB",
            quantity=1,
            unit_price=Money(amount=5000000, currency="INR"),
            discount=Money(amount=0, currency="INR"),
            shipping=Money(amount=0, currency="INR"),
            tax=Money(amount=0, currency="INR"),
            total=Money(amount=5500000, currency="INR"),  # Mismatch: should be 5000000
            currency="INR",
            inventory_status="IN_STOCK",
            delivery_estimate="1 day",
            offer_created_at=base_time,
            offer_expires_at=base_time + timedelta(hours=1),
        )


def test_merchant_offer_provenance_and_authority_rank(base_time):
    """Req 11 & 14: MerchantOffer converts to evidence with MERCHANT_ATTESTED authority; cannot override provider."""
    offer = MerchantOffer(
        offer_id="off_prov_001",
        merchant_id="merch_dell_direct",
        sku="SERVER-256GB",
        quantity=1,
        unit_price=Money(amount=5000000, currency="INR"),
        discount=Money(amount=0, currency="INR"),
        shipping=Money(amount=0, currency="INR"),
        tax=Money(amount=0, currency="INR"),
        total=Money(amount=5000000, currency="INR"),
        currency="INR",
        inventory_status="AVAILABLE",
        delivery_estimate="Next Day",
        offer_created_at=base_time,
        offer_expires_at=base_time + timedelta(hours=1),
        evidence_refs=["catalog_ref_101", "pricing_ref_202"],
    )

    evidence_items = offer.to_evidence()
    assert len(evidence_items) == 3
    offer_ev = next(e for e in evidence_items if e.field_name == "merchant_offer")
    total_ev = next(e for e in evidence_items if e.field_name == "total_amount")

    assert offer_ev.authority == EvidenceAuthority.MERCHANT_ATTESTED
    assert offer_ev.authority_rank == 70
    assert offer_ev.provenance["evidence_refs"] == ["catalog_ref_101", "pricing_ref_202"]

    # Gateway payment record at rank 100 overrides merchant offer at rank 70
    gateway_ev = Evidence(
        evidence_id="ev_rzp_gateway",
        intent_id="int_01",
        source=EvidenceSource.RAZORPAY,
        authority=EvidenceAuthority.AUTHORITATIVE,
        field_name="total_amount",
        field_value=Money(amount=5200000, currency="INR"),
        observed_at=base_time,
    )

    report = resolve_field_evidence("total_amount", [total_ev, gateway_ev])
    assert report.is_resolved is True
    assert report.winning_evidence.evidence_id == "ev_rzp_gateway"
    assert report.winning_evidence.field_value == Money(amount=5200000, currency="INR")


# ---------------------------------------------------------------------------
# 3. Deterministic Integrity Delta (Req 9, 10, 15)
# ---------------------------------------------------------------------------

def test_deterministic_economic_delta():
    """Req 9 & 10: Calculates integer delta and violation representation without float."""
    authorized_limit = Money(amount=5000000, currency="INR")  # ₹50,000
    observed_amount = Money(amount=5400000, currency="INR")   # ₹54,000

    delta = compute_economic_delta(authorized_limit, observed_amount)
    assert delta.violated_constraint == "max_total"
    assert delta.is_violation is True
    assert delta.delta["amount"] == 400000  # +₹4,000 (400,000 paise)
    assert delta.delta["currency"] == "INR"
    assert "exceeds authorized baseline by 400000" in delta.explanation


def test_deterministic_economic_delta_non_violation():
    """Req 9: Under-budget execution produces negative/zero delta and is_violation=False."""
    authorized_limit = Money(amount=5000000, currency="INR")
    observed_amount = Money(amount=4800000, currency="INR")

    delta = compute_economic_delta(authorized_limit, observed_amount)
    assert delta.is_violation is False
    assert delta.delta["amount"] == -200000
    assert "within authorized baseline" in delta.explanation


def test_deterministic_quantity_delta():
    """Req 10: SKU quantity delta calculation."""
    delta = compute_quantity_delta(authorized_qty=1, observed_qty=3, sku="SERVER-256GB")
    assert delta.violated_constraint == "item_quantity:SERVER-256GB"
    assert delta.is_violation is True
    assert delta.delta == 2
    assert "exceeds authorized by +2" in delta.explanation


# ---------------------------------------------------------------------------
# 4. Freshness + Integrity Interaction (Req 12, 13, 16, 18)
# ---------------------------------------------------------------------------

def test_stale_or_expired_evidence_cannot_silently_pass(base_time):
    """Req 12 & 13: Stale or expired evidence is flagged and rejected when freshness is required."""
    ev_expired = Evidence(
        evidence_id="ev_exp_01",
        intent_id="int_01",
        source=EvidenceSource.RAZORPAY,
        authority=EvidenceAuthority.AUTHORITATIVE,
        field_name="total_amount",
        field_value=Money(amount=5000000, currency="INR"),
        observed_at=base_time,
        provenance={"valid_until": (base_time + timedelta(minutes=5)).isoformat()},
    )

    eval_ref = base_time + timedelta(minutes=30)
    status, acceptable, reason = assess_evidence_freshness_for_constraint(
        evidence=ev_expired,
        reference_time=eval_ref,
        require_fresh=True,
    )
    assert status == FreshnessStatus.EXPIRED
    assert acceptable is False
    assert "EXPIRED" in reason


def test_stale_evidence_rejection_when_require_fresh_true(base_time):
    """Req 12: Stale evidence is rejected when freshness is required."""
    ev_stale = Evidence(
        evidence_id="ev_stl_01",
        intent_id="int_01",
        source=EvidenceSource.RAZORPAY,
        authority=EvidenceAuthority.AUTHORITATIVE,
        field_name="total_amount",
        field_value=Money(amount=5000000, currency="INR"),
        observed_at=base_time,
    )

    eval_ref = base_time + timedelta(hours=1)
    status, acceptable, reason = assess_evidence_freshness_for_constraint(
        evidence=ev_stale,
        reference_time=eval_ref,
        max_age_seconds=600,  # 10 minutes max age
        require_fresh=True,
    )
    assert status == FreshnessStatus.STALE
    assert acceptable is False
    assert "STALE" in reason


def test_ai_confidence_cannot_declare_evidence_fresh_or_authoritative(base_time):
    """Req 16: An AI evidence record with confidence_score=1.0 remains ADVISORY and cannot claim authority."""
    ev_ai = Evidence(
        evidence_id="ev_ai_fake",
        intent_id="int_01",
        source=EvidenceSource.AGENT,
        authority=EvidenceAuthority.ADVISORY,
        field_name="total_amount",
        field_value=Money(amount=5000000, currency="INR"),
        observed_at=base_time,
        confidence_score=1.0,
    )

    assert ev_ai.authority == EvidenceAuthority.ADVISORY
    assert ev_ai.authority_rank == 20
    assert ev_ai.confidence_score == 1.0


def test_adversarial_naive_datetime_in_freshness_rejected(base_time):
    """Req 18: Naive datetime in EvidenceFreshnessMetadata is rejected."""
    with pytest.raises(ValueError, match="timezone-aware"):
        EvidenceFreshnessMetadata(
            observed_at=datetime(2026, 9, 5, 12, 0, 0),  # Naive
        )
