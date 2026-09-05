"""
Deterministic Revalidation Service for TarkaRaksha (T11).
Executes the final, mandatory recovery step:
Recovery Action -> Observe -> Normalize -> Deterministic Integrity Engine -> New IntegrityResult.

Authority & Invariants:
- Recovery action execution alone NEVER declares PASS.
- Only the deterministic engine (T04) can declare whether transaction integrity is restored.
- Financial arithmetic strictly uses integer minor units (paise/cents).
"""
from datetime import datetime, timezone
import logging
from typing import List, Optional

from backend.app.domain.models import (
    CanonicalEvent,
    Evidence,
    EvidenceAuthority,
    EvidenceSource,
    IntegrityResult,
    IntentContract,
    Money,
)
from backend.app.services.evaluation import evaluate_integrity

logger = logging.getLogger(__name__)


def revalidate_recovery(
    contract: IntentContract,
    prior_evidence: List[Evidence],
    recovery_evidence: List[Evidence],
    prior_events: List[CanonicalEvent],
    recovery_events: List[CanonicalEvent],
    reference_time: Optional[datetime] = None,
) -> IntegrityResult:
    """
    Deterministically re-evaluates transaction integrity following recovery execution.
    Consolidates compensatory evidence (e.g. refunds netting out overcharges)
    and passes the resulting canonical evidence to the pure deterministic engine.
    """
    eval_ts = reference_time or datetime.now(timezone.utc)
    if eval_ts.tzinfo is None:
        eval_ts = eval_ts.replace(tzinfo=timezone.utc)

    # 1. Combine lifecycle events
    merged_events = list(prior_events) + list(recovery_events)

    # 2. Check for compensatory refund evidence
    refund_ev = next((e for e in recovery_evidence if e.field_name == "refund_amount"), None)
    
    merged_evidence: List[Evidence] = []
    if refund_ev and isinstance(refund_ev.field_value, Money):
        # Calculate net observed amount: original_captured - refund_amount
        orig_amount_ev = next((e for e in prior_evidence if e.field_name == "total_amount"), None)
        if orig_amount_ev and isinstance(orig_amount_ev.field_value, Money):
            orig_money: Money = orig_amount_ev.field_value
            refund_money: Money = refund_ev.field_value

            if orig_money.currency == refund_money.currency:
                net_paise = max(0, orig_money.amount - refund_money.amount)
                net_money = Money(amount=net_paise, currency=orig_money.currency)

                # Authoritative net amount evidence supersedes raw pre-recovery total
                net_amount_ev = Evidence(
                    evidence_id=f"ev_reval_{orig_amount_ev.evidence_id}_net",
                    intent_id=contract.intent_id,
                    source=EvidenceSource.RAZORPAY,
                    authority=EvidenceAuthority.AUTHORITATIVE,
                    field_name="total_amount",
                    field_value=net_money,
                    observed_at=eval_ts,
                    raw_reference=f"net:{orig_amount_ev.raw_reference}:{refund_ev.raw_reference}",
                )
                merged_evidence.append(net_amount_ev)

        # Copy non-total_amount evidence from prior evidence
        for e in prior_evidence:
            if e.field_name != "total_amount":
                merged_evidence.append(e)

        # Append remaining recovery evidence
        for e in recovery_evidence:
            if e.field_name != "refund_amount":
                merged_evidence.append(e)
    else:
        # Standard merge without monetary netting
        merged_evidence = list(prior_evidence) + list(recovery_evidence)

    # 3. Deterministic revalidation using the authoritative T04 engine
    return evaluate_integrity(
        contract=contract,
        evidence_list=merged_evidence,
        events=merged_events,
        reference_time=eval_ts,
    )
