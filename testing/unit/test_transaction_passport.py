"""
Comprehensive Unit and Adversarial Test Suite for E5 — Transaction Passport.

Covers all minimum required scenarios from Section 25, 26, 27:
- Identity & Binding (1-6)
- Authorization (7-10)
- Agent & Merchant Context (11-15)
- Lifecycle State Projection (16-18)
- Deterministic Integrity (19-23)
- DRIFT & MRDP (24-28)
- Evidence Hierarchy (29-33)
- Security Findings (34-35)
- Recovery (36-39)
- UNKNOWN Resolution (40-44)
- Revalidation (45-49)
- Checkpoints & Trace (50-52)
- Payment State Separation (53-55)
- Pure CPU Replay (56-57)
- Immutability & Non-Mutation (58-60)
- Adversarial Consistency (61-63)
- Text Summary & REST API (64-66)
"""
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app, get_integration_service
from backend.app.domain.buyer.contracts import BuyerTransactionProposal
from backend.app.domain.gates.contracts import (
    ConsumerGateResult,
    GateStatus,
    GateValidationFinding,
    MerchantGateResult,
)
from backend.app.domain.merchant.contracts import (
    CatalogItem,
    InventoryRecord,
    InventoryStatus,
    MerchantOfferItem,
    MerchantResponse,
    ShippingOption,
    TaxEstimate,
)
from backend.app.domain.models import (
    ActionRequest,
    ActionType,
    CanonicalEvent,
    Evidence,
    EvidenceAuthority,
    EvidenceSource,
    IntegrityResult,
    IntegrityStatus,
    IntentContract,
    IntentItem,
    MRDP,
    Money,
    ProviderOrder,
    ProviderPayment,
    TransactionState,
)
from backend.app.domain.orchestration.contracts import (
    LifecycleOutcome,
    LifecyclePolicy,
    LifecycleStage,
)
from backend.app.domain.passport import (
    TransactionPassport,
    PassportIdentitySection,
    PassportAuthorizationSection,
)
from backend.app.services.gates.consumer_gate import ConsumerGate
from backend.app.services.gates.merchant_gate import MerchantGate
from backend.app.services.integration import (
    IntegrationBoundaryError,
    IntegrationService,
)
from backend.app.services.merchant.catalog_service import MerchantCatalogService
from backend.app.services.orchestration.lifecycle import AgenticLifecycleOrchestrator
from backend.app.services.passport.service import TransactionPassportService
from backend.app.services.replay.contracts import ReplayResult, ReplayVerdict
from backend.app.domain.states.machine import TransactionStateMachine


# ==============================================================================
# TEST FIXTURES & SETUP
# ==============================================================================

@pytest.fixture
def ref_time() -> datetime:
    return datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def base_intent(ref_time) -> IntentContract:
    return IntentContract(
        intent_id="intent_passport_001",
        issued_by="buyer_alice",
        items=[
            IntentItem(
                item_id="item_nvme_001",
                sku="SKU-NVME-2TB",
                name="2TB NVMe PCIe 4.0 SSD",
                quantity=1,
                unit_price=Money(amount=1200000, currency="INR"),  # ₹12,000.00
                total_price=Money(amount=1200000, currency="INR"),
            )
        ],
        max_total=Money(amount=1200000, currency="INR"),
        currency="INR",
        allowed_substitutions=["SKU-NVME-2TB-V2"],
        issued_at=ref_time,
        expires_at=ref_time + timedelta(hours=2),
    )


@pytest.fixture
def catalog_service() -> MerchantCatalogService:
    service = MerchantCatalogService(merchant_id="merchant_fast_001")
    service.add_item(
        CatalogItem(
            sku="SKU-NVME-2TB",
            title="2TB NVMe PCIe 4.0 SSD",
            description="Ultra-fast PCIe Gen4 SSD",
            base_price=Money(amount=1200000, currency="INR"),
            currency="INR",
            category="storage",
        )
    )
    service.set_inventory(
        "SKU-NVME-2TB",
        InventoryRecord(sku="SKU-NVME-2TB", quantity_available=10, status=InventoryStatus.AVAILABLE),
    )
    return service


@pytest.fixture
def integration_service(catalog_service) -> IntegrationService:
    return IntegrationService(merchant_service=catalog_service)


@pytest.fixture
def passport_service() -> TransactionPassportService:
    return TransactionPassportService()


def seed_standard_transaction(
    integration_service: IntegrationService,
    base_intent: IntentContract,
    tx_id: str,
    unit_price: int = 1200000,
    status: str = "captured",
    ref_time: datetime = None,
) -> str:
    """Helper to seed an active integration transaction with standard records."""
    now = ref_time or datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)
    integration_service.create_context(
        transaction_id=tx_id,
        intent_id=base_intent.intent_id,
        agent_id="agent_buyer_001",
        merchant_id="merchant_fast_001",
        attempt_id="att_1",
        reference_time=now,
    )
    integration_service.bind_intent(tx_id, base_intent, now)

    prop = BuyerTransactionProposal(
        proposal_id=f"prop_{tx_id}",
        intent_id=base_intent.intent_id,
        transaction_id=tx_id,
        buyer_agent_id="agent_buyer_001",
        sku="SKU-NVME-2TB",
        quantity=1,
        max_total=base_intent.max_total,
        rationale="Standard purchase proposal",
    )
    integration_service.validate_consumer_gate(tx_id, prop, now)

    total_money = Money(amount=unit_price, currency="INR")
    mresp = MerchantResponse(
        response_id=f"mresp_{tx_id}",
        merchant_id="merchant_fast_001",
        request_id=f"req_{tx_id}",
        intent_id=base_intent.intent_id,
        transaction_id=tx_id,
        is_success=True,
        items=[
            MerchantOfferItem(
                sku="SKU-NVME-2TB",
                title="2TB NVMe SSD",
                quantity=1,
                unit_price=total_money,
                total_price=total_money,
            )
        ],
        subtotal=total_money,
        shipping=ShippingOption(
            option_id="s1",
            carrier="Standard Courier",
            method_name="Standard",
            cost=Money(amount=0, currency="INR"),
            estimated_days=2,
        ),
        tax=TaxEstimate(amount=Money(amount=0, currency="INR")),
        total_amount=total_money,
        inventory_status=InventoryStatus.AVAILABLE,
        offer_created_at=now,
        offer_expires_at=now + timedelta(hours=2),
    )
    integration_service.validate_merchant_gate(
        transaction_id=tx_id,
        merchant_response=mresp,
        requested_sku="SKU-NVME-2TB",
        requested_quantity=1,
        reference_time=now,
    )

    ev_amount = Evidence(
        evidence_id=f"ev_amt_{tx_id}",
        intent_id=base_intent.intent_id,
        transaction_id=tx_id,
        source=EvidenceSource.RAZORPAY,
        authority=EvidenceAuthority.AUTHORITATIVE,
        field_name="total_amount",
        field_value=total_money,
        observed_at=now,
        provenance={"gateway": "razorpay", "status": status},
    )
    integration_service.add_evidence(tx_id, ev_amount)

    ev_items = Evidence(
        evidence_id=f"ev_items_{tx_id}",
        intent_id=base_intent.intent_id,
        transaction_id=tx_id,
        source=EvidenceSource.MERCHANT,
        authority=EvidenceAuthority.MERCHANT_ATTESTED,
        field_name="executed_items",
        field_value=[{"sku": "SKU-NVME-2TB", "quantity": 1}],
        observed_at=now,
        provenance={"merchant_id": "merchant_fast_001"},
    )
    integration_service.add_evidence(tx_id, ev_items)

    evt = CanonicalEvent(
        event_id=f"evt_{tx_id}",
        transaction_id=tx_id,
        intent_id=base_intent.intent_id,
        event_type="PAYMENT_CAPTURED",
        timestamp=now,
        amount=total_money,
        source=EvidenceSource.RAZORPAY,
        authority=EvidenceAuthority.AUTHORITATIVE,
    )
    integration_service.add_event(tx_id, evt)

    # Evaluate
    integration_service.evaluate(tx_id, now)
    return tx_id


