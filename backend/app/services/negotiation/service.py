"""Bounded Agentic Negotiation and Replanning Service for TarkaRaksha (I7).

Guarantees:
1. Negotiation May Change The Proposal. Negotiation Must Never Change The Authorization.
2. The immutable IntentContract remains the authoritative constraint boundary.
3. The negotiation loop is strictly bounded (max_rounds, max_replans).
4. All messages are cryptographically chained and recorded in TIX (I6).
5. Zero payment authorization authority resides in the negotiation engine.
6. Deterministic evaluation and revalidation via TarkaRaksha core engine.
"""
from datetime import datetime, timezone
import hashlib
from typing import Any, Dict, List, Optional, Tuple
import uuid

from backend.app.domain.buyer.contracts import (
    BuyerAgentDecisionType,
    BuyerReplanRequest,
    BuyerTransactionProposal,
)
from backend.app.domain.merchant.contracts import (
    BuyerCommerceRequest,
    BuyerItemRequest,
    MerchantResponse,
)
from backend.app.domain.models.enums import IntegrityStatus
from backend.app.domain.models.evidence import CanonicalEvent, Evidence, EvidenceBundle
from backend.app.domain.models.intent import IntentContract
from backend.app.domain.models.integrity import MRDP, IntegrityResult
from backend.app.domain.negotiation.contracts import (
    NegotiationPolicy,
    NegotiationRoundRecord,
    NegotiationSession,
    NegotiationState,
    NegotiationViolationCode,
)
from backend.app.domain.tix.contracts import (
    TIXMessage,
    TIXMessageType,
    TIXParticipantRole,
)
from backend.app.domain.operational_mode import OperationalMode
from backend.app.services.buyer.agent_service import BuyerAgentService
from backend.app.services.evaluation import evaluate_integrity
from backend.app.services.merchant.catalog_service import MerchantCatalogService
from backend.app.services.mrdp import build_mrdp
from backend.app.services.operational_mode import OperationalModeService
from backend.app.services.tix.exchange_service import TIXExchangeService


