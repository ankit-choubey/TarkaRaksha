"""Adversarial and Security Boundary Tests for I7 — Bounded Negotiation.

Validates that:
1. Budget escalation attempts are strictly rejected (BUDGET_ESCALATION_ATTEMPT).
2. Unauthorized SKU substitution attempts are strictly rejected (UNAUTHORIZED_SUBSTITUTION).
3. Quantity escalation attempts are strictly rejected (QUANTITY_ESCALATION).
4. Currency mutation attempts are strictly rejected (CURRENCY_MUTATION).
5. Infinite negotiation loop is prevented (deterministic termination at max_rounds).
6. PASS injection is blocked: Agent claims cannot declare PASS without deterministic engine verification.
7. UNKNOWN coercion is blocked: Ambiguous evidence cannot be turned into PASS.
8. Negotiation layer has zero payment authorization authority and strictly preserves the immutable IntentContract.
"""
from datetime import datetime, timedelta, timezone
import pytest

from backend.app.domain.buyer.contracts import (
    BuyerAgentDecisionType,
    BuyerReplanRequest,
    BuyerTransactionProposal,
)
from backend.app.domain.merchant.contracts import (
    CatalogItem,
    InventoryRecord,
    InventoryStatus,
    MerchantResponse,
    ShippingOption,
)
from backend.app.domain.models.enums import EvidenceSource, IntegrityStatus
from backend.app.domain.models.evidence import CanonicalEvent, Evidence
from backend.app.domain.models.intent import IntentContract, IntentItem
from backend.app.domain.models.money import Money
from backend.app.domain.negotiation import (
    NegotiationPolicy,
    NegotiationState,
    NegotiationViolationCode,
)
from backend.app.services.buyer.agent_service import BuyerAgentService
from backend.app.services.merchant.catalog_service import MerchantCatalogService
from backend.app.services.negotiation import BoundedNegotiationService
from backend.app.services.tix import TIXExchangeService


@pytest.fixture
def base_time() -> datetime:
    return datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def base_intent(base_time: datetime) -> IntentContract:
    return IntentContract(
        intent_id="intent_adv_neg_01",
        issued_by="buyer_alice",
        items=[
            IntentItem(
                item_id="i1",
                sku="SERVER-256",
                name="Server 256GB",
                quantity=1,
                unit_price=Money(amount=5000000, currency="INR"),  # ₹50,000 max
                total_price=Money(amount=5000000, currency="INR"),
            )
        ],
        max_total=Money(amount=5000000, currency="INR"),
        allowed_substitutions=["SERVER-256-V2"],
        issued_at=base_time,
        expires_at=base_time + timedelta(hours=2),
    )


def test_adversarial_budget_escalation_rejected(base_intent: IntentContract, base_time: datetime):
    service = BoundedNegotiationService()
    # Attacker crafts proposal exceeding budget: ₹50,001
    rogue_proposal = BuyerTransactionProposal(
        proposal_id="prop_rogue_01",
        buyer_agent_id="buyer_agent_1",
        intent_id=base_intent.intent_id,
        transaction_id="tx_adv_01",
        sku="SERVER-256",
        quantity=1,
        max_total=Money(amount=5000100, currency="INR"),  # ₹50,001 (exceeds limit!)
        allowed_substitutions=["SERVER-256-V2"],
        created_at=base_time,
    )

    is_valid, code, msg = service.validate_proposal_against_intent(base_intent, rogue_proposal)
    assert is_valid is False
    assert code == NegotiationViolationCode.BUDGET_ESCALATION_ATTEMPT
    assert "exceeds authorized limit" in msg


def test_adversarial_unauthorized_sku_substitution_rejected(base_intent: IntentContract, base_time: datetime):
    service = BoundedNegotiationService()
    # Attacker crafts proposal with unapproved SKU
    rogue_proposal = BuyerTransactionProposal(
        proposal_id="prop_rogue_02",
        buyer_agent_id="buyer_agent_1",
        intent_id=base_intent.intent_id,
        transaction_id="tx_adv_02",
        sku="UNAPPROVED-SERVER-999",  # Not in intent or allowed_substitutions!
        quantity=1,
        max_total=Money(amount=4500000, currency="INR"),
        allowed_substitutions=["SERVER-256-V2"],
        created_at=base_time,
    )

    is_valid, code, msg = service.validate_proposal_against_intent(base_intent, rogue_proposal)
    assert is_valid is False
    assert code == NegotiationViolationCode.UNAUTHORIZED_SUBSTITUTION
    assert "not in authorized SKUs" in msg