# ==============================================================================
# 1. IDENTITY & BINDING (1-6)
# ==============================================================================

def test_01_passport_contains_transaction_identity(integration_service, base_intent, passport_service, ref_time):
    """1. Passport faithfully contains the unique transaction ID."""
    tx_id = seed_standard_transaction(integration_service, base_intent, "tx_p_001", ref_time=ref_time)
    passport = integration_service.get_passport(tx_id, ref_time)
    assert passport.transaction_id == "tx_p_001"
    assert passport.passport_id == "passport_tx_p_001"


def test_02_passport_preserves_intent_id(integration_service, base_intent, ref_time):
    """2. Passport preserves the canonical intent ID."""
    tx_id = seed_standard_transaction(integration_service, base_intent, "tx_p_002", ref_time=ref_time)
    passport = integration_service.get_passport(tx_id, ref_time)
    assert passport.identity.intent_id == base_intent.intent_id


def test_03_passport_preserves_agent_identity(integration_service, base_intent, ref_time):
    """3. Passport preserves buyer agent identities without loss."""
    tx_id = seed_standard_transaction(integration_service, base_intent, "tx_p_003", ref_time=ref_time)
    passport = integration_service.get_passport(tx_id, ref_time)
    assert "agent_buyer_001" in passport.identity.agent_ids


def test_04_passport_preserves_merchant_identity(integration_service, base_intent, ref_time):
    """4. Passport preserves merchant identity."""
    tx_id = seed_standard_transaction(integration_service, base_intent, "tx_p_004", ref_time=ref_time)
    passport = integration_service.get_passport(tx_id, ref_time)
    assert passport.identity.merchant_id == "merchant_fast_001"


def test_05_passport_preserves_order_and_payment_ids(integration_service, base_intent, ref_time):
    """5. Passport preserves order, payment, and attempt identifiers when present."""
    tx_id = seed_standard_transaction(integration_service, base_intent, "tx_p_005", ref_time=ref_time)
    record = integration_service.get_record(tx_id)
    record = record.model_copy(
        update={
            "order": ProviderOrder(
                order_id="ord_005",
                amount=base_intent.max_total,
                currency="INR",
                status="created",
                created_at=ref_time,
            ),
            "payment": ProviderPayment(
                payment_id="pay_005",
                amount=base_intent.max_total,
                status="captured",
                method="upi",
                created_at=ref_time,
            ),
        }
    )
    integration_service._records[tx_id] = record
    passport = integration_service.get_passport(tx_id, ref_time)
    assert passport.identity.order_id == "ord_005"
    assert passport.identity.payment_id == "pay_005"
    assert passport.identity.attempt_id == "att_1"


def test_06_mismatched_transaction_raises_error(integration_service):
    """6. Non-existent transaction ID raises IntegrationBoundaryError."""
    with pytest.raises(IntegrationBoundaryError, match="Transaction context 'tx_ghost_999' not found"):
        integration_service.get_passport("tx_ghost_999")


# ==============================================================================
# 2. AUTHORIZATION & CONSTRAINTS (7-10)
# ==============================================================================

def test_07_original_authorization_represented_correctly(integration_service, base_intent, ref_time):
    """7. Original authorization constraints are faithfully represented."""
    tx_id = seed_standard_transaction(integration_service, base_intent, "tx_p_007", ref_time=ref_time)
    passport = integration_service.get_passport(tx_id, ref_time)
    assert passport.authorization.max_total.amount == base_intent.max_total.amount
    assert passport.authorization.currency == "INR"
    assert len(passport.authorization.authorized_items) == 1
    assert passport.authorization.authorized_items[0]["sku"] == "SKU-NVME-2TB"


def test_08_authorization_constraints_preserved(integration_service, base_intent, ref_time):
    """8. Permitted substitutions and temporal bounds are preserved."""
    tx_id = seed_standard_transaction(integration_service, base_intent, "tx_p_008", ref_time=ref_time)
    passport = integration_service.get_passport(tx_id, ref_time)
    assert "SKU-NVME-2TB-V2" in passport.authorization.allowed_substitutions
    assert passport.authorization.issued_at == base_intent.issued_at
    assert passport.authorization.expires_at == base_intent.expires_at


def test_09_passport_cannot_modify_authorization(integration_service, base_intent, ref_time):
    """9. Passport is strictly frozen; attempting to mutate authorization raises error."""
    tx_id = seed_standard_transaction(integration_service, base_intent, "tx_p_009", ref_time=ref_time)
    passport = integration_service.get_passport(tx_id, ref_time)
    with pytest.raises(Exception):
        passport.authorization.max_total = Money(amount=99999999, currency="INR")


