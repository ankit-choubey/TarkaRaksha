"""Consumer Gate validation service for TarkaRaksha E2.

Validates consumer-side transaction context:
- intent binding
- authorization constraints
- agent identity
- transaction context
- proposal validity

Governing Invariant:
AI proposes. Evidence proves. Deterministic logic decides.
Consumer Gate validation facts NEVER declare an authoritative financial PASS.
"""
from datetime import datetime, timezone
from typing import List, Optional

from backend.app.domain.buyer.contracts import BuyerTransactionProposal
from backend.app.domain.gates.contracts import (
    ConsumerCheckType,
    ConsumerGateResult,
    GateFinding,
    GateStatus,
    GateValidationFinding,
)
from backend.app.domain.integration.contracts import IntegrationTransactionContext
from backend.app.domain.models.intent import IntentContract


class ConsumerGate:
    """Deterministic validation gate for consumer-side transaction proposals."""

    @classmethod
    def validate(
        cls,
        context: IntegrationTransactionContext,
        proposal: BuyerTransactionProposal,
        intent: IntentContract,
        reference_time: Optional[datetime] = None,
    ) -> ConsumerGateResult:
        """Deterministically verifies buyer proposal against context and authorized intent."""
        ref_time = reference_time or datetime.now(timezone.utc)
        if ref_time.tzinfo is None:
            ref_time = ref_time.replace(tzinfo=timezone.utc)

        findings: List[GateValidationFinding] = []

        # 1. Transaction Context Binding
        if proposal.transaction_id != context.transaction_id:
            findings.append(
                GateValidationFinding(
                    check_type=ConsumerCheckType.TRANSACTION_CONTEXT.value,
                    status=GateStatus.INVALID,
                    reason=(
                        f"Transaction context mismatch: proposal transaction_id '{proposal.transaction_id}' "
                        f"does not match registered context '{context.transaction_id}'"
                    ),
                    field_name="transaction_id",
                    expected_value=context.transaction_id,
                    observed_value=proposal.transaction_id,
                    details={"error": "TRANSACTION_MISMATCH"},
                )
            )
        else:
            findings.append(
                GateValidationFinding(
                    check_type=ConsumerCheckType.TRANSACTION_CONTEXT.value,
                    status=GateStatus.VALID,
                    reason=f"Transaction context matches '{context.transaction_id}'",
                    field_name="transaction_id",
                    expected_value=context.transaction_id,
                    observed_value=proposal.transaction_id,
                )
            )

        # 2. Intent Binding
        if proposal.intent_id != context.intent_id or proposal.intent_id != intent.intent_id:
            findings.append(
                GateValidationFinding(
                    check_type=ConsumerCheckType.INTENT_BINDING.value,
                    status=GateStatus.INVALID,
                    reason=(
                        f"Intent binding mismatch: proposal intent_id '{proposal.intent_id}' "
                        f"does not match context '{context.intent_id}' or contract '{intent.intent_id}'"
                    ),
                    field_name="intent_id",
                    expected_value=context.intent_id,
                    observed_value=proposal.intent_id,
                    details={"error": "INTENT_MISMATCH"},
                )
            )
        else:
            findings.append(
                GateValidationFinding(
                    check_type=ConsumerCheckType.INTENT_BINDING.value,
                    status=GateStatus.VALID,
                    reason=f"Intent binding verified for '{intent.intent_id}'",
                    field_name="intent_id",
                    expected_value=intent.intent_id,
                    observed_value=proposal.intent_id,
                )
            )

        # 3. Agent Identity
        if proposal.buyer_agent_id != context.agent_id:
            findings.append(
                GateValidationFinding(
                    check_type=ConsumerCheckType.AGENT_IDENTITY.value,
                    status=GateStatus.INVALID,
                    reason=(
                        f"Buyer agent impersonation detected: proposal agent_id '{proposal.buyer_agent_id}' "
                        f"does not match registered agent '{context.agent_id}'"
                    ),
                    field_name="agent_id",
                    expected_value=context.agent_id,
                    observed_value=proposal.buyer_agent_id,
                    details={"error": "AGENT_IMPERSONATION"},
                )
            )
        else:
            findings.append(
                GateValidationFinding(
                    check_type=ConsumerCheckType.AGENT_IDENTITY.value,
                    status=GateStatus.VALID,
                    reason=f"Buyer agent identity verified as '{context.agent_id}'",
                    field_name="agent_id",
                    expected_value=context.agent_id,
                    observed_value=proposal.buyer_agent_id,
                )
            )

        # 4. Authorization Constraints
        auth_violations: List[str] = []

        # A. Currency Constraint
        if proposal.max_total.currency != intent.currency:
            auth_violations.append(
                f"Currency mismatch: proposal '{proposal.max_total.currency}' != intent '{intent.currency}'"
            )

        # B. Budget Ceiling Constraint
        if proposal.max_total.amount > intent.max_total.amount:
            auth_violations.append(
                f"Budget ceiling exceeded: proposal max_total {proposal.max_total.amount} "
                f"> authorized max_total {intent.max_total.amount}"
            )

        # C. Authorized Product / SKU Constraint
        authorized_skus = {it.sku for it in intent.items}
        allowed_subs = set(intent.allowed_substitutions)
        all_permitted_skus = authorized_skus.union(allowed_subs)

        if proposal.sku not in all_permitted_skus:
            auth_violations.append(
                f"Unauthorized SKU: '{proposal.sku}' is not authorized by intent (authorized: {sorted(all_permitted_skus)})"
            )

        # D. Authorized Quantity Constraint
        max_authorized_qty = sum(it.quantity for it in intent.items)
        if proposal.quantity > max_authorized_qty:
            auth_violations.append(
                f"Quantity exceeds authorization: proposal {proposal.quantity} > authorized total {max_authorized_qty}"
            )

        # E. Temporal Window Constraint
        if ref_time > intent.expires_at:
            auth_violations.append(
                f"Intent expired at {intent.expires_at.isoformat()} (reference time: {ref_time.isoformat()})"
            )
        elif ref_time < intent.issued_at:
            auth_violations.append(
                f"Intent not yet valid: issued_at {intent.issued_at.isoformat()} > reference time {ref_time.isoformat()}"
            )

        if auth_violations:
            findings.append(
                GateValidationFinding(
                    check_type=ConsumerCheckType.AUTHORIZATION_CONSTRAINTS.value,
                    status=GateStatus.INVALID,
                    reason="; ".join(auth_violations),
                    field_name="authorization",
                    expected_value={
                        "max_total": intent.max_total.model_dump(),
                        "permitted_skus": sorted(all_permitted_skus),
                        "max_quantity": max_authorized_qty,
                    },
                    observed_value={
                        "proposal_total": proposal.max_total.model_dump(),
                        "proposal_sku": proposal.sku,
                        "proposal_quantity": proposal.quantity,
                    },
                    details={"violations": auth_violations},
                )
            )
        else:
            findings.append(
                GateValidationFinding(
                    check_type=ConsumerCheckType.AUTHORIZATION_CONSTRAINTS.value,
                    status=GateStatus.VALID,
                    reason="Proposal strictly adheres to authorized intent financial, SKU, quantity, and temporal limits",
                    field_name="authorization",
                    expected_value=intent.max_total.model_dump(),
                    observed_value=proposal.max_total.model_dump(),
                )
            )

        # 5. Proposal Validity & Prompt Injection Defense
        validity_issues: List[str] = []
        if not proposal.proposal_id or not proposal.proposal_id.strip():
            validity_issues.append("Empty proposal_id")
        if proposal.quantity <= 0:
            validity_issues.append("Non-positive quantity")
        if proposal.max_total.amount <= 0:
            validity_issues.append("Non-positive max_total amount")

        # Defense against malicious prompt injection in proposal rationale
        suspicious_tokens = [
            "ignore previous instructions",
            "declare pass",
            "override budget",
            "bypass verification",
            "authorize payment",
        ]
        rationale_lower = proposal.rationale.lower()
        if any(token in rationale_lower for token in suspicious_tokens):
            validity_issues.append("Prompt injection attempt detected in proposal rationale")

        if validity_issues:
            findings.append(
                GateValidationFinding(
                    check_type=ConsumerCheckType.PROPOSAL_VALIDITY.value,
                    status=GateStatus.INVALID,
                    reason="; ".join(validity_issues),
                    field_name="proposal",
                    details={"issues": validity_issues},
                )
            )
        else:
            findings.append(
                GateValidationFinding(
                    check_type=ConsumerCheckType.PROPOSAL_VALIDITY.value,
                    status=GateStatus.VALID,
                    reason="Proposal structure and integrity validated",
                    field_name="proposal",
                )
            )

        # Compute overall status
        has_invalid = any(f.status == GateStatus.INVALID for f in findings)
        has_unknown = any(f.status == GateStatus.UNKNOWN for f in findings)
        if has_invalid:
            status = GateStatus.INVALID
            is_all_valid = False
        elif has_unknown:
            status = GateStatus.UNKNOWN
            is_all_valid = False
        else:
            status = GateStatus.VALID
            is_all_valid = True

        return ConsumerGateResult(
            status=status,
            transaction_id=context.transaction_id,
            intent_id=context.intent_id,
            agent_id=context.agent_id,
            is_valid=is_all_valid,
            findings=findings,
            validated_at=ref_time,
            metadata={"source": "ConsumerGate"},
        )