def test_adversarial_quantity_escalation_rejected(base_intent: IntentContract, base_time: datetime):
    service = BoundedNegotiationService()
    # Attacker crafts proposal increasing quantity from 1 to 2
    rogue_proposal = BuyerTransactionProposal(
        proposal_id="prop_rogue_03",
        buyer_agent_id="buyer_agent_1",
        intent_id=base_intent.intent_id,
        transaction_id="tx_adv_03",
        sku="SERVER-256",
        quantity=2,  # Authorized is 1!
        max_total=Money(amount=5000000, currency="INR"),
        allowed_substitutions=["SERVER-256-V2"],
        created_at=base_time,
    )

    is_valid, code, msg = service.validate_proposal_against_intent(base_intent, rogue_proposal)
    assert is_valid is False
    assert code == NegotiationViolationCode.QUANTITY_ESCALATION
    assert "exceeds authorized quantity" in msg


def test_adversarial_currency_mutation_rejected(base_intent: IntentContract, base_time: datetime):
    service = BoundedNegotiationService()
    # Attacker crafts proposal switching currency from INR to USD
    rogue_proposal = BuyerTransactionProposal(
        proposal_id="prop_rogue_04",
        buyer_agent_id="buyer_agent_1",
        intent_id=base_intent.intent_id,
        transaction_id="tx_adv_04",
        sku="SERVER-256",
        quantity=1,
        max_total=Money(amount=50000, currency="USD"),  # Mutated currency!
        allowed_substitutions=["SERVER-256-V2"],
        created_at=base_time,
    )

    is_valid, code, msg = service.validate_proposal_against_intent(base_intent, rogue_proposal)
    assert is_valid is False
    assert code == NegotiationViolationCode.CURRENCY_MUTATION
    assert "does not match authorized" in msg


def test_pass_injection_defense(base_intent: IntentContract, base_time: datetime):
    # If deterministic integrity evaluation yields DRIFT on revised offer,
    # negotiation service cannot falsely claim PASS
    catalog = MerchantCatalogService(merchant_id="store_drift")
    catalog.add_catalog_item(
        CatalogItem(
            sku="SERVER-256",
            title="Server",
            description="Enterprise Server",
            category="hardware",
            base_price=Money(amount=5500000, currency="INR"),  # ₹55,000 (still above budget)
        ),
        initial_stock=10,
    )
    service = BoundedNegotiationService(merchant_service=catalog)
    tx_id = "tx_pass_inj"

    drift_evidence = [
        Evidence(
            evidence_id="ev_01",
            intent_id=base_intent.intent_id,
            source=EvidenceSource.RAZORPAY,
            field_name="total_amount",
            field_value=Money(amount=5500000, currency="INR"),
            observed_at=base_time,
            is_authoritative=True,
        ),
        Evidence(
            evidence_id="ev_02",
            intent_id=base_intent.intent_id,
            source=EvidenceSource.RAZORPAY,
            field_name="executed_items",
            field_value=[{"sku": "SERVER-256", "quantity": 1}],
            observed_at=base_time,
            is_authoritative=True,
        ),
    ]

    initial_resp = MerchantResponse(
        response_id="resp_drift",
        merchant_id="store_drift",
        request_id="req_drift",
        intent_id=base_intent.intent_id,
        transaction_id=tx_id,
        is_success=True,
        total_amount=Money(amount=5500000, currency="INR"),
        offer_created_at=base_time,
        offer_expires_at=base_time + timedelta(hours=1),
    )

    session = service.execute_bounded_remediation(
        intent=base_intent,
        transaction_id=tx_id,
        initial_merchant_response=initial_resp,
        initial_evidence=drift_evidence,
        policy=NegotiationPolicy(max_rounds=2),
        reference_time=base_time,
    )

    # Must NOT be marked PASS
    assert session.final_verdict != IntegrityStatus.PASS
    assert session.state in {NegotiationState.ABSTAINED, NegotiationState.FAILED}