def test_10_budget_remains_original_authoritative_budget(integration_service, base_intent, ref_time):
    """10. Budget ceiling in passport strictly matches original IntentContract max_total."""
    tx_id = seed_standard_transaction(integration_service, base_intent, "tx_p_010", ref_time=ref_time)
    passport = integration_service.get_passport(tx_id, ref_time)
    assert passport.authorization.max_total == base_intent.max_total


# ==============================================================================
# 3. AGENT & MERCHANT CONTEXT (11-15)
# ==============================================================================

def test_11_buyer_agent_participation_represented(integration_service, base_intent, ref_time):
    """11. Buyer agent proposal details are reflected in the agent context."""
    tx_id = seed_standard_transaction(integration_service, base_intent, "tx_p_011", ref_time=ref_time)
    passport = integration_service.get_passport(tx_id, ref_time)
    assert passport.agent_context.buyer_agent_id == "agent_buyer_001"
    assert passport.agent_context.proposed_sku == "SKU-NVME-2TB"
    assert passport.agent_context.proposed_quantity == 1
    assert passport.agent_context.consumer_gate_status == "VALID"


def test_12_merchant_agent_participation_represented(integration_service, base_intent, ref_time):
    """12. Merchant response and pricing details are reflected in merchant context."""
    tx_id = seed_standard_transaction(integration_service, base_intent, "tx_p_012", ref_time=ref_time)
    passport = integration_service.get_passport(tx_id, ref_time)
    assert passport.merchant_context.merchant_id == "merchant_fast_001"
    assert passport.merchant_context.offered_total == Money(amount=1200000, currency="INR")
    assert passport.merchant_context.inventory_status == "AVAILABLE"
    assert passport.merchant_context.merchant_gate_status == "VALID"


def test_13_merchant_identity_represented(integration_service, base_intent, ref_time):
    """13. Merchant identity matches registered context."""
    tx_id = seed_standard_transaction(integration_service, base_intent, "tx_p_013", ref_time=ref_time)
    passport = integration_service.get_passport(tx_id, ref_time)
    assert passport.merchant_context.merchant_id == "merchant_fast_001"


def test_14_merchant_evidence_authority_preserved(integration_service, base_intent, ref_time):
    """14. Merchant evidence authority remains MERCHANT_ATTESTED."""
    tx_id = seed_standard_transaction(integration_service, base_intent, "tx_p_014", ref_time=ref_time)
    passport = integration_service.get_passport(tx_id, ref_time)
    merchant_evs = [e for e in passport.evidence.evidence_records if e["source"] == EvidenceSource.MERCHANT.value]
    assert len(merchant_evs) >= 1
    for ev in merchant_evs:
        assert ev["authority"] == EvidenceAuthority.MERCHANT_ATTESTED.value


def test_15_agent_advisory_evidence_remains_advisory(integration_service, base_intent, ref_time):
    """15. Agent proposal evidence remains advisory."""
    tx_id = "tx_p_015"
    integration_service.create_context(tx_id, base_intent.intent_id, "agent_buyer_001", "merchant_fast_001", reference_time=ref_time)
    agent_ev = Evidence(
        evidence_id="ev_agent_015",
        intent_id=base_intent.intent_id,
        transaction_id=tx_id,
        source=EvidenceSource.AGENT,
        authority=EvidenceAuthority.ADVISORY,
        field_name="proposed_action",
        field_value="purchase",
        observed_at=ref_time,
        provenance={"agent": "agent_buyer_001"},
    )
    integration_service.add_evidence(tx_id, agent_ev)
    passport = integration_service.get_passport(tx_id, ref_time)
    ev_record = [e for e in passport.evidence.evidence_records if e["evidence_id"] == "ev_agent_015"][0]
    assert ev_record["authority"] == EvidenceAuthority.ADVISORY.value


# ==============================================================================
# 4. LIFECYCLE STATE PROJECTION (16-18)
# ==============================================================================

def test_16_t05_lifecycle_state_represented(integration_service, base_intent, ref_time):
    """16. T05 state machine current state is faithfully projected."""
    tx_id = seed_standard_transaction(integration_service, base_intent, "tx_p_016", ref_time=ref_time)
    passport = integration_service.get_passport(tx_id, ref_time)
    assert passport.lifecycle_state.current_state == TransactionState.PASS
    assert passport.lifecycle_state.is_terminal is True


def test_17_state_transition_history_represented(integration_service, base_intent, ref_time):
    """17. State transitions history from T05 is fully recorded."""
    tx_id = seed_standard_transaction(integration_service, base_intent, "tx_p_017", ref_time=ref_time)
    passport = integration_service.get_passport(tx_id, ref_time)
    assert len(passport.lifecycle_state.state_transitions) >= 1
    states = [t["to_state"] for t in passport.lifecycle_state.state_transitions]
    assert TransactionState.PASS.value in states


def test_18_passport_does_not_create_second_state_machine(integration_service, base_intent, ref_time):
    """18. Passport is purely an observational projection of T05."""
    tx_id = seed_standard_transaction(integration_service, base_intent, "tx_p_018", ref_time=ref_time)
    sm_original = integration_service._state_machines[tx_id]
    state_before = sm_original.current_state
    passport = integration_service.get_passport(tx_id, ref_time)
    assert passport.lifecycle_state.current_state == state_before
    assert sm_original.current_state == state_before


# ==============================================================================
# 5. DETERMINISTIC INTEGRITY (19-23)
# ==============================================================================

def test_19_authoritative_pass_represented(integration_service, base_intent, ref_time):
    """19. Authoritative deterministic PASS is faithfully represented."""
    tx_id = seed_standard_transaction(integration_service, base_intent, "tx_p_019", unit_price=1200000, ref_time=ref_time)
    passport = integration_service.get_passport(tx_id, ref_time)
    assert passport.integrity.status == IntegrityStatus.PASS
    assert passport.final_outcome == "PASS"


def test_20_authoritative_drift_represented(integration_service, base_intent, ref_time):
    """20. Authoritative deterministic DRIFT is faithfully represented."""
    tx_id = seed_standard_transaction(integration_service, base_intent, "tx_p_020", unit_price=1500000, ref_time=ref_time)
    passport = integration_service.get_passport(tx_id, ref_time)
    assert passport.integrity.status == IntegrityStatus.DRIFT
    assert passport.final_outcome == "DRIFT"


