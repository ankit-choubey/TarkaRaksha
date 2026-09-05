"""Unified Gate Composition Service for TarkaRaksha E2.

Composes ConsumerGate and MerchantGate into a single cohesive validation surface
that feeds structured facts into the TarkaRaksha integration boundary.

Governing Invariant:
AI proposes. Evidence proves. Deterministic logic decides.
Gates validate context and produce facts.
They NEVER declare an authoritative financial PASS.
"""
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from backend.app.domain.buyer.contracts import BuyerTransactionProposal
from backend.app.domain.gates.contracts import (
    ConsumerGateResult,
    GateCompositionOutcome,
    GateStatus,
    MerchantGateResult,
)
from backend.app.domain.integration.contracts import IntegrationTransactionContext
from backend.app.domain.merchant.contracts import MerchantResponse
from backend.app.domain.models.evidence import Evidence
from backend.app.domain.models.intent import IntentContract
from backend.app.services.gates.consumer_gate import ConsumerGate
from backend.app.services.gates.merchant_gate import MerchantGate
from backend.app.services.merchant.catalog_service import MerchantCatalogService


class GateCompositionService:
    """Service boundary orchestrating consumer and merchant validation gates."""

    def __init__(
        self,
        catalog_service: Optional[MerchantCatalogService] = None,
    ) -> None:
        self.catalog_service = catalog_service or MerchantCatalogService()

    def validate_consumer(
        self,
        context: IntegrationTransactionContext,
        proposal: BuyerTransactionProposal,
        intent: IntentContract,
        reference_time: Optional[datetime] = None,
    ) -> ConsumerGateResult:
        """Runs the Consumer Gate validation suite."""
        return ConsumerGate.validate(
            context=context,
            proposal=proposal,
            intent=intent,
            reference_time=reference_time,
        )

    def validate_merchant(
        self,
        context: IntegrationTransactionContext,
        merchant_response: MerchantResponse,
        catalog_service: Optional[MerchantCatalogService] = None,
        intent: Optional[IntentContract] = None,
        requested_sku: Optional[str] = None,
        requested_quantity: int = 1,
        reference_time: Optional[datetime] = None,
    ) -> MerchantGateResult:
        """Runs the Merchant Gate validation suite."""
        cat_svc = catalog_service or self.catalog_service
        return MerchantGate.validate(
            context=context,
            merchant_response=merchant_response,
            catalog_service=cat_svc,
            intent=intent,
            requested_sku=requested_sku,
            requested_quantity=requested_quantity,
            reference_time=reference_time,
        )

    def compose(
        self,
        context: IntegrationTransactionContext,
        proposal: BuyerTransactionProposal,
        intent: IntentContract,
        merchant_response: Optional[MerchantResponse] = None,
        catalog_service: Optional[MerchantCatalogService] = None,
        reference_time: Optional[datetime] = None,
    ) -> GateCompositionOutcome:
        """Composes both gates and determines whether the transaction is admissible for execution.
        
        Admissibility indicates that all boundary constraints (identity, authorization, catalog,
        inventory, pricing, policy) are satisfied so far.
        It is NOT a financial PASS. Financial integrity is decided only by T04 evaluate_integrity.
        """
        ref_time = reference_time or datetime.now(timezone.utc)
        consumer_res = self.validate_consumer(
            context=context,
            proposal=proposal,
            intent=intent,
            reference_time=ref_time,
        )

        merchant_res: Optional[MerchantGateResult] = None
        if merchant_response is not None:
            merchant_res = self.validate_merchant(
                context=context,
                merchant_response=merchant_response,
                catalog_service=catalog_service,
                intent=intent,
                requested_sku=proposal.sku,
                requested_quantity=proposal.quantity,
                reference_time=ref_time,
            )

        if merchant_res is not None:
            if consumer_res.status == GateStatus.INVALID or merchant_res.status == GateStatus.INVALID:
                overall_status = GateStatus.INVALID
                is_all_valid = False
                invalid_gates = []
                if consumer_res.status == GateStatus.INVALID:
                    invalid_gates.append("ConsumerGate")
                if merchant_res.status == GateStatus.INVALID:
                    invalid_gates.append("MerchantGate")
                summary = f"Validation failure in: {', '.join(invalid_gates)}"
            elif consumer_res.status == GateStatus.UNKNOWN or merchant_res.status == GateStatus.UNKNOWN:
                overall_status = GateStatus.UNKNOWN
                is_all_valid = False
                unknown_gates = []
                if consumer_res.status == GateStatus.UNKNOWN:
                    unknown_gates.append("ConsumerGate")
                if merchant_res.status == GateStatus.UNKNOWN:
                    unknown_gates.append("MerchantGate")
                summary = f"Validation indeterminate / unknown in: {', '.join(unknown_gates)}"
            else:
                overall_status = GateStatus.VALID
                is_all_valid = True
                summary = "Both Consumer and Merchant gates passed deterministic validation"
        else:
            is_all_valid = consumer_res.is_valid
            overall_status = consumer_res.status
            summary = f"Consumer gate validated ({consumer_res.status.value}) (merchant response pending)"

        return GateCompositionOutcome(
            transaction_id=context.transaction_id,
            consumer_gate=consumer_res,
            merchant_gate=merchant_res,
            overall_status=overall_status,
            is_admissible=is_all_valid,
            summary=summary,
            evaluated_at=ref_time,
        )

    def to_evidence_records(
        self,
        outcome: GateCompositionOutcome,
        intent_id: str,
    ) -> List[Evidence]:
        """Converts gate validation outcomes into structured evidence records.
        
        Feeds factual observations into T04 deterministic evaluation without
        granting the gates any authority to declare a financial PASS.
        """
        ev_list: List[Evidence] = [outcome.consumer_gate.to_evidence()]
        if outcome.merchant_gate:
            ev_list.append(outcome.merchant_gate.to_evidence(intent_id=intent_id))
        return ev_list
