"""Adversarial I5 Buyer Agent tests for authority and constraint preservation."""
from datetime import datetime, timedelta, timezone
import pytest

from backend.app.domain.buyer import BuyerAgentDecisionType
from backend.app.domain.models import IntentContract, IntentItem, Money
from backend.app.domain.merchant import MerchantResponse
from backend.app.services.buyer import BuyerAgentService


def make_intent():
    t0 = datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc)
    return IntentContract(
        intent_id="intent-secure-1",
        issued_by="user-test",
        issued_at=t0,
        expires_at=t0 + timedelta(hours=1),
        currency="INR",
        max_total=Money(amount=5000000, currency="INR"),
        items=[IntentItem(
            item_id="item-1", sku="SKU-SERVER", name="Server", quantity=1,
            unit_price=Money(amount=4500000, currency="INR"),
            total_price=Money(amount=4500000, currency="INR"),
        )],
    )


def make_response(**overrides):
    values = dict(
        response_id="resp-1", merchant_id="merchant-1", request_id="req-1",
        intent_id="intent-secure-1", transaction_id="tx-1", is_success=True,
        offer_id="offer-1", total_amount=Money(amount=4500000, currency="INR"),
        offer_created_at=datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc),
        offer_expires_at=datetime(2026, 9, 5, 12, 15, tzinfo=timezone.utc),
        estimated_delivery_days=2,
    )
    values.update(overrides)
    return MerchantResponse(**values)


def test_malformed_or_missing_payment_state_cannot_become_pass():
    service = BuyerAgentService()
    intent = make_intent()
    response = make_response(total_amount=None)
    decision = service.evaluate_merchant_response(intent, "buyer-agent-1", "tx-1", response)
    assert decision.decision == BuyerAgentDecisionType.ABSTAIN


def test_buyer_agent_cannot_accept_higher_budget_from_merchant():
    service = BuyerAgentService()
    intent = make_intent()
    response = make_response(total_amount=Money(amount=6000000, currency="INR"))
    decision = service.evaluate_merchant_response(intent, "buyer-agent-1", "tx-1", response)
    assert decision.decision == BuyerAgentDecisionType.REPLAN
    assert decision.proposal.max_total.amount == 5000000


def test_buyer_agent_cannot_change_authorized_sku():
    service = BuyerAgentService()
    intent = make_intent()
    proposal = service.propose(intent, "buyer-agent-1", "tx-1")
    assert proposal.sku == "SKU-SERVER"
    assert proposal.sku != "SKU-ATTACKER"


def test_buyer_agent_cannot_treat_wrong_currency_as_valid():
    service = BuyerAgentService()
    intent = make_intent()
    response = make_response(total_amount=Money(amount=45000, currency="USD"))
    decision = service.evaluate_merchant_response(intent, "buyer-agent-1", "tx-1", response)
    assert decision.decision == BuyerAgentDecisionType.ABSTAIN


def test_buyer_agent_does_not_authorize_payment():
    service = BuyerAgentService()
    proposal = service.propose(make_intent(), "buyer-agent-1", "tx-1")
    assert not hasattr(proposal, "payment_authorized")
    assert not hasattr(proposal, "payment_status")


def test_unauthorized_sku_substitution_by_merchant_causes_replan():
    service = BuyerAgentService()
    intent = make_intent()
    from backend.app.domain.merchant.contracts import MerchantOfferItem
    # Merchant offers a rogue SKU not in authorized intent or substitutions
    rogue_response = make_response(
        items=[
            MerchantOfferItem(
                sku="SKU-ROGUE-UNAUTHORIZED",
                title="Unauthorized Hardware",
                quantity=1,
                unit_price=Money(amount=4500000, currency="INR"),
                total_price=Money(amount=4500000, currency="INR"),
            )
        ]
    )
    decision = service.evaluate_merchant_response(intent, "buyer-agent-1", "tx-1", rogue_response)
    assert decision.decision == BuyerAgentDecisionType.REPLAN
    assert "unauthorized item sku" in decision.explanation.lower()


def test_merchant_delivery_deadline_breach_causes_replan():
    service = BuyerAgentService()
    intent = make_intent()
    # Merchant offers 5 days delivery when buyer allows max 2 days
    slow_response = make_response(estimated_delivery_days=5)
    decision = service.evaluate_merchant_response(
        intent, "buyer-agent-1", "tx-1", slow_response, max_delivery_days=2
    )
    assert decision.decision == BuyerAgentDecisionType.REPLAN
    assert "delivery constraint" in decision.explanation.lower()


def test_buyer_replan_strictly_rejects_transaction_identity_substitution():
    service = BuyerAgentService()
    intent = make_intent()
    from backend.app.domain.buyer import BuyerReplanRequest
    
    # BuyerReplanRequest requires explicit transaction_id; cannot be empty
    with pytest.raises(Exception):
        BuyerReplanRequest(
            request_id="replan-bad",
            buyer_agent_id="buyer-agent-1",
            intent=intent,
            transaction_id="",  # Empty transaction_id
        )

    # Calling replan with mismatched transaction_id abstains
    valid_request = BuyerReplanRequest(
        request_id="replan-good",
        buyer_agent_id="buyer-agent-1",
        intent=intent,
        transaction_id="tx-bound-1",
    )
    result = service.replan(valid_request, transaction_id="tx-attacker-tampered")
    assert result.decision == BuyerAgentDecisionType.ABSTAIN
    assert "Mismatched transaction_id" in result.reason


def test_multi_item_intent_preserves_all_items_against_truncation():
    t0 = datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc)
    multi_intent = IntentContract(
        intent_id="intent-triple-1",
        issued_by="user-test",
        issued_at=t0,
        expires_at=t0 + timedelta(hours=1),
        currency="INR",
        max_total=Money(amount=10000000, currency="INR"),
        items=[
            IntentItem(
                item_id="it-1", sku="SKU-SERVER", name="Server", quantity=1,
                unit_price=Money(amount=5000000, currency="INR"), total_price=Money(amount=5000000, currency="INR"),
            ),
            IntentItem(
                item_id="it-2", sku="SKU-RAM", name="RAM", quantity=4,
                unit_price=Money(amount=1000000, currency="INR"), total_price=Money(amount=4000000, currency="INR"),
            ),
            IntentItem(
                item_id="it-3", sku="SKU-CABLE", name="Cable", quantity=1,
                unit_price=Money(amount=1000000, currency="INR"), total_price=Money(amount=1000000, currency="INR"),
            ),
        ],
    )
    service = BuyerAgentService()
    proposal = service.propose(multi_intent, "buyer-agent-1", "tx-triple-1")

    # All 3 items preserved
    assert len(proposal.items) == 3
    assert [it.sku for it in proposal.items] == ["SKU-SERVER", "SKU-RAM", "SKU-CABLE"]
    assert proposal.quantity == 6  # 1 + 4 + 1
    assert proposal.max_total == multi_intent.max_total


def test_buyer_agent_decision_types_remain_strictly_advisory():
    # Verify BuyerAgentDecisionType has zero authority to declare PASS or COMPLETED
    permitted_decisions = {d.value for d in BuyerAgentDecisionType}
    assert "PASS" not in permitted_decisions
    assert "COMPLETED" not in permitted_decisions
    assert "AUTHORIZED" not in permitted_decisions
    assert permitted_decisions == {"PROPOSE", "REQUEST_CLARIFICATION", "REQUEST_MERCHANT_INFO", "REPLAN", "ABSTAIN"}