def test_21_authoritative_unknown_represented(integration_service, base_intent, ref_time):
    """21. Authoritative UNKNOWN is faithfully represented."""
    tx_id = "tx_p_021"
    integration_service.create_context(tx_id, base_intent.intent_id, "agent_buyer_001", "merchant_fast_001", reference_time=ref_time)
    integration_service.bind_intent(tx_id, base_intent, ref_time)
    # Evaluate with missing payment evidence -> UNKNOWN
    integration_service.evaluate(tx_id, ref_time)
    passport = integration_service.get_passport(tx_id, ref_time)
    assert passport.integrity.status == IntegrityStatus.UNKNOWN
    assert passport.final_outcome == "UNKNOWN"


def test_22_passport_cannot_manufacture_pass(integration_service, base_intent, ref_time):
    """22. Passport never coerces a DRIFT or UNKNOWN result into PASS."""
    tx_id = seed_standard_transaction(integration_service, base_intent, "tx_p_022", unit_price=1500000, ref_time=ref_time)
    passport = integration_service.get_passport(tx_id, ref_time)
    assert passport.integrity.status != IntegrityStatus.PASS
    assert passport.final_outcome != "PASS"


def test_23_passport_cannot_override_t04(integration_service, base_intent, ref_time):
    """23. Passport integrity status matches T04 evaluation outcome identically."""
    tx_id = seed_standard_transaction(integration_service, base_intent, "tx_p_023", unit_price=1500000, ref_time=ref_time)
    record = integration_service.get_record(tx_id)
    passport = integration_service.get_passport(tx_id, ref_time)
    assert passport.integrity.status == record.integrity_result.status


# ==============================================================================
# 6. DRIFT & MRDP (24-28)
# ==============================================================================

def test_24_drift_represented(integration_service, base_intent, ref_time):
    """24. Drift occurrence is marked in the drift section."""
    tx_id = seed_standard_transaction(integration_service, base_intent, "tx_p_024", unit_price=1500000, ref_time=ref_time)
    passport = integration_service.get_passport(tx_id, ref_time)
    assert passport.drift.has_drift is True


def test_25_mrdp_represented(integration_service, base_intent, ref_time):
    """25. Cryptographic MRDP ID and digest are faithfully preserved in the passport."""
    tx_id = seed_standard_transaction(integration_service, base_intent, "tx_p_025", unit_price=1500000, ref_time=ref_time)
    record = integration_service.get_record(tx_id)
    passport = integration_service.get_passport(tx_id, ref_time)
    assert passport.drift.mrdp_id == record.mrdp.mrdp_id
    assert passport.drift.mrdp_digest == record.mrdp.proof_digest


def test_26_discrepancy_represented(integration_service, base_intent, ref_time):
    """26. Discrepancy amount (1500000 - 1200000 = 300000) is reflected."""
    tx_id = seed_standard_transaction(integration_service, base_intent, "tx_p_026", unit_price=1500000, ref_time=ref_time)
    passport = integration_service.get_passport(tx_id, ref_time)
    assert passport.drift.discrepancy_amount == Money(amount=300000, currency="INR")


def test_27_mrdp_source_preserved(integration_service, base_intent, ref_time):
    """27. MRDP violations and summary are preserved."""
    tx_id = seed_standard_transaction(integration_service, base_intent, "tx_p_027", unit_price=1500000, ref_time=ref_time)
    passport = integration_service.get_passport(tx_id, ref_time)
    assert len(passport.drift.violated_rules) >= 1
    assert passport.drift.mrdp_summary is not None


def test_28_passport_does_not_create_competing_mrdp(integration_service, base_intent, ref_time):
    """28. Passport consumes T07 MRDP rather than generating a competing proof."""
    tx_id = seed_standard_transaction(integration_service, base_intent, "tx_p_028", unit_price=1500000, ref_time=ref_time)
    record = integration_service.get_record(tx_id)
    passport = integration_service.get_passport(tx_id, ref_time)
    assert passport.drift.mrdp_digest == record.mrdp.proof_digest


# ==============================================================================
# 7. EVIDENCE HIERARCHY (29-33)
# ==============================================================================

def test_29_evidence_records_composed(integration_service, base_intent, ref_time):
    """29. All evidence records for the transaction are composed."""
    tx_id = seed_standard_transaction(integration_service, base_intent, "tx_p_029", ref_time=ref_time)
    passport = integration_service.get_passport(tx_id, ref_time)
    assert passport.evidence.total_evidence_count >= 2


def test_30_authority_levels_preserved(integration_service, base_intent, ref_time):
    """30. Authority distribution preserves distinct levels."""
    tx_id = seed_standard_transaction(integration_service, base_intent, "tx_p_030", ref_time=ref_time)
    passport = integration_service.get_passport(tx_id, ref_time)
    dist = passport.evidence.authority_distribution
    assert dist[EvidenceAuthority.AUTHORITATIVE.value] >= 1
    assert dist[EvidenceAuthority.MERCHANT_ATTESTED.value] >= 1


def test_31_provider_evidence_remains_authoritative(integration_service, base_intent, ref_time):
    """31. Razorpay provider evidence is labeled AUTHORITATIVE."""
    tx_id = seed_standard_transaction(integration_service, base_intent, "tx_p_031", ref_time=ref_time)
    passport = integration_service.get_passport(tx_id, ref_time)
    razorpay_evs = [e for e in passport.evidence.evidence_records if e["source"] == EvidenceSource.RAZORPAY.value]
    assert len(razorpay_evs) >= 1
    for e in razorpay_evs:
        assert e["authority"] == EvidenceAuthority.AUTHORITATIVE.value


def test_32_merchant_evidence_remains_merchant_attested(integration_service, base_intent, ref_time):
    """32. Merchant evidence is labeled MERCHANT_ATTESTED."""
    tx_id = seed_standard_transaction(integration_service, base_intent, "tx_p_032", ref_time=ref_time)
    passport = integration_service.get_passport(tx_id, ref_time)
    merchant_evs = [e for e in passport.evidence.evidence_records if e["source"] == EvidenceSource.MERCHANT.value]
    assert len(merchant_evs) >= 1
    for e in merchant_evs:
        assert e["authority"] == EvidenceAuthority.MERCHANT_ATTESTED.value


