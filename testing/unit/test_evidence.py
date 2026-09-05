"""
Unit test suite for TarkaRaksha Evidence Normalization Layer (T06).
Covers:
- Canonical evidence source taxonomy and validation
- Explicit authority tiers and hierarchy
- Timezone-aware timestamp validation (rejection of naive datetimes)
- Monetary value normalization into canonical Money value objects
- Factual conflict representation and deterministic authority resolution
- Idempotent evidence deduplication
- Immutability of Evidence and EvidenceBundle
- 100x repeated determinism across identical inputs
"""
from datetime import datetime, timezone, timedelta
import pytest

from backend.app.domain.models import (
    EvidenceAuthority,
    EvidenceSource,
    Evidence,
    CanonicalEvent,
    EvidenceBundle,
    Money,
)
from backend.app.domain.evidence import (
    normalize_source,
    normalize_authority,
    normalize_monetary_value,
    normalize_evidence_record,
    build_evidence_bundle,
    deduplicate_evidence,
    resolve_field_evidence,
    analyze_bundle_conflicts,
)


def test_canonical_source_taxonomy():
    """Verify all canonical sources are accepted and unknown sources rejected."""
    expected_sources = [
        "INTENT",
        "USER_INTENT",
        "AGENT",
        "MERCHANT",
        "RAZORPAY",
        "SYSTEM",
        "REPLAY",
        "SYNTHETIC",
    ]
    for src in expected_sources:
        normalized = normalize_source(src)
        assert isinstance(normalized, EvidenceSource)
        assert normalized.value == src

    with pytest.raises(ValueError, match="Unknown evidence source"):
        normalize_source("UNAUTHORIZED_GATEWAY")

    with pytest.raises(TypeError):
        normalize_source(12345)  # type: ignore


def test_authority_tiers_and_ranking():
    """Verify explicit authority tiers and strict numeric ranking hierarchy."""
    now = datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)

    ev_auth = Evidence(
        evidence_id="ev_01",
        intent_id="int_01",
        source=EvidenceSource.RAZORPAY,
        authority=EvidenceAuthority.AUTHORITATIVE,
        field_name="total_amount",
        field_value=Money(amount=50000, currency="INR"),
        observed_at=now,
    )
    ev_intent = Evidence(
        evidence_id="ev_02",
        intent_id="int_01",
        source=EvidenceSource.INTENT,
        authority=EvidenceAuthority.PROTOCOL_TRUSTED,
        field_name="total_amount",
        field_value=Money(amount=50000, currency="INR"),
        observed_at=now,
    )
    ev_merchant = Evidence(
        evidence_id="ev_03",
        intent_id="int_01",
        source=EvidenceSource.MERCHANT,
        authority=EvidenceAuthority.MERCHANT_ATTESTED,
        field_name="total_amount",
        field_value=Money(amount=50000, currency="INR"),
        observed_at=now,
    )
    ev_replay = Evidence(
        evidence_id="ev_04",
        intent_id="int_01",
        source=EvidenceSource.REPLAY,
        authority=EvidenceAuthority.REPLAY_OBSERVED,
        field_name="total_amount",
        field_value=Money(amount=50000, currency="INR"),
        observed_at=now,
    )
    ev_system = Evidence(
        evidence_id="ev_05",
        intent_id="int_01",
        source=EvidenceSource.SYSTEM,
        authority=EvidenceAuthority.SYSTEM_DERIVED,
        field_name="total_amount",
        field_value=Money(amount=50000, currency="INR"),
        observed_at=now,
    )
    ev_agent = Evidence(
        evidence_id="ev_06",
        intent_id="int_01",
        source=EvidenceSource.AGENT,
        authority=EvidenceAuthority.ADVISORY,
        field_name="total_amount",
        field_value=Money(amount=50000, currency="INR"),
        observed_at=now,
    )

    # Assert ranking hierarchy: 100 > 90 > 70 > 60 > 50 > 20
    assert ev_auth.authority_rank == 100
    assert ev_intent.authority_rank == 90
    assert ev_merchant.authority_rank == 70
    assert ev_replay.authority_rank == 60
    assert ev_system.authority_rank == 50
    assert ev_agent.authority_rank == 20
    assert ev_auth.authority_rank > ev_intent.authority_rank > ev_merchant.authority_rank > ev_replay.authority_rank > ev_system.authority_rank > ev_agent.authority_rank


