"""Adversarial I5 Buyer Agent tests for authority and constraint preservation."""
from datetime import datetime, timedelta, timezone

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