class BoundedNegotiationService:
    """Orchestrates deterministic bounded negotiation / replanning between Buyer and Merchant."""

    def __init__(
        self,
        buyer_service: Optional[BuyerAgentService] = None,
        merchant_service: Optional[MerchantCatalogService] = None,
        tix_service: Optional[TIXExchangeService] = None,
        operational_mode_service: Optional[OperationalModeService] = None,
    ):
        self.buyer_service = buyer_service or BuyerAgentService()
        self.merchant_service = merchant_service or MerchantCatalogService()
        self.tix_service = tix_service or TIXExchangeService()
        self.operational_mode_service = operational_mode_service

    def validate_proposal_against_intent(
        self,
        intent: IntentContract,
        proposal: BuyerTransactionProposal,
    ) -> Tuple[bool, Optional[NegotiationViolationCode], str]:
        """Deterministically validates that a candidate proposal does not breach authorized constraints."""
        # 1. Budget boundary
        if proposal.max_total.amount > intent.max_total.amount:
            return (
                False,
                NegotiationViolationCode.BUDGET_ESCALATION_ATTEMPT,
                f"Proposed budget {proposal.max_total.amount} exceeds authorized limit {intent.max_total.amount}",
            )

        # 2. Currency boundary
        if proposal.max_total.currency != intent.currency:
            return (
                False,
                NegotiationViolationCode.CURRENCY_MUTATION,
                f"Proposed currency '{proposal.max_total.currency}' does not match authorized '{intent.currency}'",
            )

        # 3. SKU / Substitution boundary
        authorized_skus = {it.sku for it in intent.items}
        allowed_subs = set(intent.allowed_substitutions)
        all_valid_skus = authorized_skus | allowed_subs

        if proposal.sku not in all_valid_skus:
            return (
                False,
                NegotiationViolationCode.UNAUTHORIZED_SUBSTITUTION,
                f"Proposed SKU '{proposal.sku}' is not in authorized SKUs {authorized_skus} or allowed substitutions {allowed_subs}",
            )

        # 4. Quantity boundary
        authorized_qty = sum(it.quantity for it in intent.items if it.sku == proposal.sku) or sum(
            it.quantity for it in intent.items
        )
        if proposal.quantity > authorized_qty:
            return (
                False,
                NegotiationViolationCode.QUANTITY_ESCALATION,
                f"Proposed quantity {proposal.quantity} exceeds authorized quantity {authorized_qty}",
            )

        return True, None, "Proposal strictly satisfies authorized constraints."

    def execute_bounded_remediation(
        self,
        intent: IntentContract,
        transaction_id: str,
        initial_merchant_response: MerchantResponse,
        initial_evidence: List[Evidence],
        events: Optional[List[CanonicalEvent]] = None,
        buyer_agent_id: str = "buyer_agent_1",
        merchant_id: Optional[str] = None,
        attempt_id: str = "att_1",
        policy: Optional[NegotiationPolicy] = None,
        reference_time: Optional[datetime] = None,
    ) -> NegotiationSession:
        """Executes the canonical bounded remediation loop following a commerce mismatch or drift."""
        pol = policy or NegotiationPolicy()
        ref_time = reference_time or intent.issued_at
        merch_id = merchant_id or initial_merchant_response.merchant_id
        session_id = f"neg_sess_{uuid.uuid4().hex[:12]}"

        # Invariant: SHADOW mode never executes automated remediation
        if self.operational_mode_service and self.operational_mode_service.get_mode() == OperationalMode.SHADOW:
            return NegotiationSession(
                session_id=session_id,
                transaction_id=transaction_id,
                intent_id=intent.intent_id,
                buyer_agent_id=buyer_agent_id,
                merchant_id=merch_id,
                state=NegotiationState.ABSTAINED,
                current_round=0,
                policy=pol,
                rounds=[],
                original_verdict=IntegrityStatus.DRIFT,
                original_violations=["SHADOW mode active: automated remediation is disabled."],
                final_verdict=IntegrityStatus.DRIFT,
                is_settled=True,
                termination_reason="Automated negotiation/remediation disabled in SHADOW mode (DETECTION=ACTIVE, ENFORCEMENT=DISABLED).",
                created_at=ref_time,
                updated_at=ref_time,
            )

        # 1. Initial Deterministic Evaluation
        initial_res = evaluate_integrity(
            contract=intent,
            evidence_list=initial_evidence,
            events=events,
            reference_time=ref_time,
        )

        if initial_res.status == IntegrityStatus.PASS:
            # Already compliant; no remediation needed
            return NegotiationSession(
                session_id=session_id,
                transaction_id=transaction_id,
                intent_id=intent.intent_id,
                buyer_agent_id=buyer_agent_id,
                merchant_id=merch_id,
                state=NegotiationState.COMPLETED,
                current_round=0,
                policy=pol,
                rounds=[],
                original_verdict=IntegrityStatus.PASS,
                original_violations=[],
                final_verdict=IntegrityStatus.PASS,
                is_settled=True,
                termination_reason="Initial proposal and evidence satisfied all integrity constraints.",
                created_at=ref_time,
                updated_at=ref_time,
            )

        # 2. Record initial drift state and initial MRDP
        orig_violations = [str(v) for v in initial_res.violations]
        initial_bundle = EvidenceBundle(
            bundle_id=f"bundle_init_{uuid.uuid4().hex[:8]}",
            intent_id=intent.intent_id,
            transaction_id=transaction_id,
            records=initial_evidence,
            created_at=ref_time,
        )
        initial_mrdp = build_mrdp(
            contract=intent,
            integrity_result=initial_res,
            evidence_bundle=initial_bundle,
            generated_at=ref_time,
        )

        # Log TIX drift notice
        drift_tix = self.tix_service.build_drift_notice_message(
            message_id=f"tix_drift_{uuid.uuid4().hex[:8]}",
            intent_id=intent.intent_id,
            transaction_id=transaction_id,
            violations=orig_violations,
            attempt_id=attempt_id,
            previous_hash=self.tix_service.get_chain_hash(transaction_id),
            timestamp=ref_time,
        )
        self.tix_service.append_and_verify(drift_tix, reference_time=ref_time)

        rounds_list: List[NegotiationRoundRecord] = []
        current_response = initial_merchant_response
        current_violations = orig_violations
        current_mrdp_id = initial_mrdp.mrdp_id
        session_state = NegotiationState.DRIFT_DETECTED
        termination_reason = None
        final_verdict: Optional[IntegrityStatus] = initial_res.status

        # 3. Bounded Negotiation Loop
        for round_idx in range(1, pol.max_rounds + 1):
            round_tix_ids: List[str] = []

            # A. Buyer Replanning
            replan_req = BuyerReplanRequest(
                request_id=f"replan_req_r{round_idx}_{uuid.uuid4().hex[:6]}",
                buyer_agent_id=buyer_agent_id,
                intent=intent,
                transaction_id=transaction_id,
                merchant_response=current_response,
                integrity_feedback="; ".join(current_violations),
                created_at=ref_time,
            )
            replan_res = self.buyer_service.replan(
                replan_req,
                transaction_id=transaction_id,
                reference_time=ref_time,
            )

            if replan_res.decision == BuyerAgentDecisionType.ABSTAIN:
                session_state = NegotiationState.ABSTAINED
                termination_reason = replan_res.reason
                rounds_list.append(
                    NegotiationRoundRecord(
                        round_number=round_idx,
                        transaction_id=transaction_id,
                        intent_id=intent.intent_id,
                        attempt_id=attempt_id,
                        state=NegotiationState.ABSTAINED,
                        drift_violations=current_violations,
                        mrdp_id=current_mrdp_id,
                        tix_message_ids=round_tix_ids,
                        timestamp=ref_time,
                        rationale=f"Buyer agent abstained: {replan_res.reason}",
                    )
                )
                break

            if replan_res.decision == BuyerAgentDecisionType.REQUEST_CLARIFICATION:
                session_state = NegotiationState.ESCALATED
                termination_reason = (
                    replan_res.clarification.question
                    if replan_res.clarification
                    else "Buyer agent requested clarification"
                )
                rounds_list.append(
                    NegotiationRoundRecord(
                        round_number=round_idx,
                        transaction_id=transaction_id,
                        intent_id=intent.intent_id,
                        attempt_id=attempt_id,
                        state=NegotiationState.ESCALATED,
                        drift_violations=current_violations,
                        mrdp_id=current_mrdp_id,
                        tix_message_ids=round_tix_ids,
                        timestamp=ref_time,
                        rationale=f"Buyer clarification required: {termination_reason}",
                    )
                )
                break

            candidate_proposal = replan_res.proposal
            if candidate_proposal is None:
                session_state = NegotiationState.FAILED
                termination_reason = "Buyer replan returned REPLAN decision but omitted proposal object."
                break

            # B. Deterministic Constraint Gate
            is_valid, viol_code, reason_msg = self.validate_proposal_against_intent(intent, candidate_proposal)
            if not is_valid:
                session_state = NegotiationState.FAILED
                termination_reason = f"Constraint breach ({viol_code.value if viol_code else 'UNKNOWN'}): {reason_msg}"
                rounds_list.append(
                    NegotiationRoundRecord(
                        round_number=round_idx,
                        transaction_id=transaction_id,
                        intent_id=intent.intent_id,
                        attempt_id=attempt_id,
                        state=NegotiationState.FAILED,
                        buyer_proposal_id=candidate_proposal.proposal_id,
                        drift_violations=[reason_msg],
                        mrdp_id=current_mrdp_id,
                        tix_message_ids=round_tix_ids,
                        timestamp=ref_time,
                        rationale=termination_reason,
                    )
                )
                break

            # C. TIX REMEDIATION_REQUEST
            tix_remed_req = self.tix_service.build_remediation_request_message(
                message_id=f"tix_rem_req_r{round_idx}_{uuid.uuid4().hex[:6]}",
                intent_id=intent.intent_id,
                transaction_id=transaction_id,
                requested_remediation=f"Proposing SKU {candidate_proposal.sku} x {candidate_proposal.quantity} within limit {intent.max_total.amount}",
                sender=buyer_agent_id,
                receiver=merch_id,
                attempt_id=attempt_id,
                previous_hash=self.tix_service.get_chain_hash(transaction_id),
                timestamp=ref_time,
            )
            self.tix_service.append_and_verify(tix_remed_req, reference_time=ref_time)
            round_tix_ids.append(tix_remed_req.message_id)

            # D. Formulate Merchant Request and Query Offer
            merchant_comm_req = BuyerCommerceRequest(
                request_id=f"comm_req_r{round_idx}_{uuid.uuid4().hex[:6]}",
                buyer_agent_id=buyer_agent_id,
                intent_id=intent.intent_id,
                transaction_id=transaction_id,
                items=[
                    BuyerItemRequest(
                        sku=candidate_proposal.sku,
                        quantity=candidate_proposal.quantity,
                        max_acceptable_unit_price=intent.max_total,
                    )
                ],
                max_budget=intent.max_total,
                request_timestamp=ref_time,
            )
            merchant_resp = self.merchant_service.process_buyer_request(merchant_comm_req, reference_time=ref_time)

            # E. TIX REMEDIATION_RESPONSE / OFFER
            tix_rem_resp = self.tix_service.build_offer_message(
                message_id=f"tix_rem_resp_r{round_idx}_{uuid.uuid4().hex[:6]}",
                intent_id=intent.intent_id,
                transaction_id=transaction_id,
                offer_payload={
                    "is_success": merchant_resp.is_success,
                    "rejection_reason": merchant_resp.rejection_reason,
                    "items": [
                        {"sku": it.sku, "quantity": it.quantity, "total_price_paise": it.total_price.amount}
                        for it in merchant_resp.items
                    ],
                },
                sender=merch_id,
                receiver=buyer_agent_id,
                attempt_id=attempt_id,
                capability_refs=getattr(merchant_resp, "capability_refs", []),
                policy_version=merchant_resp.policy_version,
                expires_at=merchant_resp.offer_expires_at,
                previous_hash=self.tix_service.get_chain_hash(transaction_id),
                timestamp=ref_time,
            )
            self.tix_service.append_and_verify(tix_rem_resp, reference_time=ref_time)
            round_tix_ids.append(tix_rem_resp.message_id)

            if not merchant_resp.is_success:
                current_response = merchant_resp
                current_violations = [merchant_resp.rejection_reason or "Merchant rejected proposed configuration."]
                rounds_list.append(
                    NegotiationRoundRecord(
                        round_number=round_idx,
                        transaction_id=transaction_id,
                        intent_id=intent.intent_id,
                        attempt_id=attempt_id,
                        state=NegotiationState.REPLAN_REQUESTED,
                        buyer_proposal_id=candidate_proposal.proposal_id,
                        merchant_response_id=merchant_resp.response_id,
                        proposed_sku=candidate_proposal.sku,
                        proposed_quantity=candidate_proposal.quantity,
                        drift_violations=current_violations,
                        mrdp_id=current_mrdp_id,
                        tix_message_ids=round_tix_ids,
                        timestamp=ref_time,
                        rationale=f"Merchant rejected offer: {merchant_resp.rejection_reason}",
                    )
                )
                if round_idx >= pol.max_rounds:
                    session_state = NegotiationState.ABSTAINED
                    termination_reason = "Maximum negotiation rounds reached without compliant merchant offer."
                continue

            # F. Fresh Evidence Generation
            offer = self.merchant_service.convert_response_to_merchant_offer(merchant_resp)
            if offer:
                fresh_evidence = [
                    ev.model_copy(update={"intent_id": intent.intent_id, "transaction_id": transaction_id})
                    for ev in offer.to_evidence()
                ]
            else:
                fresh_evidence = []

            # G. Deterministic Revalidation
            reval_events = events or [
                CanonicalEvent(
                    event_id=f"evt_reval_r{round_idx}",
                    transaction_id=transaction_id,
                    intent_id=intent.intent_id,
                    event_type="PAYMENT_CAPTURED",
                    timestamp=ref_time,
                    sequence_number=round_idx,
                )
            ]
            reval_res = evaluate_integrity(
                contract=intent,
                evidence_list=fresh_evidence,
                events=reval_events,
                reference_time=ref_time,
            )

            offered_total = None
            if merchant_resp.total_amount:
                offered_total = merchant_resp.total_amount

            # H. Evaluate Outcome
            if reval_res.status == IntegrityStatus.PASS:
                # Deterministic PASS achieved!
                session_state = NegotiationState.COMPLETED
                final_verdict = IntegrityStatus.PASS
                termination_reason = "Deterministic integrity revalidation succeeded."

                # Emit authoritative TIX OUTCOME
                tix_outcome = self.tix_service.build_outcome_message(
                    message_id=f"tix_out_r{round_idx}_{uuid.uuid4().hex[:6]}",
                    intent_id=intent.intent_id,
                    transaction_id=transaction_id,
                    status="PASS",
                    attempt_id=attempt_id,
                    previous_hash=self.tix_service.get_chain_hash(transaction_id),
                    timestamp=ref_time,
                )
                self.tix_service.append_and_verify(tix_outcome, reference_time=ref_time)
                round_tix_ids.append(tix_outcome.message_id)

                rounds_list.append(
                    NegotiationRoundRecord(
                        round_number=round_idx,
                        transaction_id=transaction_id,
                        intent_id=intent.intent_id,
                        attempt_id=attempt_id,
                        state=NegotiationState.COMPLETED,
                        buyer_proposal_id=candidate_proposal.proposal_id,
                        merchant_response_id=merchant_resp.response_id,
                        proposed_sku=candidate_proposal.sku,
                        proposed_quantity=candidate_proposal.quantity,
                        offered_total=offered_total,
                        drift_violations=[],
                        mrdp_id=None,
                        tix_message_ids=round_tix_ids,
                        timestamp=ref_time,
                        rationale="Revalidation PASS achieved.",
                    )
                )
                break

            elif reval_res.status == IntegrityStatus.DRIFT:
                # Still drifting
                current_violations = [str(v) for v in reval_res.violations]
                reval_bundle = EvidenceBundle(
                    bundle_id=f"bundle_r{round_idx}_{uuid.uuid4().hex[:8]}",
                    intent_id=intent.intent_id,
                    transaction_id=transaction_id,
                    records=fresh_evidence,
                    created_at=ref_time,
                )
                reval_mrdp = build_mrdp(
                    contract=intent,
                    integrity_result=reval_res,
                    evidence_bundle=reval_bundle,
                    generated_at=ref_time,
                )
                current_mrdp_id = reval_mrdp.mrdp_id
                current_response = merchant_resp

                # Emit TIX DRIFT_NOTICE
                tix_drift_r = self.tix_service.build_drift_notice_message(
                    message_id=f"tix_drift_r{round_idx}_{uuid.uuid4().hex[:6]}",
                    intent_id=intent.intent_id,
                    transaction_id=transaction_id,
                    violations=current_violations,
                    attempt_id=attempt_id,
                    previous_hash=self.tix_service.get_chain_hash(transaction_id),
                    timestamp=ref_time,
                )
                self.tix_service.append_and_verify(tix_drift_r, reference_time=ref_time)
                round_tix_ids.append(tix_drift_r.message_id)

                rounds_list.append(
                    NegotiationRoundRecord(
                        round_number=round_idx,
                        transaction_id=transaction_id,
                        intent_id=intent.intent_id,
                        attempt_id=attempt_id,
                        state=NegotiationState.DRIFT_DETECTED,
                        buyer_proposal_id=candidate_proposal.proposal_id,
                        merchant_response_id=merchant_resp.response_id,
                        proposed_sku=candidate_proposal.sku,
                        proposed_quantity=candidate_proposal.quantity,
                        offered_total=offered_total,
                        drift_violations=current_violations,
                        mrdp_id=current_mrdp_id,
                        tix_message_ids=round_tix_ids,
                        timestamp=ref_time,
                        rationale="Revalidation detected continuing drift.",
                    )
                )
                if round_idx >= pol.max_rounds:
                    session_state = NegotiationState.ABSTAINED
                    termination_reason = "Maximum negotiation rounds reached without resolving drift."
                    break

            else:  # UNKNOWN
                session_state = NegotiationState.ESCALATED
                final_verdict = IntegrityStatus.UNKNOWN
                termination_reason = "Revalidation yielded UNKNOWN; cannot guess PASS."
                tix_unknown = self.tix_service.build_outcome_message(
                    message_id=f"tix_unk_r{round_idx}_{uuid.uuid4().hex[:6]}",
                    intent_id=intent.intent_id,
                    transaction_id=transaction_id,
                    status="UNKNOWN",
                    attempt_id=attempt_id,
                    previous_hash=self.tix_service.get_chain_hash(transaction_id),
                    timestamp=ref_time,
                )
                self.tix_service.append_and_verify(tix_unknown, reference_time=ref_time)
                round_tix_ids.append(tix_unknown.message_id)

                rounds_list.append(
                    NegotiationRoundRecord(
                        round_number=round_idx,
                        transaction_id=transaction_id,
                        intent_id=intent.intent_id,
                        attempt_id=attempt_id,
                        state=NegotiationState.ESCALATED,
                        buyer_proposal_id=candidate_proposal.proposal_id,
                        merchant_response_id=merchant_resp.response_id,
                        proposed_sku=candidate_proposal.sku,
                        proposed_quantity=candidate_proposal.quantity,
                        offered_total=offered_total,
                        drift_violations=[],
                        mrdp_id=None,
                        tix_message_ids=round_tix_ids,
                        timestamp=ref_time,
                        rationale="Revalidation yielded UNKNOWN evidence state.",
                    )
                )
                break

        is_settled = session_state in {NegotiationState.COMPLETED, NegotiationState.ABSTAINED, NegotiationState.ESCALATED, NegotiationState.FAILED}

        return NegotiationSession(
            session_id=session_id,
            transaction_id=transaction_id,
            intent_id=intent.intent_id,
            buyer_agent_id=buyer_agent_id,
            merchant_id=merch_id,
            state=session_state,
            current_round=len(rounds_list),
            policy=pol,
            rounds=rounds_list,
            original_verdict=initial_res.status,
            original_violations=orig_violations,
            final_verdict=final_verdict,
            final_mrdp_id=current_mrdp_id,
            is_settled=is_settled,
            termination_reason=termination_reason,
            created_at=ref_time,
            updated_at=ref_time,
        )