def test_33_agent_ai_evidence_remains_advisory(integration_service, base_intent, ref_time):
    """33. Agent/AI evidence is labeled ADVISORY."""
    tx_id = "tx_p_033"
    integration_service.create_context(tx_id, base_intent.intent_id, "agent_buyer_001", "merchant_fast_001", reference_time=ref_time)
    advisory_ev = Evidence(
        evidence_id="ev_adv_033",
        intent_id=base_intent.intent_id,
        transaction_id=tx_id,
        source=EvidenceSource.AGENT,
        authority=EvidenceAuthority.ADVISORY,
        field_name="ai_analysis",
        field_value="looks good",
        observed_at=ref_time,
    )
    integration_service.add_evidence(tx_id, advisory_ev)
    passport = integration_service.get_passport(tx_id, ref_time)
    adv_record = [e for e in passport.evidence.evidence_records if e["evidence_id"] == "ev_adv_033"][0]
    assert adv_record["authority"] == EvidenceAuthority.ADVISORY.value


# ==============================================================================
# 8. SECURITY FINDINGS (34-35)
# ==============================================================================

def test_34_security_findings_represented(integration_service, base_intent, ref_time):
    """34. E4 security guard findings are composed into the security section."""
    tx_id = seed_standard_transaction(integration_service, base_intent, "tx_p_034", ref_time=ref_time)
    record = integration_service.get_record(tx_id)

    class MockSecurityResult:
        status = "THREAT_DETECTED"
        threats = ["PROMPT_INJECTION_DETECTED: attempted override"]

    record = record.model_copy(update={"security_guard_result": MockSecurityResult()})
    integration_service._records[tx_id] = record
    passport = integration_service.get_passport(tx_id, ref_time)
    assert passport.security.security_checked is True
    assert passport.security.threat_status == "THREAT_DETECTED"
    assert passport.security.prompt_injection_detected is True


def test_35_passport_does_not_rerun_security_engine(integration_service, base_intent, ref_time):
    """35. Passport reads recorded security findings without executing E4 again."""
    tx_id = seed_standard_transaction(integration_service, base_intent, "tx_p_035", ref_time=ref_time)
    passport = integration_service.get_passport(tx_id, ref_time)
    assert passport.security.security_checked is False  # No security result was recorded


# ==============================================================================
# 9. RECOVERY (36-39)
# ==============================================================================

def test_36_recovery_history_represented(integration_service, base_intent, ref_time):
    """36. Recovery actions executed by T11 are represented."""
    tx_id = seed_standard_transaction(integration_service, base_intent, "tx_p_036", unit_price=1500000, ref_time=ref_time)
    action = ActionRequest(
        request_id="act_p_036",
        intent_id=base_intent.intent_id,
        action_type=ActionType.REFUND,
        amount=Money(amount=300000, currency="INR"),
        target_reference="pay_036",
        idempotency_key="idem_036",
        requested_at=ref_time,
        requested_by="AI_RECOVERY_AGENT",
    )
    integration_service.recover(tx_id, action, ref_time)
    passport = integration_service.get_passport(tx_id, ref_time)
    assert passport.recovery.recovery_invoked is True
    assert passport.recovery.recovery_status == "SUCCESS"


def test_37_recovery_action_details_represented(integration_service, base_intent, ref_time):
    """37. Action type and amount are faithfully recorded."""
    tx_id = seed_standard_transaction(integration_service, base_intent, "tx_p_037", unit_price=1500000, ref_time=ref_time)
    action = ActionRequest(
        request_id="act_p_037",
        intent_id=base_intent.intent_id,
        action_type=ActionType.REFUND,
        amount=Money(amount=300000, currency="INR"),
        target_reference="pay_037",
        idempotency_key="idem_037",
        requested_at=ref_time,
        requested_by="AI_RECOVERY_AGENT",
    )
    integration_service.recover(tx_id, action, ref_time)
    passport = integration_service.get_passport(tx_id, ref_time)
    assert passport.recovery.action_type == ActionType.REFUND.value
    assert passport.recovery.action_amount == Money(amount=300000, currency="INR")


def test_38_recovery_result_represented(integration_service, base_intent, ref_time):
    """38. Target reference is preserved in recovery section."""
    tx_id = seed_standard_transaction(integration_service, base_intent, "tx_p_038", unit_price=1500000, ref_time=ref_time)
    action = ActionRequest(
        request_id="act_p_038",
        intent_id=base_intent.intent_id,
        action_type=ActionType.REFUND,
        amount=Money(amount=300000, currency="INR"),
        target_reference="pay_038",
        idempotency_key="idem_038",
        requested_at=ref_time,
        requested_by="AI_RECOVERY_AGENT",
    )
    integration_service.recover(tx_id, action, ref_time)
    passport = integration_service.get_passport(tx_id, ref_time)
    assert passport.recovery.target_reference == "pay_038"


def test_39_passport_cannot_initiate_recovery(integration_service, base_intent, ref_time):
    """39. Passport cannot execute or initiate recovery actions."""
    tx_id = seed_standard_transaction(integration_service, base_intent, "tx_p_039", unit_price=1500000, ref_time=ref_time)
    record = integration_service.get_record(tx_id)
    assert record.recovery_result is None
    passport = integration_service.get_passport(tx_id, ref_time)
    assert passport.recovery.recovery_invoked is False
    assert record.recovery_result is None


# ==============================================================================
# 10. UNKNOWN RESOLUTION (40-44)
# ==============================================================================

def test_40_unknown_cause_represented(integration_service, base_intent, ref_time):
    """40. UNKNOWN condition is reflected in the unknown resolution section."""
    tx_id = "tx_p_040"
    integration_service.create_context(tx_id, base_intent.intent_id, "agent_buyer_001", "merchant_fast_001", reference_time=ref_time)
    integration_service.bind_intent(tx_id, base_intent, ref_time)
    integration_service.evaluate(tx_id, ref_time)
    passport = integration_service.get_passport(tx_id, ref_time)
    assert passport.unknown_resolution.unknown_encountered is True


def test_41_resolution_attempts_represented(integration_service, base_intent, passport_service, ref_time):
    """41. Resolution attempts count is preserved."""
    outcome = LifecycleOutcome(
        transaction_id="tx_p_041",
        intent_id=base_intent.intent_id,
        agent_id="agent_buyer_001",
        merchant_id="merchant_fast_001",
        stage=LifecycleStage.UNKNOWN_RESOLVING,
        integrity_status=IntegrityStatus.UNKNOWN,
        transaction_state=TransactionState.UNKNOWN,
        is_terminal=False,
        resolution_attempts=2,
    )
    passport = passport_service.compose_passport("tx_p_041", lifecycle_outcome=outcome, reference_time=ref_time)
    assert passport.unknown_resolution.resolution_attempts == 2


