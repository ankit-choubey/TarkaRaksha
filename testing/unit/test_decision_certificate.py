"""
Unit tests for Decision Reproducibility Certificate (I3.3).
"""
from datetime import datetime, timezone
import pytest

from backend.app.domain.governance import (
    DEFAULT_POLICY_VERSION,
    DEFAULT_RULES_VERSION,
    DecisionReproducibilityCertificate,
    compute_intent_hash,
    compute_evidence_hash,
    compute_event_chain_hash,
)
from backend.app.domain.models import (
    CanonicalEvent,
    Evidence,
    EvidenceAuthority,
    EvidenceSource,
    IntegrityStatus,
    IntentContract,
    IntentItem,
    Money,
)


@pytest.fixture
def base_intent():
    unit_m = Money(amount=10000, currency="INR")
    return IntentContract(
        intent_id="intent_cert_1",
        issued_by="usr_cert_1",
        currency="INR",
        max_total=unit_m,
        items=[IntentItem(item_id="item_1", sku="SKU-1", name="Wireless Mouse", quantity=1, unit_price=unit_m, total_price=unit_m)],
        issued_at=datetime(2026, 9, 5, 10, 0, 0, tzinfo=timezone.utc),
        expires_at=datetime(2026, 9, 5, 11, 0, 0, tzinfo=timezone.utc),
    )


@pytest.fixture
def base_events():
    return [
        CanonicalEvent(
            event_id="ev_1",
            transaction_id="tx_cert_1",
            intent_id="intent_cert_1",
            event_type="ORDER_CREATED",
            source=EvidenceSource.MERCHANT,
            authority=EvidenceAuthority.MERCHANT_ATTESTED,
            timestamp=datetime(2026, 9, 5, 10, 5, 0, tzinfo=timezone.utc),
            payload_summary={"order_id": "order_1", "amount": 10000},
        ),
        CanonicalEvent(
            event_id="ev_2",
            transaction_id="tx_cert_1",
            intent_id="intent_cert_1",
            event_type="PAYMENT_CAPTURED",
            source=EvidenceSource.RAZORPAY,
            authority=EvidenceAuthority.AUTHORITATIVE,
            timestamp=datetime(2026, 9, 5, 10, 6, 0, tzinfo=timezone.utc),
            payload_summary={"payment_id": "pay_1", "amount": 10000},
        ),
    ]


@pytest.fixture
def base_evidence():
    return [
        Evidence(
            evidence_id="evi_1",
            intent_id="intent_cert_1",
            transaction_id="tx_cert_1",
            source=EvidenceSource.RAZORPAY,
            authority=EvidenceAuthority.AUTHORITATIVE,
            field_name="payment_status",
            field_value="captured",
            observed_at=datetime(2026, 9, 5, 10, 6, 1, tzinfo=timezone.utc),
        )
    ]


def test_certificate_issuance_and_verification(base_intent, base_events, base_evidence):
    dec_time = datetime(2026, 9, 5, 10, 10, 0, tzinfo=timezone.utc)
    cert = DecisionReproducibilityCertificate.issue(
        certificate_id="cert_1",
        transaction_id="tx_cert_1",
        decision=IntegrityStatus.PASS,
        intent=base_intent,
        events=base_events,
        evidence=base_evidence,
        decision_timestamp=dec_time,
    )

    assert cert.certificate_id == "cert_1"
    assert cert.decision == IntegrityStatus.PASS
    assert cert.rules_version == DEFAULT_RULES_VERSION
    assert cert.policy_version == DEFAULT_POLICY_VERSION
    assert len(cert.certificate_signature_hash) == 64

    # Verify without raw inputs
    res_internal = cert.verify_integrity()
    assert res_internal.is_valid is True
    assert len(res_internal.mutations) == 0

    # Verify with matching raw inputs
    res_full = cert.verify_integrity(intent=base_intent, events=base_events, evidence=base_evidence)
    assert res_full.is_valid is True


def test_certificate_detects_tampered_signature():
    dec_time = datetime(2026, 9, 5, 10, 10, 0, tzinfo=timezone.utc)
    cert = DecisionReproducibilityCertificate(
        certificate_id="cert_1",
        transaction_id="tx_cert_1",
        decision=IntegrityStatus.PASS,
        intent_hash="00" * 32,
        evidence_hash="11" * 32,
        event_chain_hash="22" * 32,
        rules_version=DEFAULT_RULES_VERSION,
        policy_version=DEFAULT_POLICY_VERSION,
        decision_timestamp=dec_time,
        certificate_signature_hash="invalid_hash_signature",
    )
    res = cert.verify_integrity()
    assert res.is_valid is False
    assert "CERTIFICATE_TAMPERED" in res.mutations


def test_certificate_detects_intent_mutation(base_intent, base_events, base_evidence):
    dec_time = datetime(2026, 9, 5, 10, 10, 0, tzinfo=timezone.utc)
    cert = DecisionReproducibilityCertificate.issue(
        certificate_id="cert_1",
        transaction_id="tx_cert_1",
        decision=IntegrityStatus.PASS,
        intent=base_intent,
        events=base_events,
        evidence=base_evidence,
        decision_timestamp=dec_time,
    )

    tampered_intent = base_intent.model_copy(update={"max_total": Money(amount=50000, currency="INR")})
    res = cert.verify_integrity(intent=tampered_intent, events=base_events, evidence=base_evidence)
    assert res.is_valid is False
    assert "INTENT_HASH_MUTATION" in res.mutations


def test_certificate_detects_evidence_mutation(base_intent, base_events, base_evidence):
    dec_time = datetime(2026, 9, 5, 10, 10, 0, tzinfo=timezone.utc)
    cert = DecisionReproducibilityCertificate.issue(
        certificate_id="cert_1",
        transaction_id="tx_cert_1",
        decision=IntegrityStatus.PASS,
        intent=base_intent,
        events=base_events,
        evidence=base_evidence,
        decision_timestamp=dec_time,
    )

    tampered_evidence = [
        base_evidence[0].model_copy(update={"field_value": "failed"})
    ]
    res = cert.verify_integrity(intent=base_intent, events=base_events, evidence=tampered_evidence)
    assert res.is_valid is False
    assert "EVIDENCE_HASH_MUTATION" in res.mutations


def test_certificate_detects_event_chain_mutation(base_intent, base_events, base_evidence):
    dec_time = datetime(2026, 9, 5, 10, 10, 0, tzinfo=timezone.utc)
    cert = DecisionReproducibilityCertificate.issue(
        certificate_id="cert_1",
        transaction_id="tx_cert_1",
        decision=IntegrityStatus.PASS,
        intent=base_intent,
        events=base_events,
        evidence=base_evidence,
        decision_timestamp=dec_time,
    )

    tampered_events = [base_events[0]]  # Omit second event
    res = cert.verify_integrity(intent=base_intent, events=tampered_events, evidence=base_evidence)
    assert res.is_valid is False
    assert "EVENT_CHAIN_HASH_MUTATION" in res.mutations


def test_hashes_are_distinguishable_between_components(base_intent, base_events, base_evidence):
    i_hash = compute_intent_hash(base_intent)
    ev_hash = compute_evidence_hash(base_evidence)
    ch_hash = compute_event_chain_hash(base_events)

    assert i_hash != ev_hash
    assert i_hash != ch_hash
    assert ev_hash != ch_hash