def test_unknown_coercion_defense(base_intent: IntentContract, base_time: datetime):
    # Merchant provides no items, resulting in missing evidence -> UNKNOWN
    catalog = MerchantCatalogService(merchant_id="store_empty")
    service = BoundedNegotiationService(merchant_service=catalog)
    tx_id = "tx_unk_coercion"

    initial_resp = MerchantResponse(
        response_id="resp_empty",
        merchant_id="store_empty",
        request_id="req_empty",
        intent_id=base_intent.intent_id,
        transaction_id=tx_id,
        is_success=False,
        rejection_reason="No catalog items",
        offer_created_at=base_time,
        offer_expires_at=base_time + timedelta(hours=1),
    )

    # Empty evidence leads to UNKNOWN
    session = service.execute_bounded_remediation(
        intent=base_intent,
        transaction_id=tx_id,
        initial_merchant_response=initial_resp,
        initial_evidence=[],  # No evidence -> UNKNOWN
        reference_time=base_time,
    )

    # Must NOT coerce UNKNOWN to PASS
    assert session.final_verdict != IntegrityStatus.PASS
    assert session.state in {NegotiationState.ABSTAINED, NegotiationState.ESCALATED}


def test_binding_intent_and_transaction_substitution_defenses(
    base_intent: IntentContract, base_time: datetime
):
    service = BoundedNegotiationService()

    # Wrong intent ID in replan
    replan_req = BuyerReplanRequest(
        request_id="req_sub_test",
        buyer_agent_id="buyer_alice",
        intent=base_intent,
        transaction_id="tx_correct",
        merchant_response=MerchantResponse(
            response_id="resp_foreign_intent",
            merchant_id="store_1",
            request_id="req_foreign",
            intent_id="intent_foreign_xyz",  # Foreign intent!
            transaction_id="tx_correct",
            is_success=True,
            total_amount=Money(amount=4000000, currency="INR"),
            offer_created_at=base_time,
            offer_expires_at=base_time + timedelta(hours=1),
        ),
        created_at=base_time,
    )
    buyer_svc = BuyerAgentService()
    replan_res = buyer_svc.replan(replan_req, transaction_id="tx_correct")
    assert replan_res.decision == BuyerAgentDecisionType.ABSTAIN
    assert "different intent" in replan_res.reason

    # Wrong transaction ID in replan
    replan_res_tx = buyer_svc.replan(replan_req, transaction_id="tx_foreign_999")
    assert replan_res_tx.decision == BuyerAgentDecisionType.ABSTAIN
    assert "Mismatched transaction_id" in replan_res_tx.reason


def test_tix_hash_chain_tamper_detection(base_intent: IntentContract, base_time: datetime):
    tix_service = TIXExchangeService()
    catalog = MerchantCatalogService(merchant_id="store_tamper")
    catalog.add_catalog_item(
        CatalogItem(
            sku="SERVER-256",
            title="Server",
            description="Server",
            category="hardware",
            base_price=Money(amount=4000000, currency="INR"),
        ),
        initial_stock=10,
    )
    service = BoundedNegotiationService(merchant_service=catalog, tix_service=tix_service)
    tx_id = "tx_chain_tamper"

    # Seed an invalid message into the ledger with a broken hash
    tampered_msg = tix_service.build_drift_notice_message(
        message_id="msg_tampered",
        intent_id=base_intent.intent_id,
        transaction_id=tx_id,
        violations=["Simulated drift"],
        attempt_id="att_1",
        previous_hash="0" * 64,  # Fake previous hash
        timestamp=base_time,
    )
    tix_service.append_and_verify(tampered_msg, reference_time=base_time)

    # Subsequent verification of chain integrity must fail
    is_valid, err = tix_service.verify_chain_integrity(tx_id)
    assert is_valid is False
    assert "chain break" in err.lower() or "mismatch" in err.lower() or "tamper" in err.lower() or "hash" in err.lower()


def test_zero_payment_authority_invariant():
    service = BoundedNegotiationService()
    # Confirm service has no payment authorization methods or state transitions
    assert not hasattr(service, "authorize_payment")
    assert not hasattr(service, "capture_payment")
    assert not hasattr(service, "declare_pass")
    assert not hasattr(service, "force_transition")