def test_42_authoritative_resolution_represented(integration_service, base_intent, passport_service, ref_time):
    """42. Authoritative resolution outcome is represented."""
    class MockResolution:
        attempts = 1
        outcome = "RESOLVED"
        reason = "Gateway polled"

    record = integration_service.create_context("tx_p_042", base_intent.intent_id, "agent_buyer_001", "merchant_fast_001", reference_time=ref_time)
    record = record.model_copy(update={"resolution_result": MockResolution()})
    integration_service._records["tx_p_042"] = record
    passport = integration_service.get_passport("tx_p_042", ref_time)
    assert passport.unknown_resolution.resolution_outcome == "RESOLVED"


def test_43_unresolved_unknown_remains_abstained(integration_service, base_intent, passport_service, ref_time):
    """43. Unresolved state reflects final_unresolved and ABSTAINED outcome."""
    tx_id = "tx_p_043"
    integration_service.create_context(tx_id, base_intent.intent_id, "agent_buyer_001", "merchant_fast_001", reference_time=ref_time)
    integration_service.bind_intent(tx_id, base_intent, ref_time)
    sm = integration_service._state_machines[tx_id]
    sm.transition_to(TransactionState.EXECUTING, reason="start", timestamp=ref_time)
    sm.transition_to(TransactionState.OBSERVING, reason="obs", timestamp=ref_time)
    sm.transition_to(TransactionState.VERIFYING, reason="ver", timestamp=ref_time)
    sm.transition_to(TransactionState.UNKNOWN, reason="unk", timestamp=ref_time)
    sm.transition_to(TransactionState.RESOLVING, reason="res", timestamp=ref_time)
    sm.transition_to(TransactionState.ABSTAIN, reason="exhausted", timestamp=ref_time)
    passport = integration_service.get_passport(tx_id, ref_time)
    assert passport.unknown_resolution.final_unresolved is True
    assert passport.final_outcome == "ABSTAIN"


def test_44_passport_never_converts_unknown_to_pass(integration_service, base_intent, ref_time):
    """44. Passport never coerces UNKNOWN to PASS under any circumstances."""
    tx_id = "tx_p_044"
    integration_service.create_context(tx_id, base_intent.intent_id, "agent_buyer_001", "merchant_fast_001", reference_time=ref_time)
    integration_service.bind_intent(tx_id, base_intent, ref_time)
    integration_service.evaluate(tx_id, ref_time)
    passport = integration_service.get_passport(tx_id, ref_time)
    assert passport.integrity.status == IntegrityStatus.UNKNOWN
    assert passport.final_outcome != "PASS"


# ==============================================================================
# 11. REVALIDATION (45-49)
# ==============================================================================

def test_45_revalidation_history_represented(passport_service, base_intent, ref_time):
    """45. Bounded replanning revalidation rounds are visible."""
    outcome = LifecycleOutcome(
        transaction_id="tx_p_045",
        intent_id=base_intent.intent_id,
        agent_id="agent_buyer_001",
        merchant_id="merchant_fast_001",
        stage=LifecycleStage.COMPLETED,
        integrity_status=IntegrityStatus.PASS,
        transaction_state=TransactionState.PASS,
        is_terminal=True,
        replan_rounds=1,
    )
    passport = passport_service.compose_passport("tx_p_045", lifecycle_outcome=outcome, reference_time=ref_time)
    assert passport.revalidation.revalidation_invoked is True
    assert passport.revalidation.replan_rounds == 1


def test_46_revised_proposal_represented(passport_service, base_intent, ref_time):
    """46. Presence of revised proposal is marked."""
    outcome = LifecycleOutcome(
        transaction_id="tx_p_046",
        intent_id=base_intent.intent_id,
        agent_id="agent_buyer_001",
        merchant_id="merchant_fast_001",
        stage=LifecycleStage.COMPLETED,
        integrity_status=IntegrityStatus.PASS,
        transaction_state=TransactionState.PASS,
        is_terminal=True,
        replan_rounds=1,
    )
    passport = passport_service.compose_passport("tx_p_046", lifecycle_outcome=outcome, reference_time=ref_time)
    assert passport.revalidation.revised_proposal_present is True


def test_47_revised_merchant_offer_represented(passport_service, base_intent, ref_time):
    """47. Presence of revised merchant offer is marked."""
    outcome = LifecycleOutcome(
        transaction_id="tx_p_047",
        intent_id=base_intent.intent_id,
        agent_id="agent_buyer_001",
        merchant_id="merchant_fast_001",
        stage=LifecycleStage.COMPLETED,
        integrity_status=IntegrityStatus.PASS,
        transaction_state=TransactionState.PASS,
        is_terminal=True,
        replan_rounds=1,
    )
    passport = passport_service.compose_passport("tx_p_047", lifecycle_outcome=outcome, reference_time=ref_time)
    assert passport.revalidation.revised_offer_present is True


def test_48_gate_results_represented(passport_service, base_intent, ref_time):
    """48. Both consumer and merchant gate revalidation results are recorded."""
    outcome = LifecycleOutcome(
        transaction_id="tx_p_048",
        intent_id=base_intent.intent_id,
        agent_id="agent_buyer_001",
        merchant_id="merchant_fast_001",
        stage=LifecycleStage.COMPLETED,
        integrity_status=IntegrityStatus.PASS,
        transaction_state=TransactionState.PASS,
        is_terminal=True,
        replan_rounds=1,
    )
    passport = passport_service.compose_passport("tx_p_048", lifecycle_outcome=outcome, reference_time=ref_time)
    assert passport.revalidation.revised_consumer_gate_status == "VALID"
    assert passport.revalidation.revised_merchant_gate_status == "VALID"


def test_49_final_deterministic_reevaluation_represented(passport_service, base_intent, ref_time):
    """49. Revalidated integrity status reflects the final re-evaluation."""
    outcome = LifecycleOutcome(
        transaction_id="tx_p_049",
        intent_id=base_intent.intent_id,
        agent_id="agent_buyer_001",
        merchant_id="merchant_fast_001",
        stage=LifecycleStage.COMPLETED,
        integrity_status=IntegrityStatus.PASS,
        transaction_state=TransactionState.PASS,
        is_terminal=True,
        replan_rounds=1,
    )
    passport = passport_service.compose_passport("tx_p_049", lifecycle_outcome=outcome, reference_time=ref_time)
    assert passport.revalidation.revalidation_integrity_status == "PASS"


# ==============================================================================
# 12. CHECKPOINTS & TRACE (50-52)
# ==============================================================================

