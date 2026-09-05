"""Focused I5 Buyer Agent tests.

These tests verify the bounded buyer-agent boundary without granting it
financial or integrity authority.
"""
from datetime import datetime, timedelta, timezone

import pytest

from backend.app.domain.buyer import BuyerAgentDecisionType, BuyerReplanRequest
from backend.app.domain.models import IntentContract, IntentItem, Money
from backend.app.domain.merchant import MerchantResponse
from backend.app.services.buyer import BuyerAgentService


@pytest.fixture
def reference_time():
    return datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def intent(reference_time):
    return IntentContract(
        intent_id="intent-buyer-1",
        issued_by="user-test",
        issued_at=reference_time,
        expires_at=reference_time + timedelta(hours=1),
        currency="INR",
        max_total=Money(amount=5000000, currency="INR"),
        items=[IntentItem(
            item_id="item-1",
            sku="SKU-PHONE-1",
            name="Reference Phone",
            quantity=1,
            unit_price=Money(amount=4000000, currency="INR"),
            total_price=Money(amount=4000000, currency="INR"),
        )],
        allowed_substitutions=[],
        allow_partial=False,
    )


def merchant_response(intent_id="intent-buyer-1", transaction_id="tx-1", total=4000000, success=True):
    return MerchantResponse(
        response_id="merchant-resp-1",
        merchant_id="merchant-reference-1",
        request_id="request-1",
        intent_id=intent_id,
        transaction_id=transaction_id,
        is_success=success,
        offer_id="offer-1" if success else None,
        total_amount=Money(amount=total, currency="INR") if success else None,
        offer_created_at=datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc),
        offer_expires_at=datetime(2026, 9, 5, 12, 15, tzinfo=timezone.utc),
        estimated_delivery_days=2,
        rejection_reason=None if success else "No compliant offer available",
    )


def test_proposal_is_strict_projection_of_intent(intent):
    service = BuyerAgentService()
    proposal = service.propose(intent, "buyer-agent-1", "tx-1")

    assert proposal.intent_id == intent.intent_id
    assert proposal.transaction_id == "tx-1"
    assert proposal.sku == intent.items[0].sku
    assert proposal.quantity == intent.items[0].quantity
    assert proposal.max_total == intent.max_total
    assert proposal.allowed_substitutions == intent.allowed_substitutions
    assert proposal.allow_partial is intent.allow_partial


def test_proposal_is_deterministic(intent):
    service = BuyerAgentService()
    first = service.propose(intent, "buyer-agent-1", "tx-1")
    second = service.propose(intent, "buyer-agent-1", "tx-1")
    assert first == second


def test_matching_merchant_offer_remains_advisory(intent):
    service = BuyerAgentService()
    decision = service.evaluate_merchant_response(intent, "buyer-agent-1", "tx-1", merchant_response())
    assert decision.decision == BuyerAgentDecisionType.PROPOSE
    assert decision.proposal is not None
    assert "authoritative" in decision.explanation.lower()


def test_wrong_intent_causes_abstention(intent):
    service = BuyerAgentService()
    decision = service.evaluate_merchant_response(
        intent, "buyer-agent-1", "tx-1", merchant_response(intent_id="different-intent")
    )
    assert decision.decision == BuyerAgentDecisionType.ABSTAIN
    assert "different intent" in decision.explanation


def test_wrong_transaction_causes_abstention(intent):
    service = BuyerAgentService()
    decision = service.evaluate_merchant_response(
        intent, "buyer-agent-1", "tx-1", merchant_response(transaction_id="different-tx")
    )
    assert decision.decision == BuyerAgentDecisionType.ABSTAIN
    assert "different transaction" in decision.explanation


def test_offer_over_budget_requests_replan_without_relaxing_limit(intent):
    service = BuyerAgentService()
    decision = service.evaluate_merchant_response(
        intent, "buyer-agent-1", "tx-1", merchant_response(total=5000100)
    )
    assert decision.decision == BuyerAgentDecisionType.REPLAN
    assert decision.proposal is not None
    assert decision.proposal.max_total == intent.max_total


def test_missing_merchant_total_abstains(intent):
    service = BuyerAgentService()
    response = merchant_response()
    response = response.model_copy(update={"total_amount": None})
    decision = service.evaluate_merchant_response(intent, "buyer-agent-1", "tx-1", response)
    assert decision.decision == BuyerAgentDecisionType.ABSTAIN


def test_replan_preserves_authorized_constraints(intent):
    service = BuyerAgentService()
    request = BuyerReplanRequest(
        request_id="replan-1",
        buyer_agent_id="buyer-agent-1",
        intent=intent,
        integrity_feedback="Price drift detected",
    )
    result = service.replan(request, transaction_id="tx-1")
    assert result.decision == BuyerAgentDecisionType.REPLAN
    assert result.proposal is not None
    assert result.proposal.max_total == intent.max_total
    assert result.proposal.sku == intent.items[0].sku


def test_clarification_does_not_guess_missing_constraint():
    clarification = BuyerAgentService.clarification(
        "intent-1", "What delivery deadline should I use?", "delivery_deadline"
    )
    assert clarification.intent_id == "intent-1"
    assert clarification.missing_constraint == "delivery_deadline"


def test_empty_clarification_is_rejected():
    with pytest.raises(ValueError):
        BuyerAgentService.clarification("intent-1", "", "budget")