def test_timestamp_validation_and_provenance():
    """Verify timezone awareness enforcement and provenance preservation."""
    now = datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)
    ingested = now + timedelta(seconds=1)

    raw = {
        "evidence_id": "ev_prov_01",
        "intent_id": "int_01",
        "transaction_id": "tx_01",
        "source": "RAZORPAY",
        "field_name": "payment_id",
        "field_value": "pay_test123",
        "observed_at": now.isoformat(),
        "ingested_at": ingested.isoformat(),
        "raw_reference": "rzp_webhook_evt_999",
        "provenance": {"ip": "127.0.0.1", "signature_verified": True},
        "confidence_score": 1.0,
    }

    ev = normalize_evidence_record(raw)
    assert ev.evidence_id == "ev_prov_01"
    assert ev.transaction_id == "tx_01"
    assert ev.observed_at == now
    assert ev.ingested_at == ingested
    assert ev.raw_reference == "rzp_webhook_evt_999"
    assert ev.provenance["signature_verified"] is True
    assert ev.confidence_score == 1.0

    # Naive timestamp must be rejected
    naive_raw = dict(raw, observed_at="2026-09-05T12:00:00")
    with pytest.raises(ValueError, match="timezone-aware"):
        normalize_evidence_record(naive_raw)


def test_monetary_normalization():
    """Verify conversion to canonical Money and rejection of floats."""
    # Integer subunits
    m1 = normalize_monetary_value(50000, "INR")
    assert isinstance(m1, Money)
    assert m1.amount == 50000
    assert m1.currency == "INR"

    # Dict representation
    m2 = normalize_monetary_value({"amount": 75000, "currency": "INR"})
    assert isinstance(m2, Money)
    assert m2.amount == 75000

    # Float values must be rejected
    with pytest.raises(ValueError, match="Floating point values are forbidden"):
        normalize_monetary_value(500.50)


def test_conflict_resolution_via_authority_dominance():
    """
    Test that higher-authority evidence (e.g. RAZORPAY ₹50,000) overrides lower-authority
    evidence (e.g. AGENT ₹48,000) deterministically while retaining subordinate claims as provenance.
    """
    now = datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)

    ev_agent = Evidence(
        evidence_id="ev_ag",
        intent_id="int_01",
        source=EvidenceSource.AGENT,
        authority=EvidenceAuthority.ADVISORY,
        field_name="total_amount",
        field_value=Money(amount=48000, currency="INR"),
        observed_at=now,
    )
    ev_rzp = Evidence(
        evidence_id="ev_rzp",
        intent_id="int_01",
        source=EvidenceSource.RAZORPAY,
        authority=EvidenceAuthority.AUTHORITATIVE,
        field_name="total_amount",
        field_value=Money(amount=50000, currency="INR"),
        observed_at=now,
    )

    report = resolve_field_evidence("total_amount", [ev_agent, ev_rzp])
    assert report.is_resolved is True
    assert report.winning_evidence is not None
    assert report.winning_evidence.evidence_id == "ev_rzp"
    assert report.winning_evidence.field_value == Money(amount=50000, currency="INR")
    assert len(report.conflicting_records) == 1
    assert report.conflicting_records[0].evidence_id == "ev_ag"


