"""Context builder for I21 Evidence-Aware AI Explanation.

Extracts, sanitizes, and normalizes factual evidence and deterministic decisions
into an immutable, serializable ExplanationContext.
Shields the AI prompt from sensitive credentials, secrets, and irrelevant payload noise.
"""
from datetime import datetime, timezone
import uuid
from typing import Any, Dict, List, Optional

from backend.app.domain.binding.contracts import BindingVerificationOutcome
from backend.app.domain.explanation.contracts import (
    EvidenceReference,
    ExplanationContext,
)
from backend.app.domain.kill_switch.contracts import KillSwitchRecord, KillSwitchState, KillTrigger
from backend.app.domain.models import (
    CanonicalEvent,
    Evidence,
    EvidenceBundle,
    IntegrityResult,
    IntegrityStatus,
    IntentContract,
    MRDP,
    ProviderOrder,
    ProviderPayment,
)
from backend.app.domain.models.enums import EvidenceAuthority, EvidenceSource


class ExplanationContextBuilder:
    """
    Deterministic builder for ExplanationContext.
    Gathers evidence across T04 (Integrity Engine), I8 (Binding), I9 (Kill Switch),
    T06 (MRDP), and payment gateway objects.
    """

    @classmethod
    def build_context(
        cls,
        transaction_id: str,
        intent: IntentContract,
        integrity_result: Optional[IntegrityResult] = None,
        binding_outcome: Optional[BindingVerificationOutcome] = None,
        kill_switch_state: KillSwitchState = KillSwitchState.RUNNING,
        kill_switch_record: Optional[KillSwitchRecord] = None,
        evidence_bundle: Optional[EvidenceBundle] = None,
        evidence_list: Optional[List[Evidence]] = None,
        events: Optional[List[CanonicalEvent]] = None,
        order: Optional[ProviderOrder] = None,
        payment: Optional[ProviderPayment] = None,
        mrdp: Optional[MRDP] = None,
        governance_version: Optional[str] = "gov_v1.0.0",
        rules_version: Optional[str] = "rules_v1.0.0",
        snapshot_hash: Optional[str] = None,
        certificate_id: Optional[str] = None,
        reference_time: Optional[datetime] = None,
        integrity_trace: Optional[Any] = None,
        integrity_checkpoints: Optional[Any] = None,
        integrity_sla_report: Optional[Any] = None,
    ) -> ExplanationContext:
        """
        Builds a frozen ExplanationContext.
        Guarantees that all evidence IDs cited in findings exist in evidence_references.
        """
        ref_time = reference_time or datetime.now(timezone.utc)
        context_id = f"ctx_{uuid.uuid4().hex[:12]}"

        # 1. Resolve raw evidence records
        raw_evidence: List[Evidence] = []
        if evidence_bundle and evidence_bundle.records:
            raw_evidence.extend(evidence_bundle.records)
        if evidence_list:
            raw_evidence.extend(evidence_list)

        # De-duplicate by evidence_id
        seen_ev_ids = set()
        unique_evidence: List[Evidence] = []
        for ev in raw_evidence:
            if ev.evidence_id not in seen_ev_ids:
                seen_ev_ids.add(ev.evidence_id)
                unique_evidence.append(ev)

        # 2. Extract Deterministic Decision & Violations
        if integrity_result:
            decision = integrity_result.status
            reason = integrity_result.explanation or f"Integrity status: {decision.value}"
            integrity_violations = list(integrity_result.violations)
        else:
            decision = IntegrityStatus.UNKNOWN
            reason = "No integrity evaluation has been performed for this transaction"
            integrity_violations = []

        # 3. Extract Binding Findings
        binding_violations: List[str] = []
        if binding_outcome:
            binding_violations = [v.value for v in binding_outcome.violations]
            if not binding_outcome.is_valid and decision != IntegrityStatus.DRIFT:
                # Binding violations trigger drift in system context
                pass

        # 4. Resolve Kill Switch Trigger & Revalidation
        ks_trigger: Optional[KillTrigger] = None
        reval_reqs: List[str] = []
        if kill_switch_record:
            ks_trigger = kill_switch_record.trigger
            if kill_switch_record.revalidation_requirements:
                reval_reqs = list(kill_switch_record.revalidation_requirements)

        # 5. Build EvidenceReferences with expected vs observed mappings
        ev_refs: List[EvidenceReference] = []

        # (a) Intent-level baseline references
        ev_refs.append(
            EvidenceReference(
                evidence_id=f"ev_intent_amt_{intent.intent_id}",
                field_name="authorized_amount",
                source=EvidenceSource.INTENT,
                authority=EvidenceAuthority.PROTOCOL_TRUSTED,
                observed_value=intent.max_total.amount,
                expected_value=intent.max_total.amount,
                is_authoritative=True,
                description=f"Authorized spending cap: {intent.max_total.currency} {intent.max_total.amount} minor units",
            )
        )
        ev_refs.append(
            EvidenceReference(
                evidence_id=f"ev_intent_curr_{intent.intent_id}",
                field_name="authorized_currency",
                source=EvidenceSource.INTENT,
                authority=EvidenceAuthority.PROTOCOL_TRUSTED,
                observed_value=intent.currency,
                expected_value=intent.currency,
                is_authoritative=True,
                description=f"Authorized currency code: {intent.currency}",
            )
        )

        # (b) Normalized Evidence from bundle/events
        for ev in unique_evidence:
            expected_val = None
            if "amount" in ev.field_name.lower():
                expected_val = intent.max_total.amount
            elif "currency" in ev.field_name.lower():
                expected_val = intent.currency

            ev_refs.append(
                EvidenceReference(
                    evidence_id=ev.evidence_id,
                    field_name=ev.field_name,
                    source=ev.source,
                    authority=ev.effective_authority,
                    observed_value=cls._sanitize_value(ev.field_value),
                    expected_value=expected_val,
                    is_authoritative=ev.is_authoritative,
                    description=f"Observed from {ev.source.value} with {ev.effective_authority.value} authority",
                )
            )

        # (c) Provider Order evidence reference if present
        if order:
            ev_refs.append(
                EvidenceReference(
                    evidence_id=f"ev_order_{order.order_id}",
                    field_name="gateway_order",
                    source=EvidenceSource.RAZORPAY,
                    authority=EvidenceAuthority.AUTHORITATIVE,
                    observed_value={
                        "order_id": order.order_id,
                        "amount_minor": order.amount.amount,
                        "currency": order.amount.currency,
                        "status": order.status,
                    },
                    expected_value={
                        "amount_minor": intent.max_total.amount,
                        "currency": intent.currency,
                    },
                    is_authoritative=True,
                    description=f"Gateway order {order.order_id} record",
                )
            )

        # (d) Provider Payment evidence reference if present
        if payment:
            ev_refs.append(
                EvidenceReference(
                    evidence_id=f"ev_payment_{payment.payment_id}",
                    field_name="gateway_payment",
                    source=EvidenceSource.RAZORPAY,
                    authority=EvidenceAuthority.AUTHORITATIVE,
                    observed_value={
                        "payment_id": payment.payment_id,
                        "order_id": payment.order_id,
                        "amount_minor": payment.amount.amount,
                        "currency": payment.amount.currency,
                        "status": payment.status,
                    },
                    expected_value={
                        "order_id": order.order_id if order else None,
                        "amount_minor": intent.max_total.amount,
                        "currency": intent.currency,
                    },
                    is_authoritative=True,
                    description=f"Gateway payment {payment.payment_id} record",
                )
            )

        # (e) Binding outcome evidence reference if present
        if binding_outcome:
            binding_ev = binding_outcome.to_evidence(
                intent_id=intent.intent_id,
                transaction_id=transaction_id,
            )
            ev_refs.append(
                EvidenceReference(
                    evidence_id=binding_ev.evidence_id,
                    field_name=binding_ev.field_name,
                    source=binding_ev.source,
                    authority=binding_ev.effective_authority,
                    observed_value=binding_ev.field_value,
                    expected_value={"is_valid": True, "violations": []},
                    is_authoritative=True,
                    description="Transaction identity 7-tuple binding verification outcome",
                )
            )

        # (f) Kill switch record reference if present
        if kill_switch_record:
            ev_refs.append(
                EvidenceReference(
                    evidence_id=f"ev_ks_{kill_switch_record.record_id}",
                    field_name="kill_switch_state",
                    source=EvidenceSource.SYSTEM,
                    authority=kill_switch_record.authority,
                    observed_value={
                        "state": kill_switch_record.resulting_state.value,
                        "decision": kill_switch_record.decision.value,
                        "trigger": kill_switch_record.trigger.value if kill_switch_record.trigger else None,
                        "reason": kill_switch_record.reason,
                    },
                    expected_value={"state": KillSwitchState.RUNNING.value},
                    is_authoritative=True,
                    description=f"Execution safety control record: {kill_switch_record.resulting_state.value}",
                )
            )

        # 6. Detect Missing Evidence & Uncertainties
        missing_evidence: List[str] = []
        uncertainty_notes: List[str] = []

        if not payment:
            missing_evidence.append("authoritative_payment_capture_confirmation")
        if not order:
            missing_evidence.append("gateway_order_record")
        if not binding_outcome:
            missing_evidence.append("transaction_binding_claim")

        if decision == IntegrityStatus.UNKNOWN:
            if not payment:
                uncertainty_notes.append("Authoritative payment confirmation from gateway was not ingested")
            if integrity_result and integrity_result.violations:
                uncertainty_notes.extend(integrity_result.violations)
            else:
                uncertainty_notes.append("System could not establish facts with authoritative confidence")

        if integrity_trace:
            if hasattr(integrity_trace, "missing_evidence") and integrity_trace.missing_evidence:
                missing_evidence.extend(integrity_trace.missing_evidence)
            if hasattr(integrity_trace, "uncertainties") and integrity_trace.uncertainties:
                uncertainty_notes.extend(integrity_trace.uncertainties)

        if integrity_checkpoints:
            last_val = getattr(integrity_checkpoints, "last_valid_checkpoint", None)
            if last_val:
                ev_refs.append(
                    EvidenceReference(
                        evidence_id=f"ev_{last_val.checkpoint_id}",
                        field_name="last_valid_checkpoint",
                        source=EvidenceSource.SYSTEM,
                        authority=EvidenceAuthority.AUTHORITATIVE,
                        observed_value={
                            "checkpoint_type": last_val.checkpoint_type.value,
                            "sequence": last_val.sequence,
                            "status": last_val.status.value,
                        },
                        expected_value={"status": "VALID"},
                        is_authoritative=True,
                        description=f"Last verified valid boundary: {last_val.checkpoint_type.value} (sequence {last_val.sequence})",
                    )
                )
            first_inv = getattr(integrity_checkpoints, "first_invalid_checkpoint", None)
            if first_inv:
                ev_refs.append(
                    EvidenceReference(
                        evidence_id=f"ev_{first_inv.checkpoint_id}",
                        field_name="first_invalid_checkpoint",
                        source=EvidenceSource.SYSTEM,
                        authority=EvidenceAuthority.AUTHORITATIVE,
                        observed_value={
                            "checkpoint_type": first_inv.checkpoint_type.value,
                            "sequence": first_inv.sequence,
                            "status": first_inv.status.value,
                            "findings": first_inv.findings,
                        },
                        expected_value={"status": "VALID"},
                        is_authoritative=True,
                        description=f"First invalid boundary: {first_inv.checkpoint_type.value} (sequence {first_inv.sequence})",
                    )
                )
            if getattr(integrity_checkpoints, "has_unknown_checkpoints", False):
                uncertainty_notes.append("Transaction timeline contains UNKNOWN checkpoint boundaries awaiting authoritative evidence")

        if integrity_sla_report and hasattr(integrity_sla_report, "metrics"):
            for m in integrity_sla_report.metrics:
                m_name = m.metric_name.value if hasattr(m.metric_name, "value") else str(m.metric_name)
                m_status = m.status.value if hasattr(m.status, "value") else str(m.status)
                m_unit = m.unit.value if hasattr(m.unit, "value") else str(m.unit)
                if m_status == "MEASURABLE":
                    ev_refs.append(
                        EvidenceReference(
                            evidence_id=f"ev_sla_{m_name.lower()}",
                            field_name=m_name.lower(),
                            source=EvidenceSource.SYSTEM,
                            authority=EvidenceAuthority.AUTHORITATIVE,
                            observed_value={
                                "value": m.value,
                                "unit": m_unit,
                                "status": m_status,
                                "is_compliant": m.is_compliant,
                            },
                            expected_value={"threshold": m.threshold},
                            is_authoritative=True,
                            description=f"Deterministic SLA Metric {m_name}: {m.value} {m_unit} (compliant: {m.is_compliant})",
                        )
                    )
                elif m_status == "UNKNOWN":
                    uncertainty_notes.append(f"SLA metric {m_name} is UNKNOWN: {m.calculation_reason}")

        # 7. Extract identifiers
        agent_id = getattr(intent, "issued_by", None)
        merchant_id = getattr(order, "notes", {}).get("merchant_id") if order else None
        order_id = order.order_id if order else None
        payment_id = payment.payment_id if payment else None

        return ExplanationContext(
            context_id=context_id,
            transaction_id=transaction_id,
            intent_id=intent.intent_id,
            agent_id=agent_id,
            merchant_id=merchant_id,
            order_id=order_id,
            payment_id=payment_id,
            attempt_id="att_1",
            deterministic_decision=decision,
            decision_reason=reason,
            kill_switch_state=kill_switch_state,
            kill_switch_trigger=ks_trigger,
            integrity_violations=integrity_violations,
            binding_violations=binding_violations,
            evidence_references=ev_refs,
            missing_evidence_fields=missing_evidence,
            uncertainty_notes=uncertainty_notes,
            revalidation_requirements=reval_reqs,
            governance_version=governance_version,
            rules_version=rules_version,
            snapshot_hash=snapshot_hash,
            certificate_id=certificate_id,
            mrdp_digest=mrdp.proof_digest if mrdp else None,
            created_at=ref_time,
        )

    @classmethod
    def _sanitize_value(cls, val: Any) -> Any:
        """Sanitizes raw values to remove secrets, tokens, or keys."""
        import re
        if isinstance(val, str):
            return re.sub(
                r"(secret|token|api_key|password|signature)\s*=\s*[^\s,;]+",
                r"\1=[REDACTED]",
                val,
                flags=re.IGNORECASE,
            )
        elif isinstance(val, dict):
            clean = {}
            for k, v in val.items():
                k_lower = str(k).lower()
                if any(sec in k_lower for sec in ["secret", "api_key", "password", "token", "signature"]):
                    clean[k] = "[REDACTED]"
                else:
                    clean[k] = cls._sanitize_value(v)
            return clean
        elif isinstance(val, list):
            return [cls._sanitize_value(item) for item in val]
        return val

