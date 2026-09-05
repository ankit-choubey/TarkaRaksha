"""Bounded Buyer Agent service for TarkaRaksha I5.

Natural-language interpretation is delegated to the existing T08 intent parser.
This service adds the buyer-agent boundary around that validated contract and
supports deterministic proposal creation, merchant request formulation,
and constrained replanning.
"""
from datetime import datetime, timezone
import hashlib
from typing import Any, Optional

from backend.app.domain.buyer.contracts import (
    BuyerAgentDecision,
    BuyerAgentDecisionType,
    BuyerClarification,
    BuyerReplanRequest,
    BuyerReplanResult,
    BuyerTransactionProposal,
)
from backend.app.domain.models import IntentContract
from backend.app.domain.merchant.contracts import BuyerCommerceRequest, BuyerItemRequest, MerchantResponse
from backend.app.services.ai.intent_parser import parse_intent


class BuyerAgentService:
    """Reference buyer-agent boundary with explicit authorization preservation."""

    def parse_user_goal(self, user_prompt: str, **parser_kwargs) -> IntentContract:
        """Convert natural language into the existing authoritative IntentContract."""
        return parse_intent(user_prompt=user_prompt, **parser_kwargs)

    def propose(
        self,
        intent: IntentContract,
        buyer_agent_id: str,
        transaction_id: str,
        reference_time: Optional[datetime] = None,
    ) -> BuyerTransactionProposal:
        """Create a proposal that is a strict projection of the authorized intent."""
        if not buyer_agent_id.strip() or not transaction_id.strip():
            raise ValueError("buyer_agent_id and transaction_id are required")
        if not intent.items:
            raise ValueError("IntentContract must contain at least one item")

        items = list(intent.items)
        primary_item = items[0]

        items_digest_str = ";".join(f"{it.sku}:{it.quantity}:{it.total_price.amount}" for it in items)
        digest = hashlib.sha256(
            f"{buyer_agent_id}:{intent.intent_id}:{transaction_id}:{items_digest_str}:{intent.max_total.amount}".encode()
        ).hexdigest()[:16]

        created_at = reference_time or intent.issued_at
        total_quantity = sum(it.quantity for it in items)

        return BuyerTransactionProposal(
            proposal_id=f"buyer_proposal_{digest}",
            buyer_agent_id=buyer_agent_id,
            intent_id=intent.intent_id,
            transaction_id=transaction_id,
            items=items,
            sku=primary_item.sku,
            quantity=primary_item.quantity if len(items) == 1 else total_quantity,
            max_total=intent.max_total,
            allowed_substitutions=list(intent.allowed_substitutions),
            allow_partial=intent.allow_partial,
            rationale="Projection of the immutable authorized IntentContract",
            created_at=created_at,
        )

    def formulate_merchant_request(
        self,
        intent: IntentContract,
        buyer_agent_id: str,
        transaction_id: str,
        delivery_deadline_days: Optional[int] = None,
        preferred_shipping_id: Optional[str] = None,
    ) -> BuyerCommerceRequest:
        """
        Formulates a structured BuyerCommerceRequest for the Merchant Agent (I4),
        strictly bounded by the authorized IntentContract constraints.
        """
        if not buyer_agent_id.strip() or not transaction_id.strip():
            raise ValueError("buyer_agent_id and transaction_id are required")

        request_items = [
            BuyerItemRequest(
                sku=it.sku,
                quantity=it.quantity,
                max_acceptable_unit_price=it.unit_price,
            )
            for it in intent.items
        ]

        digest = hashlib.sha256(
            f"{buyer_agent_id}:{intent.intent_id}:{transaction_id}:{intent.max_total.amount}".encode()
        ).hexdigest()[:12]

        return BuyerCommerceRequest(
            request_id=f"req_{digest}",
            buyer_agent_id=buyer_agent_id,
            intent_id=intent.intent_id,
            transaction_id=transaction_id,
            items=request_items,
            max_budget=intent.max_total,
            preferred_shipping_id=preferred_shipping_id,
            delivery_deadline_days=delivery_deadline_days,
        )

    def evaluate_merchant_response(
        self,
        intent: IntentContract,
        buyer_agent_id: str,
        transaction_id: str,
        merchant_response: MerchantResponse,
        max_delivery_days: Optional[int] = None,
        reference_time: Optional[datetime] = None,
    ) -> BuyerAgentDecision:
        """Evaluate an offer without changing the authorized buyer constraints."""
        if merchant_response.intent_id != intent.intent_id:
            return BuyerAgentDecision(
                decision=BuyerAgentDecisionType.ABSTAIN,
                explanation="Merchant response is bound to a different intent.",
            )
        if merchant_response.transaction_id != transaction_id:
            return BuyerAgentDecision(
                decision=BuyerAgentDecisionType.ABSTAIN,
                explanation="Merchant response is bound to a different transaction.",
            )

        # Dynamic offer expiry check (I4/I5)
        eval_time = reference_time or intent.issued_at
        if merchant_response.is_expired(as_of=eval_time):
            return BuyerAgentDecision(
                decision=BuyerAgentDecisionType.REPLAN,
                proposal=self.propose(intent, buyer_agent_id, transaction_id, reference_time=eval_time),
                explanation="Merchant offer has expired; request fresh offer without changing authorized constraints.",
            )

        if not merchant_response.is_success:
            return BuyerAgentDecision(
                decision=BuyerAgentDecisionType.REPLAN,
                proposal=self.propose(intent, buyer_agent_id, transaction_id, reference_time=eval_time),
                explanation=merchant_response.rejection_reason or "Merchant rejected the request; retain authorized constraints and replan.",
            )
        if merchant_response.total_amount is None:
            return BuyerAgentDecision(
                decision=BuyerAgentDecisionType.ABSTAIN,
                explanation="Merchant response lacks a total amount; insufficient evidence for a buyer decision.",
            )
        if merchant_response.total_amount.currency != intent.currency:
            return BuyerAgentDecision(
                decision=BuyerAgentDecisionType.ABSTAIN,
                explanation="Merchant offer currency conflicts with the authorized intent.",
            )
        if merchant_response.total_amount.amount > intent.max_total.amount:
            return BuyerAgentDecision(
                decision=BuyerAgentDecisionType.REPLAN,
                proposal=self.propose(intent, buyer_agent_id, transaction_id, reference_time=eval_time),
                explanation="Offer exceeds the authorized buyer spending ceiling; constraints remain unchanged.",
            )

        # Authorized item / substitution check
        authorized_skus = {it.sku for it in intent.items} | set(intent.allowed_substitutions)
        if merchant_response.items:
            offered_skus = {item.sku for item in merchant_response.items}
            if not offered_skus.issubset(authorized_skus):
                return BuyerAgentDecision(
                    decision=BuyerAgentDecisionType.REPLAN,
                    proposal=self.propose(intent, buyer_agent_id, transaction_id, reference_time=eval_time),
                    explanation="Merchant offer contains unauthorized item SKU not permitted by buyer intent.",
                )

        delivery_limit = max_delivery_days or self._delivery_limit(intent)
        if merchant_response.estimated_delivery_days > delivery_limit:
            return BuyerAgentDecision(
                decision=BuyerAgentDecisionType.REPLAN,
                proposal=self.propose(intent, buyer_agent_id, transaction_id, reference_time=eval_time),
                explanation="Offer exceeds the buyer's authorized delivery constraint; constraints remain unchanged.",
            )

        merchant_req = self.formulate_merchant_request(
            intent=intent,
            buyer_agent_id=buyer_agent_id,
            transaction_id=transaction_id,
            delivery_deadline_days=max_delivery_days,
        )

        return BuyerAgentDecision(
            decision=BuyerAgentDecisionType.PROPOSE,
            proposal=self.propose(intent, buyer_agent_id, transaction_id, reference_time=eval_time),
            merchant_request=merchant_req.model_dump(mode="json"),
            explanation="Offer satisfies the buyer constraints represented in the intent; TarkaRaksha remains authoritative for integrity and payment.",
        )

    def replan(
        self,
        request: BuyerReplanRequest,
        transaction_id: Optional[str] = None,
        reference_time: Optional[datetime] = None,
    ) -> BuyerReplanResult:
        """Produce a bounded replan from feedback without relaxing authorization."""
        if transaction_id and transaction_id != request.transaction_id:
            return BuyerReplanResult(
                result_id=self._result_id(request.request_id, "ABSTAIN"),
                decision=BuyerAgentDecisionType.ABSTAIN,
                reason="Mismatched transaction_id passed to replan; cannot substitute transaction identity.",
            )

        effective_transaction_id = request.transaction_id
        eval_time = reference_time or request.created_at
        proposal = self.propose(
            request.intent,
            request.buyer_agent_id,
            effective_transaction_id,
            reference_time=eval_time,
        )
        reason = request.integrity_feedback or "Replan requested by the transaction control flow."

        if request.merchant_response is not None:
            decision = self.evaluate_merchant_response(
                request.intent,
                request.buyer_agent_id,
                effective_transaction_id,
                request.merchant_response,
                reference_time=eval_time,
            )
            if decision.decision == BuyerAgentDecisionType.ABSTAIN:
                return BuyerReplanResult(
                    result_id=self._result_id(request.request_id, "ABSTAIN"),
                    decision=BuyerAgentDecisionType.ABSTAIN,
                    reason=decision.explanation,
                )
        return BuyerReplanResult(
            result_id=self._result_id(request.request_id, "REPLAN"),
            decision=BuyerAgentDecisionType.REPLAN,
            proposal=proposal,
            reason=reason,
        )

    @staticmethod
    def clarification(intent_id: Optional[str], question: str, missing_constraint: str) -> BuyerClarification:
        """Create an explicit clarification request instead of guessing missing constraints."""
        if not question.strip() or not missing_constraint.strip():
            raise ValueError("question and missing_constraint are required")
        digest = hashlib.sha256(f"{intent_id}:{question}:{missing_constraint}".encode()).hexdigest()[:12]
        return BuyerClarification(
            clarification_id=f"clarify_{digest}",
            intent_id=intent_id,
            question=question,
            missing_constraint=missing_constraint,
        )

    @staticmethod
    def _delivery_limit(intent: IntentContract) -> int:
        """Do not invent a delivery constraint absent from the authoritative contract."""
        return 2**31 - 1

    @staticmethod
    def _result_id(request_id: str, decision: str) -> str:
        return "replan_" + hashlib.sha256(f"{request_id}:{decision}".encode()).hexdigest()[:16]

