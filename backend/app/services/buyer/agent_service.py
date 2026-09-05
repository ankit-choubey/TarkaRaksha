"""Bounded Buyer Agent service for TarkaRaksha I5.

Natural-language interpretation is delegated to the existing T08 intent parser.
This service adds the buyer-agent boundary around that validated contract and
supports deterministic proposal creation and constrained replanning.
"""
from datetime import datetime, timezone
import hashlib

from backend.app.domain.buyer.contracts import (
    BuyerAgentDecision,
    BuyerAgentDecisionType,
    BuyerClarification,
    BuyerReplanRequest,
    BuyerReplanResult,
    BuyerTransactionProposal,
)
from backend.app.domain.models import IntentContract
from backend.app.domain.merchant.contracts import MerchantResponse
from backend.app.services.ai.intent_parser import parse_intent


class BuyerAgentService:
    """Reference buyer-agent boundary with explicit authorization preservation."""

    def parse_user_goal(self, user_prompt: str, **parser_kwargs) -> IntentContract:
        """Convert natural language into the existing authoritative IntentContract."""
        return parse_intent(user_prompt=user_prompt, **parser_kwargs)

    def propose(self, intent: IntentContract, buyer_agent_id: str, transaction_id: str) -> BuyerTransactionProposal:
        """Create a proposal that is a strict projection of the authorized intent."""
        if not buyer_agent_id.strip() or not transaction_id.strip():
            raise ValueError("buyer_agent_id and transaction_id are required")
        item = intent.items[0]
        digest = hashlib.sha256(
            f"{buyer_agent_id}:{intent.intent_id}:{transaction_id}:{item.sku}:{item.quantity}:{intent.max_total.amount}".encode()
        ).hexdigest()[:16]
        return BuyerTransactionProposal(
            proposal_id=f"buyer_proposal_{digest}",
            buyer_agent_id=buyer_agent_id,
            intent_id=intent.intent_id,
            transaction_id=transaction_id,
            sku=item.sku,
            quantity=item.quantity,
            max_total=intent.max_total,
            allowed_substitutions=list(intent.allowed_substitutions),
            allow_partial=intent.allow_partial,
            rationale="Projection of the immutable authorized IntentContract",
        )

    def evaluate_merchant_response(
        self,
        intent: IntentContract,
        buyer_agent_id: str,
        transaction_id: str,
        merchant_response: MerchantResponse,
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
        if not merchant_response.is_success:
            return BuyerAgentDecision(
                decision=BuyerAgentDecisionType.REPLAN,
                proposal=self.propose(intent, buyer_agent_id, transaction_id),
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
                proposal=self.propose(intent, buyer_agent_id, transaction_id),
                explanation="Offer exceeds the authorized buyer spending ceiling; constraints remain unchanged.",
            )
        if merchant_response.estimated_delivery_days > self._delivery_limit(intent):
            return BuyerAgentDecision(
                decision=BuyerAgentDecisionType.REPLAN,
                proposal=self.propose(intent, buyer_agent_id, transaction_id),
                explanation="Offer exceeds the buyer's authorized delivery constraint; constraints remain unchanged.",
            )
        return BuyerAgentDecision(
            decision=BuyerAgentDecisionType.PROPOSE,
            proposal=self.propose(intent, buyer_agent_id, transaction_id),
            explanation="Offer satisfies the buyer constraints represented in the intent; TarkaRaksha remains authoritative for integrity and payment.",
        )

    def replan(self, request: BuyerReplanRequest) -> BuyerReplanResult:
        """Produce a bounded replan from feedback without relaxing authorization."""
        proposal = self.propose(request.intent, request.buyer_agent_id, request.intent.intent_id)
        reason = request.integrity_feedback or "Replan requested by the transaction control flow."
        if request.merchant_response is not None:
            decision = self.evaluate_merchant_response(
                request.intent,
                request.buyer_agent_id,
                request.intent.intent_id,
                request.merchant_response,
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
    def clarification(intent_id: str | None, question: str, missing_constraint: str) -> BuyerClarification:
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
        """Use the intent's delivery constraint only when represented in the contract.

        The current T03/T08 IntentContract does not contain a delivery field, so
        the safe fallback is unbounded rather than inventing a buyer constraint.
        """
        return 2**31 - 1

    @staticmethod
    def _result_id(request_id: str, decision: str) -> str:
        return "replan_" + hashlib.sha256(f"{request_id}:{decision}".encode()).hexdigest()[:16]
