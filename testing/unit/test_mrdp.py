"""
Unit test suite for TarkaRaksha's proposed Machine-Readable Drift Proof (MRDP) service (T07).
Testing reference: brain/TarkaRaksha_TESTING.md §9.25–§9.29.

Covers:
- Valid DRIFT -> MRDP generation (Economic, Semantic, Temporal)
- All required machine-readable fields and properties
- Status safety: PASS cannot generate MRDP
- Intent correlation validation
- Evidence reference traceability to EvidenceBundle
- Cryptographic SHA-256 tamper-evident digest and integrity verification
- 100x repeated execution determinism
"""
from datetime import datetime, timezone, timedelta
import pytest

from backend.app.domain.models import (
    EvidenceAuthority,
    EvidenceSource,
    Evidence,
    EvidenceBundle,
    IntegrityResult,
    IntegrityStatus,
    IntentContract,
    IntentItem,
    Money,
    MRDP,
    MRDPErrorCode,
)
from backend.app.services.mrdp import build_mrdp, verify_mrdp_integrity


@pytest.fixture
def base_contract() -> IntentContract:
    now = datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)
    return IntentContract(
        intent_id="intent-mrdp-100",
        issued_by="user-test",
        issued_at=now,
        expires_at=now + timedelta(hours=1),
        currency="INR",
        max_total=Money(amount=5000000, currency="INR"),  # ₹50,000.00
        items=[
            IntentItem(
                item_id="item-srv-1",
                sku="SERVER-256GB",
                name="Dedicated Server 256GB",
                quantity=1,
                unit_price=Money(amount=5000000, currency="INR"),
                total_price=Money(amount=5000000, currency="INR"),
            )
        ],
    )


@pytest.fixture
def economic_drift_fixture(base_contract: IntentContract):
    now = datetime(2026, 9, 5, 12, 5, 0, tzinfo=timezone.utc)
    ev = Evidence(
        evidence_id="ev_rzp_55k",
        intent_id=base_contract.intent_id,
        source=EvidenceSource.RAZORPAY,
        authority=EvidenceAuthority.AUTHORITATIVE,
        field_name="total_amount",
        field_value=Money(amount=5500000, currency="INR"),  # ₹55,000.00
        observed_at=now,
    )
    bundle = EvidenceBundle(
        bundle_id="b_econ",
        intent_id=base_contract.intent_id,
        created_at=now,
        records=[ev],
    )
    result = IntegrityResult(
        evaluation_id="eval-econ-01",
        intent_id=base_contract.intent_id,
        status=IntegrityStatus.DRIFT,
        evaluated_at=now,
        rule_results={"economic": False, "semantic": True, "temporal": True},
        violations=["Amount observed 5500000 INR exceeded authorized limit 5000000 INR"],
        evidence_ids=["ev_rzp_55k"],
        confidence_score=1.0,
        explanation="Observed payment amount exceeded authorized maximum",
    )
    return bundle, result


def test_economic_drift_builds_valid_mrdp(base_contract: IntentContract, economic_drift_fixture):
    """
    Test DRIFT -> valid MRDP for economic boundary violation:
    - Expected = ₹50,000.00
    - Observed = ₹55,000.00
    - Discrepancy = ₹5,000.00
    - Evidence ref = 'ev_rzp_55k'
    """
    bundle, result = economic_drift_fixture
    fixed_ts = datetime(2026, 9, 5, 12, 10, 0, tzinfo=timezone.utc)

    proof = build_mrdp(
        contract=base_contract,
        integrity_result=result,
        evidence_bundle=bundle,
        generated_at=fixed_ts,
    )

    assert isinstance(proof, MRDP)
    assert proof.protocol == "TarkaRaksha-MRDP"
    assert proof.version == "1.0.0"
    assert proof.intent_id == base_contract.intent_id
    assert proof.error_code == MRDPErrorCode.ECONOMIC_AMOUNT_EXCEEDED.value
    assert proof.status == IntegrityStatus.DRIFT
    assert proof.expected_value == base_contract.max_total
    assert proof.expected == base_contract.max_total
    assert proof.observed_value == Money(amount=5500000, currency="INR")
    assert proof.observed == Money(amount=5500000, currency="INR")
    assert proof.discrepancy_amount == Money(amount=500000, currency="INR")
    assert proof.drift_source == "RAZORPAY"
    assert proof.evidence_references == ["ev_rzp_55k"]
    assert proof.evidence_refs == ["ev_rzp_55k"]
    assert proof.revalidation_required is True
    assert proof.remediation_hint is not None
    assert proof.proof_digest is not None
    assert len(proof.proof_digest) == 64  # Valid SHA-256 hex string

    # Verify tamper-evident integrity passes
    assert verify_mrdp_integrity(proof) is True