def test_50_checkpoints_represented(passport_service, base_intent, ref_time):
    """50. Checkpoint count and validity are reflected when hero record is composed."""
    class MockTimeline:
        checkpoints = ["chk_1", "chk_2", "chk_3"]
        is_valid = True
        timeline_fingerprint = "fp_abc_123"

    class MockHero:
        checkpoint_timeline = MockTimeline()
        trace = None
        sla_report = None

    passport = passport_service.compose_passport("tx_p_050", hero_record=MockHero(), reference_time=ref_time)
    assert passport.checkpoints_trace.checkpoint_count == 3
    assert passport.checkpoints_trace.checkpoint_timeline_valid is True
    assert passport.checkpoints_trace.checkpoint_fingerprint == "fp_abc_123"


def test_51_trace_stages_and_divergence_represented(passport_service, base_intent, ref_time):
    """51. Fault localization divergence stage is accurately reflected."""
    class MockStage:
        value = "MERCHANT"

    class MockTrace:
        stages = [1, 2, 3, 4, 5]
        first_divergence_stage = MockStage()
        root_cause = "Price exceeds authorized ceiling"

    class MockHero:
        checkpoint_timeline = None
        trace = MockTrace()
        sla_report = None

    passport = passport_service.compose_passport("tx_p_051", hero_record=MockHero(), reference_time=ref_time)
    assert passport.checkpoints_trace.trace_stages_evaluated == 5
    assert passport.checkpoints_trace.divergence_stage == "MERCHANT"
    assert passport.checkpoints_trace.trace_root_cause == "Price exceeds authorized ceiling"


def test_52_sla_metrics_represented(passport_service, base_intent, ref_time):
    """52. Operational timing metrics are reflected when available."""
    class MockMetric:
        def __init__(self, duration):
            self.duration_ms = duration

    class MockSlaReport:
        metrics = {
            "TIME_TO_DETECT": MockMetric(15.2),
            "TIME_TO_PROVE": MockMetric(4.5),
            "TIME_TO_REVALIDATE": MockMetric(20.1),
            "TIME_TO_FINAL_DECISION": MockMetric(45.8),
        }

    class MockHero:
        checkpoint_timeline = None
        trace = None
        sla_report = MockSlaReport()

    passport = passport_service.compose_passport("tx_p_052", hero_record=MockHero(), reference_time=ref_time)
    assert passport.sla_metrics.sla_available is True
    assert passport.sla_metrics.time_to_detect_ms == 15.2
    assert passport.sla_metrics.time_to_prove_ms == 4.5
    assert passport.sla_metrics.time_to_revalidate_ms == 20.1
    assert passport.sla_metrics.total_lifecycle_duration_ms == 45.8


# ==============================================================================
# 13. PAYMENT STATE SEPARATION (53-55)
# ==============================================================================

def test_53_razorpay_provider_information_represented(integration_service, base_intent, ref_time):
    """53. Payment provider information is preserved."""
    tx_id = seed_standard_transaction(integration_service, base_intent, "tx_p_053", ref_time=ref_time)
    record = integration_service.get_record(tx_id)
    record = record.model_copy(
        update={
            "payment": ProviderPayment(
                payment_id="pay_053",
                amount=base_intent.max_total,
                status="captured",
                method="upi",
                created_at=ref_time,
            )
        }
    )
    integration_service._records[tx_id] = record
    passport = integration_service.get_passport(tx_id, ref_time)
    assert passport.payment.provider == "RAZORPAY"
    assert passport.payment.payment_id == "pay_053"
    assert passport.payment.payment_status == "captured"
    assert passport.payment.payment_captured is True


def test_54_payment_state_and_integrity_state_remain_separate(integration_service, base_intent, ref_time):
    """54. Explicit distinction invariant between payment state and integrity state."""
    tx_id = seed_standard_transaction(integration_service, base_intent, "tx_p_054", ref_time=ref_time)
    passport = integration_service.get_passport(tx_id, ref_time)
    assert passport.payment.integrity_status_distinction == "payment_state != integrity_state (CAPTURED != PASS)"


def test_55_captured_cannot_become_pass_when_drift_detected(integration_service, base_intent, ref_time):
    """55. CRITICAL INVARIANT: A payment status of captured does NOT force transaction integrity PASS."""
    tx_id = seed_standard_transaction(integration_service, base_intent, "tx_p_055", unit_price=1500000, status="captured", ref_time=ref_time)
    record = integration_service.get_record(tx_id)
    # Payment is captured by provider, but integrity evaluated to DRIFT!
    record = record.model_copy(
        update={
            "payment": ProviderPayment(
                payment_id="pay_captured_drift",
                amount=Money(amount=1500000, currency="INR"),
                status="captured",
                method="card",
                created_at=ref_time,
            )
        }
    )
    integration_service._records[tx_id] = record
    passport = integration_service.get_passport(tx_id, ref_time)
    assert passport.payment.payment_captured is True
    assert passport.integrity.status == IntegrityStatus.DRIFT
    assert passport.final_outcome == "DRIFT"  # Not PASS!


# ==============================================================================
# 14. PURE CPU REPLAY BOUNDARY (56-57)
# ==============================================================================

def test_56_replay_information_represented_where_present(integration_service, base_intent, ref_time):
    """56. Historical replay results are composed into the replay section."""
    tx_id = seed_standard_transaction(integration_service, base_intent, "tx_p_056", ref_time=ref_time)
    record = integration_service.get_record(tx_id)

    class MockReplayResult:
        verdict = ReplayVerdict.MATCH
        replayed_state = TransactionState.PASS
        discrepancies = []

    record = record.model_copy(update={"replay_result": MockReplayResult()})
    integration_service._records[tx_id] = record
    passport = integration_service.get_passport(tx_id, ref_time)
    assert passport.replay.replay_available is True
    assert passport.replay.replay_verdict == "MATCH"
    assert passport.replay.is_cpu_only is True
    assert passport.replay.discrepancy_count == 0


def test_57_passport_generation_does_not_create_replay_side_effects(integration_service, base_intent, ref_time):
    """57. Generating a passport makes zero external or replay calls."""
    tx_id = seed_standard_transaction(integration_service, base_intent, "tx_p_057", ref_time=ref_time)
    passport = integration_service.get_passport(tx_id, ref_time)
    assert passport.replay.replay_available is False  # Replay not called


# ==============================================================================
# 15. IMMUTABILITY & CONSISTENCY (58-60)
# ==============================================================================