def test_conflict_resolution_irreconcilable_tie_at_top_tier():
    """
    When contradictory evidence exists at the identical highest authority tier
    (e.g. two conflicting RAZORPAY records), it cannot be resolved safely.
    It returns is_resolved=False, winning_evidence=None (signaling UNKNOWN).
    """
    now = datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)

    ev_rzp1 = Evidence(
        evidence_id="ev_rzp1",
        intent_id="int_01",
        source=EvidenceSource.RAZORPAY,
        authority=EvidenceAuthority.AUTHORITATIVE,
        field_name="payment_status",
        field_value="captured",
        observed_at=now,
    )
    ev_rzp2 = Evidence(
        evidence_id="ev_rzp2",
        intent_id="int_01",
        source=EvidenceSource.RAZORPAY,
        authority=EvidenceAuthority.AUTHORITATIVE,
        field_name="payment_status",
        field_value="failed",
        observed_at=now,
    )

    report = resolve_field_evidence("payment_status", [ev_rzp1, ev_rzp2])
    assert report.is_resolved is False
    assert report.winning_evidence is None
    assert len(report.conflicting_records) == 2
    assert "Irreconcilable conflict" in report.resolution_reason


def test_evidence_deduplication():
    """Verify duplicate evidence records are removed deterministically while preserving order."""
    now = datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)

    ev1 = Evidence(
        evidence_id="ev_100",
        intent_id="int_01",
        source=EvidenceSource.RAZORPAY,
        field_name="total_amount",
        field_value=Money(amount=50000, currency="INR"),
        observed_at=now,
    )
    # Duplicate with same evidence_id
    ev1_dup = Evidence(
        evidence_id="ev_100",
        intent_id="int_01",
        source=EvidenceSource.RAZORPAY,
        field_name="total_amount",
        field_value=Money(amount=50000, currency="INR"),
        observed_at=now,
    )
    ev2 = Evidence(
        evidence_id="ev_101",
        intent_id="int_01",
        source=EvidenceSource.MERCHANT,
        field_name="order_id",
        field_value="order_999",
        observed_at=now,
    )

    deduped = deduplicate_evidence([ev1, ev1_dup, ev2])
    assert len(deduped) == 2
    assert [e.evidence_id for e in deduped] == ["ev_100", "ev_101"]


def test_immutability_guarantee():
    """Verify that Evidence and EvidenceBundle cannot be mutated after construction."""
    now = datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)
    ev = Evidence(
        evidence_id="ev_imm",
        intent_id="int_01",
        source=EvidenceSource.RAZORPAY,
        field_name="status",
        field_value="captured",
        observed_at=now,
    )
    bundle = EvidenceBundle(
        bundle_id="b_imm",
        intent_id="int_01",
        created_at=now,
        records=[ev],
    )

    with pytest.raises(Exception):
        ev.field_value = "refunded"  # type: ignore

    with pytest.raises(Exception):
        bundle.bundle_id = "b_tampered"  # type: ignore


def test_evidence_bundle_determinism_100_runs():
    """Verify identical raw inputs produce 100% identical EvidenceBundle across 100 repeated runs."""
    now = datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)
    raw_records = [
        {
            "evidence_id": "ev_det_01",
            "source": "AGENT",
            "field_name": "total_amount",
            "field_value": 48000,
            "observed_at": now.isoformat(),
        },
        {
            "evidence_id": "ev_det_02",
            "source": "RAZORPAY",
            "field_name": "total_amount",
            "field_value": 50000,
            "observed_at": now.isoformat(),
        },
    ]

    base_bundle = build_evidence_bundle(
        intent_id="int_det",
        raw_records=raw_records,
        created_at=now,
        bundle_id="bundle_det_fixed",
    )
    base_json = base_bundle.model_dump_json()

    for _ in range(100):
        test_bundle = build_evidence_bundle(
            intent_id="int_det",
            raw_records=raw_records,
            created_at=now,
            bundle_id="bundle_det_fixed",
        )
        assert test_bundle.model_dump_json() == base_json