def test_semantic_drift_builds_valid_mrdp(base_contract: IntentContract):
    """
    Test DRIFT -> valid MRDP for semantic SKU divergence:
    - Expected = ['SERVER-256GB']
    - Observed = 'SERVER-512GB'
    """
    now = datetime(2026, 9, 5, 12, 5, 0, tzinfo=timezone.utc)
    ev = Evidence(
        evidence_id="ev_sku_unauth",
        intent_id=base_contract.intent_id,
        source=EvidenceSource.MERCHANT,
        authority=EvidenceAuthority.MERCHANT_ATTESTED,
        field_name="sku",
        field_value="SERVER-512GB",
        observed_at=now,
    )
    bundle = EvidenceBundle(
        bundle_id="b_sem",
        intent_id=base_contract.intent_id,
        created_at=now,
        records=[ev],
    )
    result = IntegrityResult(
        evaluation_id="eval-sem-01",
        intent_id=base_contract.intent_id,
        status=IntegrityStatus.DRIFT,
        evaluated_at=now,
        rule_results={"economic": True, "semantic": False, "temporal": True},
        violations=["SKU mismatch: observed 'SERVER-512GB' not in authorized items"],
        evidence_ids=["ev_sku_unauth"],
        confidence_score=1.0,
        explanation="Unauthorized item substitution detected",
    )

    proof = build_mrdp(
        contract=base_contract,
        integrity_result=result,
        evidence_bundle=bundle,
        generated_at=now,
    )

    assert proof.error_code == MRDPErrorCode.SEMANTIC_SKU_MISMATCH.value
    assert proof.expected == ["SERVER-256GB"]
    assert proof.observed == "SERVER-512GB"
    assert proof.drift_source == "MERCHANT"
    assert proof.evidence_refs == ["ev_sku_unauth"]
    assert verify_mrdp_integrity(proof) is True


def test_status_safety_pass_cannot_build_mrdp(base_contract: IntentContract):
    """
    Status Safety: MRDP must strictly represent non-passing outcomes.
    Attempting to build an MRDP for IntegrityStatus.PASS must raise ValueError.
    """
    now = datetime(2026, 9, 5, 12, 5, 0, tzinfo=timezone.utc)
    bundle = EvidenceBundle(
        bundle_id="b_pass",
        intent_id=base_contract.intent_id,
        created_at=now,
        records=[],
    )
    result_pass = IntegrityResult(
        evaluation_id="eval-pass-01",
        intent_id=base_contract.intent_id,
        status=IntegrityStatus.PASS,
        evaluated_at=now,
        rule_results={"economic": True, "semantic": True, "temporal": True},
        violations=[],
        evidence_ids=[],
        confidence_score=1.0,
        explanation="All checks passed cleanly",
    )

    with pytest.raises(ValueError, match="Cannot build MRDP for passing transaction"):
        build_mrdp(base_contract, result_pass, bundle, generated_at=now)


def test_intent_correlation_mismatch_rejected(base_contract: IntentContract, economic_drift_fixture):
    """Mismatched intent IDs across contract, result, or bundle must raise ValueError."""
    bundle, result = economic_drift_fixture
    now = datetime(2026, 9, 5, 12, 10, 0, tzinfo=timezone.utc)

    # Tampered result with different intent_id
    tampered_result = IntegrityResult(
        evaluation_id="eval-mismatch",
        intent_id="intent-foreign-999",
        status=IntegrityStatus.DRIFT,
        evaluated_at=now,
        rule_results={"economic": False},
        violations=["Amount exceeded"],
        evidence_ids=["ev_rzp_55k"],
        confidence_score=1.0,
        explanation="Divergence detected",
    )

    with pytest.raises(ValueError, match="Intent ID mismatch"):
        build_mrdp(base_contract, tampered_result, bundle, generated_at=now)


def test_mrdp_determinism_100_runs(base_contract: IntentContract, economic_drift_fixture):
    """
    Verify that 100 repeated executions with identical inputs produce 100% identical
    MRDP digests and canonical fields.
    """
    bundle, result = economic_drift_fixture
    fixed_ts = datetime(2026, 9, 5, 12, 10, 0, tzinfo=timezone.utc)

    base_proof = build_mrdp(
        contract=base_contract,
        integrity_result=result,
        evidence_bundle=bundle,
        generated_at=fixed_ts,
        mrdp_id="mrdp_fixed_001",
    )
    expected_digest = base_proof.proof_digest
    expected_json = base_proof.model_dump_json()

    for _ in range(100):
        test_proof = build_mrdp(
            contract=base_contract,
            integrity_result=result,
            evidence_bundle=bundle,
            generated_at=fixed_ts,
            mrdp_id="mrdp_fixed_001",
        )
        assert test_proof.proof_digest == expected_digest
        assert test_proof.model_dump_json() == expected_json