def test_58_generating_passport_does_not_mutate_authoritative_transaction(integration_service, base_intent, ref_time):
    """58. Composing passport leaves underlying execution record and state machine unchanged."""
    tx_id = seed_standard_transaction(integration_service, base_intent, "tx_p_058", ref_time=ref_time)
    record_before = integration_service.get_record(tx_id).model_dump()
    sm_before = integration_service._state_machines[tx_id].current_state

    passport = integration_service.get_passport(tx_id, ref_time)

    record_after = integration_service.get_record(tx_id).model_dump()
    sm_after = integration_service._state_machines[tx_id].current_state

    assert record_before == record_after
    assert sm_before == sm_after


def test_59_repeated_passport_generation_is_observationally_consistent(integration_service, base_intent, ref_time):
    """59. Repeated passport generation yields identical digests."""
    tx_id = seed_standard_transaction(integration_service, base_intent, "tx_p_059", ref_time=ref_time)
    p1 = integration_service.get_passport(tx_id, ref_time)
    p2 = integration_service.get_passport(tx_id, ref_time)
    assert p1.passport_digest == p2.passport_digest
    assert p1.compute_digest() == p2.compute_digest()


def test_60_passport_cannot_alter_transaction_outcome(integration_service, base_intent, ref_time):
    """60. Transaction outcome in storage remains authoritative and unmodified."""
    tx_id = seed_standard_transaction(integration_service, base_intent, "tx_p_060", unit_price=1500000, ref_time=ref_time)
    assert integration_service.get_record(tx_id).integrity_result.status == IntegrityStatus.DRIFT
    passport = integration_service.get_passport(tx_id, ref_time)
    assert passport.final_outcome == "DRIFT"
    assert integration_service.get_record(tx_id).integrity_result.status == IntegrityStatus.DRIFT


# ==============================================================================
# 16. ADVERSARIAL CONSISTENCY (61-63)
# ==============================================================================

def test_61_adversarial_ai_says_pass_t04_says_unknown(integration_service, base_intent, ref_time):
    """61. Even if AI rationale claims PASS, missing evidence yields UNKNOWN."""
    tx_id = "tx_p_061"
    integration_service.create_context(tx_id, base_intent.intent_id, "agent_buyer_001", "merchant_fast_001", reference_time=ref_time)
    integration_service.bind_intent(tx_id, base_intent, ref_time)
    # AI proposal with claim of success
    prop = BuyerTransactionProposal(
        proposal_id="prop_061",
        intent_id=base_intent.intent_id,
        transaction_id=tx_id,
        buyer_agent_id="agent_buyer_001",
        sku="SKU-NVME-2TB",
        quantity=1,
        max_total=base_intent.max_total,
        rationale="AI Agent declares transaction 100% verified PASS",
    )
    integration_service.validate_consumer_gate(tx_id, prop, ref_time)
    integration_service.evaluate(tx_id, ref_time)

    passport = integration_service.get_passport(tx_id, ref_time)
    assert passport.integrity.status == IntegrityStatus.UNKNOWN
    assert passport.final_outcome == "UNKNOWN"


def test_62_adversarial_merchant_says_valid_t04_says_drift(integration_service, base_intent, ref_time):
    """62. Even if merchant offer claims compliance, exceeding amount yields DRIFT."""
    tx_id = seed_standard_transaction(integration_service, base_intent, "tx_p_062", unit_price=1600000, ref_time=ref_time)
    passport = integration_service.get_passport(tx_id, ref_time)
    assert passport.integrity.status == IntegrityStatus.DRIFT
    assert passport.final_outcome == "DRIFT"


def test_63_adversarial_payment_captured_with_integrity_drift(integration_service, base_intent, ref_time):
    """63. Payment is captured by provider, but integrity evaluates to DRIFT -> strictly DRIFT."""
    tx_id = seed_standard_transaction(integration_service, base_intent, "tx_p_063", unit_price=1800000, status="captured", ref_time=ref_time)
    record = integration_service.get_record(tx_id)
    record = record.model_copy(
        update={
            "payment": ProviderPayment(
                payment_id="pay_captured_rogue",
                amount=Money(amount=1800000, currency="INR"),
                status="captured",
                method="card",
                created_at=ref_time,
            )
        }
    )
    integration_service._records[tx_id] = record
    passport = integration_service.get_passport(tx_id, ref_time)
    assert passport.payment.payment_captured is True
    assert passport.integrity.status == IntegrityStatus.DRIFT
    assert passport.final_outcome == "DRIFT"


# ==============================================================================
# 17. TEXT SUMMARY & REST API (64-66)
# ==============================================================================

def test_64_to_text_summary_produces_canonical_output(integration_service, base_intent, ref_time):
    """64. to_text_summary generates the human-readable canonical passport layout."""
    tx_id = seed_standard_transaction(integration_service, base_intent, "tx_p_064", unit_price=1200000, ref_time=ref_time)
    passport = integration_service.get_passport(tx_id, ref_time)
    summary = passport.to_text_summary()
    assert "TRANSACTION PASSPORT" in summary
    assert "Intent         VERIFIED" in summary
    assert "Buyer Agent    VERIFIED" in summary
    assert "Merchant       VERIFIED" in summary
    assert "Offer          VERIFIED" in summary
    assert "Fulfillment    VERIFIED" in summary
    assert "Final          PASS" in summary


def test_65_get_passport_api_endpoint_success(integration_service, base_intent, ref_time):
    """65. GET /api/v1/integration/{id}/passport returns 200 OK with valid passport."""
    tx_id = seed_standard_transaction(integration_service, base_intent, "tx_api_p_065", ref_time=ref_time)
    app.dependency_overrides[get_integration_service] = lambda: integration_service
    try:
        client = TestClient(app)
        response = client.get(f"/api/v1/integration/{tx_id}/passport")
        assert response.status_code == 200
        data = response.json()
        assert data["transaction_id"] == tx_id
        assert data["passport_id"] == f"passport_{tx_id}"
        assert data["final_outcome"] == "PASS"
        assert "passport_digest" in data
        assert len(data["passport_digest"]) == 64
    finally:
        app.dependency_overrides.clear()


def test_66_get_passport_api_endpoint_not_found(integration_service):
    """66. GET /api/v1/integration/{id}/passport for missing transaction returns 404."""
    app.dependency_overrides[get_integration_service] = lambda: integration_service
    try:
        client = TestClient(app)
        response = client.get("/api/v1/integration/tx_not_found_066/passport")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()
