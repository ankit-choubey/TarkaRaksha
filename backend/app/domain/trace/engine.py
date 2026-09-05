"""Deterministic Trace Engine for Innovation I13 — Integrity Trace / Fault Localization.

Evaluates the canonical 8-stage transaction lifecycle chronologically:
INTENT (1) -> AGENT (2) -> MERCHANT (3) -> ORDER (4) -> ATTEMPT (5) -> PAYMENT (6) -> GATEWAY (7) -> COMPLETION (8).

Core Invariant:
AI proposes -> evidence proves -> deterministic logic decides.
Zero LLM involvement. Zero decision changes (cannot alter PASS/DRIFT/UNKNOWN or KillSwitchState).
Deterministic, reproducible, secret-sanitizing.
"""
from datetime import datetime, timezone
import re
from typing import Any, Dict, List, Optional
import uuid

from backend.app.domain.models.enums import IntegrityStatus, TransactionState
from backend.app.domain.models.intent import IntentContract
from backend.app.domain.models.payment import ProviderOrder, ProviderPayment
from backend.app.domain.models.evidence import CanonicalEvent, Evidence, EvidenceBundle
from backend.app.domain.models.integrity import MRDP, IntegrityResult
from backend.app.domain.binding.contracts import (
    BindingContext,
    BindingVerificationOutcome,
    BindingViolationCode,
)
from backend.app.domain.kill_switch.contracts import (
    KillSwitchRecord,
    KillSwitchState,
    KillTrigger,
)
from .contracts import (
    ContextBindingSnapshot,
    FaultLocation,
    FieldDiscrepancy,
    FirstDivergence,
    IntegrityTrace,
    LifecycleStage,
    LifecycleStep,
    StageIntegrityStatus,
)


class DeterministicTraceEngine:
    """
    Pure deterministic engine for generating authoritative IntegrityTraces.
    Answers: Where in the lifecycle did integrity diverge, what evidence proves it,
    what changed, and which component is implicated?
    """

    @classmethod
    def build_trace(
        cls,
        transaction_id: str,
        intent: Optional[IntentContract] = None,
        order: Optional[ProviderOrder] = None,
        payment: Optional[ProviderPayment] = None,
        binding_context: Optional[BindingContext] = None,
        binding_outcome: Optional[BindingVerificationOutcome] = None,
        integrity_result: Optional[IntegrityResult] = None,
        kill_switch_state: KillSwitchState = KillSwitchState.RUNNING,
        kill_switch_record: Optional[KillSwitchRecord] = None,
        evidence_bundle: Optional[EvidenceBundle] = None,
        evidence_list: Optional[List[Evidence]] = None,
        events: Optional[List[CanonicalEvent]] = None,
        mrdp: Optional[MRDP] = None,
        state_machine_state: Optional[TransactionState] = None,
        reference_time: Optional[datetime] = None,
        governance_version: str = "gov_v1.0.0",
        trace_id: Optional[str] = None,
    ) -> IntegrityTrace:
        """
        Builds a complete, deterministic, frozen IntegrityTrace.
        Evaluates the 8 lifecycle stages in chronological order.
        """
        ref_time = reference_time or datetime.now(timezone.utc)
        t_id = trace_id or f"trc_{uuid.uuid4().hex[:12]}"

        # Resolve evidence map
        all_evidence: List[Evidence] = []
        if evidence_bundle and evidence_bundle.records:
            all_evidence.extend(evidence_bundle.records)
        if evidence_list:
            all_evidence.extend(evidence_list)
        
        evidence_ids = {ev.evidence_id for ev in all_evidence}

        # 1. Build Context Binding Snapshot
        snapshot = cls._build_binding_snapshot(
            transaction_id=transaction_id,
            intent=intent,
            order=order,
            payment=payment,
            binding_context=binding_context,
            binding_outcome=binding_outcome,
        )

        missing_evidence: List[str] = []
        uncertainties: List[str] = []

        # 2. Evaluate 8 Stages Chronologically
        steps: List[LifecycleStep] = []

        # Stage 1: INTENT
        step_intent = cls._evaluate_intent_stage(
            intent=intent,
            reference_time=ref_time,
            evidence_ids=evidence_ids,
            missing_evidence=missing_evidence,
        )
        steps.append(step_intent)

        # Stage 2: AGENT
        step_agent = cls._evaluate_agent_stage(
            binding_context=binding_context,
            binding_outcome=binding_outcome,
            intent=intent,
            evidence_ids=evidence_ids,
            missing_evidence=missing_evidence,
        )
        steps.append(step_agent)

        # Stage 3: MERCHANT
        step_merchant = cls._evaluate_merchant_stage(
            binding_context=binding_context,
            binding_outcome=binding_outcome,
            order=order,
            integrity_result=integrity_result,
            evidence_ids=evidence_ids,
            missing_evidence=missing_evidence,
        )
        steps.append(step_merchant)

        # Stage 4: ORDER
        step_order = cls._evaluate_order_stage(
            intent=intent,
            order=order,
            binding_outcome=binding_outcome,
            state_machine_state=state_machine_state,
            evidence_ids=evidence_ids,
            missing_evidence=missing_evidence,
        )
        steps.append(step_order)

        # Stage 5: ATTEMPT
        step_attempt = cls._evaluate_attempt_stage(
            binding_outcome=binding_outcome,
            kill_switch_record=kill_switch_record,
            state_machine_state=state_machine_state,
            evidence_ids=evidence_ids,
            missing_evidence=missing_evidence,
        )
        steps.append(step_attempt)

        # Stage 6: PAYMENT
        step_payment = cls._evaluate_payment_stage(
            intent=intent,
            order=order,
            payment=payment,
            integrity_result=integrity_result,
            binding_outcome=binding_outcome,
            state_machine_state=state_machine_state,
            evidence_ids=evidence_ids,
            missing_evidence=missing_evidence,
        )
        steps.append(step_payment)

        # Stage 7: GATEWAY
        step_gateway = cls._evaluate_gateway_stage(
            payment=payment,
            events=events,
            binding_outcome=binding_outcome,
            state_machine_state=state_machine_state,
            evidence_ids=evidence_ids,
            missing_evidence=missing_evidence,
        )
        steps.append(step_gateway)

        # Stage 8: COMPLETION
        step_completion = cls._evaluate_completion_stage(
            steps=steps,
            mrdp=mrdp,
            state_machine_state=state_machine_state,
            integrity_result=integrity_result,
            evidence_ids=evidence_ids,
            missing_evidence=missing_evidence,
        )
        steps.append(step_completion)

        # 3. First Divergence & Fault Localization
        first_divergence: Optional[FirstDivergence] = None
        fault_locations: List[FaultLocation] = []

        for step in steps:
            if step.status == StageIntegrityStatus.DIVERGENCE_DETECTED:
                if first_divergence is None:
                    primary_disc = step.discrepancies[0] if step.discrepancies else None
                    first_divergence = FirstDivergence(
                        stage=step.stage,
                        step_sequence=step.sequence,
                        finding=step.findings[0] if step.findings else "DIVERGENCE_DETECTED",
                        primary_discrepancy=primary_disc,
                        evidence_refs=step.evidence_refs,
                        detected_at=step.timestamp or ref_time,
                    )

                    # Strict UNKNOWN Check: check if any earlier stage is UNKNOWN
                    for prev_step in steps:
                        if prev_step.sequence < step.sequence and prev_step.status == StageIntegrityStatus.UNKNOWN:
                            uncertainties.append(
                                f"Earlier stage '{prev_step.stage.value}' (step {prev_step.sequence}) is UNKNOWN due to missing evidence; "
                                f"first divergence at stage '{step.stage.value}' may be downstream of an unobserved earlier fault."
                            )

                # Collect fault locations for all diverging steps (preserves subsequent faults)
                comp = cls._map_component(step.stage)
                for f_code in step.findings:
                    fault_locations.append(
                        FaultLocation(
                            stage=step.stage,
                            component=comp,
                            finding_code=f_code,
                            description=f"Divergence detected at stage {step.stage.value}: {f_code}",
                            evidence_refs=step.evidence_refs,
                            is_authoritative=True,
                        )
                    )

        # 4. Integrate Kill Switch fault location if blocked/killed
        if kill_switch_state in (KillSwitchState.KILLED, KillSwitchState.REQUIRES_REVALIDATION, KillSwitchState.PAUSED):
            trigger_code = kill_switch_record.trigger.value if (kill_switch_record and kill_switch_record.trigger) else "SAFETY_INTERVENTION"
            ks_stage = cls._map_trigger_to_stage(kill_switch_record.trigger if kill_switch_record else None)
            fault_locations.append(
                FaultLocation(
                    stage=ks_stage,
                    component="execution_safety_kill_switch",
                    finding_code=trigger_code,
                    description=f"Execution halted by Kill Switch with state {kill_switch_state.value} (trigger: {trigger_code})",
                    evidence_refs=kill_switch_record.details.get("evidence_ids", []) if (kill_switch_record and hasattr(kill_switch_record, "details")) else [],
                    is_authoritative=True,
                )
            )

        # 5. Resolve Deterministic Decision
        if integrity_result is not None:
            det_decision = integrity_result.status
        elif any(s.status == StageIntegrityStatus.DIVERGENCE_DETECTED for s in steps):
            det_decision = IntegrityStatus.DRIFT
        elif any(s.status == StageIntegrityStatus.UNKNOWN for s in steps):
            det_decision = IntegrityStatus.UNKNOWN
        else:
            det_decision = IntegrityStatus.PASS

        # Reproducibility reference
        repro_ref = None
        if mrdp and mrdp.mrdp_id:
            repro_ref = mrdp.mrdp_id
        elif integrity_result and hasattr(integrity_result, "evidence_digest"):
            repro_ref = integrity_result.evidence_digest

        return IntegrityTrace(
            trace_id=t_id,
            transaction_id=transaction_id,
            deterministic_decision=det_decision,
            execution_state=kill_switch_state,
            context_bindings=snapshot,
            steps=steps,
            first_divergence=first_divergence,
            fault_locations=fault_locations,
            missing_evidence=list(dict.fromkeys(missing_evidence)),
            uncertainties=list(dict.fromkeys(uncertainties)),
            governance_version=governance_version,
            reproducibility_reference=repro_ref,
            generated_at=ref_time,
        )

    # -------------------------------------------------------------------------
    # Stage Evaluators
    # -------------------------------------------------------------------------

    @classmethod
    def _evaluate_intent_stage(
        cls,
        intent: Optional[IntentContract],
        reference_time: datetime,
        evidence_ids: set,
        missing_evidence: List[str],
    ) -> LifecycleStep:
        discrepancies: List[FieldDiscrepancy] = []
        findings: List[str] = []
        evidence_refs: List[str] = [eid for eid in evidence_ids if "intent" in eid.lower()]

        if intent is None:
            missing_evidence.append("intent_contract")
            return LifecycleStep(
                sequence=1,
                stage=LifecycleStage.INTENT,
                status=StageIntegrityStatus.UNKNOWN,
                expected_context={"intent_contract": "authorized_intent"},
                observed_context={},
                discrepancies=[
                    FieldDiscrepancy(
                        field_name="intent_contract",
                        expected_value="authorized_intent",
                        observed_value=None,
                        description="IntentContract missing from transaction context",
                    )
                ],
                findings=["INTENT_MISSING"],
                evidence_refs=[],
                timestamp=reference_time,
            )

        exp_ctx = {
            "intent_id": intent.intent_id,
            "currency": intent.currency,
            "max_total": intent.max_total.amount,
            "expires_at": intent.expires_at.isoformat(),
        }
        obs_ctx = cls._sanitize_dict(exp_ctx)

        # Check intent expiration
        if intent.expires_at < reference_time:
            discrepancies.append(
                FieldDiscrepancy(
                    field_name="expires_at",
                    expected_value=f"> {reference_time.isoformat()}",
                    observed_value=intent.expires_at.isoformat(),
                    description="IntentContract authorization has expired",
                )
            )
            findings.append("INTENT_EXPIRED")

        # Check non-positive amount
        if intent.max_total.amount <= 0:
            discrepancies.append(
                FieldDiscrepancy(
                    field_name="max_total.amount",
                    expected_value="> 0",
                    observed_value=intent.max_total.amount,
                    description="IntentContract authorizes non-positive amount",
                )
            )
            findings.append("INTENT_INVALID_AMOUNT")

        status = StageIntegrityStatus.DIVERGENCE_DETECTED if findings else StageIntegrityStatus.CONFIRMED_VALID

        return LifecycleStep(
            sequence=1,
            stage=LifecycleStage.INTENT,
            status=status,
            expected_context=exp_ctx,
            observed_context=obs_ctx,
            discrepancies=discrepancies,
            findings=findings,
            evidence_refs=evidence_refs,
            timestamp=intent.issued_at,
        )

    @classmethod
    def _evaluate_agent_stage(
        cls,
        binding_context: Optional[BindingContext],
        binding_outcome: Optional[BindingVerificationOutcome],
        intent: Optional[IntentContract],
        evidence_ids: set,
        missing_evidence: List[str],
    ) -> LifecycleStep:
        discrepancies: List[FieldDiscrepancy] = []
        findings: List[str] = []
        evidence_refs = [eid for eid in evidence_ids if "agent" in eid.lower()]

        if binding_outcome and BindingViolationCode.AGENT_MISMATCH in binding_outcome.violations:
            expected_agent = binding_context.agent_id if binding_context else "authorized_agent"
            observed_agent = binding_outcome.details.get("claimed_agent_id", "unauthorized_agent")
            discrepancies.append(
                FieldDiscrepancy(
                    field_name="agent_id",
                    expected_value=expected_agent,
                    observed_value=observed_agent,
                    description="Executing agent does not match authorized binding context",
                )
            )
            findings.append(BindingViolationCode.AGENT_MISMATCH.value)
            return LifecycleStep(
                sequence=2,
                stage=LifecycleStage.AGENT,
                status=StageIntegrityStatus.DIVERGENCE_DETECTED,
                expected_context={"agent_id": expected_agent},
                observed_context={"agent_id": observed_agent},
                discrepancies=discrepancies,
                findings=findings,
                evidence_refs=evidence_refs,
                timestamp=binding_outcome.verified_at,
            )

        if binding_context is None:
            missing_evidence.append("agent_binding_context")
            return LifecycleStep(
                sequence=2,
                stage=LifecycleStage.AGENT,
                status=StageIntegrityStatus.UNKNOWN,
                expected_context={"agent_id": "authorized_agent"},
                observed_context={},
                discrepancies=[],
                findings=["AGENT_BINDING_MISSING"],
                evidence_refs=[],
                timestamp=None,
            )

        return LifecycleStep(
            sequence=2,
            stage=LifecycleStage.AGENT,
            status=StageIntegrityStatus.CONFIRMED_VALID,
            expected_context={"agent_id": binding_context.agent_id},
            observed_context={"agent_id": binding_context.agent_id},
            discrepancies=[],
            findings=[],
            evidence_refs=evidence_refs,
            timestamp=binding_context.created_at,
        )

    @classmethod
    def _evaluate_merchant_stage(
        cls,
        binding_context: Optional[BindingContext],
        binding_outcome: Optional[BindingVerificationOutcome],
        order: Optional[ProviderOrder],
        integrity_result: Optional[IntegrityResult],
        evidence_ids: set,
        missing_evidence: List[str],
    ) -> LifecycleStep:
        discrepancies: List[FieldDiscrepancy] = []
        findings: List[str] = []
        evidence_refs = [eid for eid in evidence_ids if "merchant" in eid.lower()]

        if binding_outcome and BindingViolationCode.MERCHANT_MISMATCH in binding_outcome.violations:
            expected_m = binding_context.merchant_id if binding_context else "authorized_merchant"
            observed_m = binding_outcome.details.get("claimed_merchant_id", "unauthorized_merchant")
            discrepancies.append(
                FieldDiscrepancy(
                    field_name="merchant_id",
                    expected_value=expected_m,
                    observed_value=observed_m,
                    description="Merchant identity mismatch against authorized binding context",
                )
            )
            findings.append(BindingViolationCode.MERCHANT_MISMATCH.value)
            return LifecycleStep(
                sequence=3,
                stage=LifecycleStage.MERCHANT,
                status=StageIntegrityStatus.DIVERGENCE_DETECTED,
                expected_context={"merchant_id": expected_m},
                observed_context={"merchant_id": observed_m},
                discrepancies=discrepancies,
                findings=findings,
                evidence_refs=evidence_refs,
                timestamp=binding_outcome.verified_at,
            )

        if binding_context is None and order is None:
            missing_evidence.append("merchant_evidence")
            return LifecycleStep(
                sequence=3,
                stage=LifecycleStage.MERCHANT,
                status=StageIntegrityStatus.UNKNOWN,
                expected_context={"merchant_id": "authorized_merchant"},
                observed_context={},
                discrepancies=[],
                findings=["MERCHANT_EVIDENCE_MISSING"],
                evidence_refs=[],
                timestamp=None,
            )

        m_id = (
            binding_context.merchant_id
            if binding_context
            else (getattr(order, "merchant_id", None) or (order.notes.get("merchant_id") if order and hasattr(order, "notes") else None) or "unknown_merchant")
        )
        return LifecycleStep(
            sequence=3,
            stage=LifecycleStage.MERCHANT,
            status=StageIntegrityStatus.CONFIRMED_VALID,
            expected_context={"merchant_id": m_id},
            observed_context={"merchant_id": m_id},
            discrepancies=[],
            findings=[],
            evidence_refs=evidence_refs,
            timestamp=binding_context.created_at if binding_context else None,
        )

    @classmethod
    def _evaluate_order_stage(
        cls,
        intent: Optional[IntentContract],
        order: Optional[ProviderOrder],
        binding_outcome: Optional[BindingVerificationOutcome],
        state_machine_state: Optional[TransactionState],
        evidence_ids: set,
        missing_evidence: List[str],
    ) -> LifecycleStep:
        discrepancies: List[FieldDiscrepancy] = []
        findings: List[str] = []
        evidence_refs = [eid for eid in evidence_ids if "order" in eid.lower()]

        if binding_outcome and BindingViolationCode.ORDER_MISMATCH in binding_outcome.violations:
            discrepancies.append(
                FieldDiscrepancy(
                    field_name="order_id",
                    expected_value=binding_outcome.details.get("expected_order_id", "authorized_order"),
                    observed_value=binding_outcome.details.get("claimed_order_id", "mismatched_order"),
                    description="Order ID mismatch against authorized binding context",
                )
            )
            findings.append(BindingViolationCode.ORDER_MISMATCH.value)
            return LifecycleStep(
                sequence=4,
                stage=LifecycleStage.ORDER,
                status=StageIntegrityStatus.DIVERGENCE_DETECTED,
                expected_context={"order_id": binding_outcome.details.get("expected_order_id")},
                observed_context={"order_id": binding_outcome.details.get("claimed_order_id")},
                discrepancies=discrepancies,
                findings=findings,
                evidence_refs=evidence_refs,
                timestamp=binding_outcome.verified_at,
            )

        if order is None:
            if state_machine_state == TransactionState.CREATED:
                return LifecycleStep(
                    sequence=4,
                    stage=LifecycleStage.ORDER,
                    status=StageIntegrityStatus.UNREACHED,
                    expected_context={},
                    observed_context={},
                    discrepancies=[],
                    findings=[],
                    evidence_refs=[],
                    timestamp=None,
                )
            missing_evidence.append("gateway_order")
            return LifecycleStep(
                sequence=4,
                stage=LifecycleStage.ORDER,
                status=StageIntegrityStatus.UNKNOWN,
                expected_context={"order": "gateway_order"},
                observed_context={},
                discrepancies=[],
                findings=["ORDER_RECORD_MISSING"],
                evidence_refs=[],
                timestamp=None,
            )

        order_amount_minor = order.amount.amount if hasattr(order.amount, "amount") else order.amount
        exp_ctx = cls._sanitize_dict({
            "order_id": order.order_id,
            "amount": order_amount_minor,
            "currency": order.currency,
            "notes": order.notes if hasattr(order, "notes") else {},
        })
        obs_ctx = cls._sanitize_dict(exp_ctx)

        # Verify order against intent
        if intent:
            if order.currency != intent.currency:
                discrepancies.append(
                    FieldDiscrepancy(
                        field_name="currency",
                        expected_value=intent.currency,
                        observed_value=order.currency,
                        description="Order currency does not match authorized intent currency",
                    )
                )
                findings.append("ORDER_CURRENCY_MISMATCH")

            if not intent.allow_partial and order_amount_minor > intent.max_total.amount:
                discrepancies.append(
                    FieldDiscrepancy(
                        field_name="amount",
                        expected_value=intent.max_total.amount,
                        observed_value=order_amount_minor,
                        description="Order amount exceeds maximum authorized total in intent",
                    )
                )
                findings.append("ORDER_AMOUNT_EXCEEDED")

        status = StageIntegrityStatus.DIVERGENCE_DETECTED if findings else StageIntegrityStatus.CONFIRMED_VALID

        return LifecycleStep(
            sequence=4,
            stage=LifecycleStage.ORDER,
            status=status,
            expected_context=exp_ctx,
            observed_context=obs_ctx,
            discrepancies=discrepancies,
            findings=findings,
            evidence_refs=evidence_refs,
            timestamp=getattr(order, "created_at", None),
        )

    @classmethod
    def _evaluate_attempt_stage(
        cls,
        binding_outcome: Optional[BindingVerificationOutcome],
        kill_switch_record: Optional[KillSwitchRecord],
        state_machine_state: Optional[TransactionState],
        evidence_ids: set,
        missing_evidence: List[str],
    ) -> LifecycleStep:
        discrepancies: List[FieldDiscrepancy] = []
        findings: List[str] = []
        evidence_refs = [eid for eid in evidence_ids if "attempt" in eid.lower()]

        # Check for attempt violations from I8 binding
        if binding_outcome:
            for v in [
                BindingViolationCode.ATTEMPT_MISMATCH,
                BindingViolationCode.DUPLICATE_ATTEMPT_REUSED,
                BindingViolationCode.CROSS_TRANSACTION_REUSE,
            ]:
                if v in binding_outcome.violations:
                    findings.append(v.value)
                    discrepancies.append(
                        FieldDiscrepancy(
                            field_name="attempt_token",
                            expected_value="single_use_valid_attempt",
                            observed_value=v.value,
                            description=f"Attempt verification failed with {v.value}",
                        )
                    )

        # Check for attempt limit exceeded from I9
        if kill_switch_record and kill_switch_record.trigger == KillTrigger.ATTEMPT_LIMIT_EXCEEDED:
            findings.append("ATTEMPT_LIMIT_EXCEEDED")
            discrepancies.append(
                FieldDiscrepancy(
                    field_name="attempt_count",
                    expected_value="<= max_retries",
                    observed_value="exceeded",
                    description="Checkout attempt count exceeded authorized maximum limit",
                )
            )

        if findings:
            return LifecycleStep(
                sequence=5,
                stage=LifecycleStage.ATTEMPT,
                status=StageIntegrityStatus.DIVERGENCE_DETECTED,
                expected_context={"attempt": "single_use_valid_attempt"},
                observed_context={"violations": findings},
                discrepancies=discrepancies,
                findings=findings,
                evidence_refs=evidence_refs,
                timestamp=kill_switch_record.timestamp if kill_switch_record else None,
            )

        if state_machine_state == TransactionState.CREATED:
            return LifecycleStep(
                sequence=5,
                stage=LifecycleStage.ATTEMPT,
                status=StageIntegrityStatus.UNREACHED,
                expected_context={},
                observed_context={},
                discrepancies=[],
                findings=[],
                evidence_refs=[],
                timestamp=None,
            )

        return LifecycleStep(
            sequence=5,
            stage=LifecycleStage.ATTEMPT,
            status=StageIntegrityStatus.CONFIRMED_VALID,
            expected_context={"attempt": "valid_single_use"},
            observed_context={"attempt": "valid_single_use"},
            discrepancies=[],
            findings=[],
            evidence_refs=evidence_refs,
            timestamp=None,
        )

    @classmethod
    def _evaluate_payment_stage(
        cls,
        intent: Optional[IntentContract],
        order: Optional[ProviderOrder],
        payment: Optional[ProviderPayment],
        integrity_result: Optional[IntegrityResult],
        binding_outcome: Optional[BindingVerificationOutcome],
        state_machine_state: Optional[TransactionState],
        evidence_ids: set,
        missing_evidence: List[str],
    ) -> LifecycleStep:
        discrepancies: List[FieldDiscrepancy] = []
        findings: List[str] = []
        evidence_refs = [eid for eid in evidence_ids if "payment" in eid.lower()]

        # Check I8 binding violations
        if binding_outcome:
            for v in [BindingViolationCode.PAYMENT_MISMATCH, BindingViolationCode.AMOUNT_NON_SUFFICIENCY]:
                if v in binding_outcome.violations:
                    findings.append(v.value)
                    discrepancies.append(
                        FieldDiscrepancy(
                            field_name="payment",
                            expected_value="bound_payment",
                            observed_value=v.value,
                            description=f"Payment binding failed: {v.value}",
                        )
                    )

        # Check T04 integrity drift
        if integrity_result and integrity_result.status == IntegrityStatus.DRIFT:
            for v in integrity_result.violations:
                code_str = (
                    v.code.value
                    if hasattr(v, "code") and hasattr(v.code, "value")
                    else (str(v.code) if hasattr(v, "code") else str(v))
                )
                desc = getattr(v, "message", str(v))
                findings.append(code_str)
                discrepancies.append(
                    FieldDiscrepancy(
                        field_name="payment_integrity",
                        expected_value=f"authorized_{intent.currency if intent else 'INR'}",
                        observed_value=code_str,
                        description=desc,
                    )
                )

        if findings:
            return LifecycleStep(
                sequence=6,
                stage=LifecycleStage.PAYMENT,
                status=StageIntegrityStatus.DIVERGENCE_DETECTED,
                expected_context={"payment": "bound_authorized_payment"},
                observed_context={"violations": findings},
                discrepancies=discrepancies,
                findings=findings,
                evidence_refs=evidence_refs,
                timestamp=binding_outcome.verified_at if binding_outcome else None,
            )

        if payment is None:
            if state_machine_state in (TransactionState.CREATED, TransactionState.EXECUTING):
                return LifecycleStep(
                    sequence=6,
                    stage=LifecycleStage.PAYMENT,
                    status=StageIntegrityStatus.UNREACHED,
                    expected_context={},
                    observed_context={},
                    discrepancies=[],
                    findings=[],
                    evidence_refs=[],
                    timestamp=None,
                )
            missing_evidence.append("payment_record")
            return LifecycleStep(
                sequence=6,
                stage=LifecycleStage.PAYMENT,
                status=StageIntegrityStatus.UNKNOWN,
                expected_context={"payment": "provider_payment"},
                observed_context={},
                discrepancies=[],
                findings=["PAYMENT_RECORD_MISSING"],
                evidence_refs=[],
                timestamp=None,
            )

        payment_amount_minor = payment.amount.amount if hasattr(payment.amount, "amount") else payment.amount
        exp_ctx = cls._sanitize_dict({
            "payment_id": payment.payment_id,
            "amount": payment_amount_minor,
            "currency": payment.currency,
            "status": payment.status,
            "notes": payment.notes if hasattr(payment, "notes") else {},
        })
        obs_ctx = cls._sanitize_dict(exp_ctx)

        # Check payment amount/currency drift directly against intent
        if intent:
            if payment.currency != intent.currency:
                discrepancies.append(
                    FieldDiscrepancy(
                        field_name="currency",
                        expected_value=intent.currency,
                        observed_value=payment.currency,
                        description="Payment currency does not match authorized intent currency",
                    )
                )
                if "PAYMENT_CURRENCY_MISMATCH" not in findings:
                    findings.append("PAYMENT_CURRENCY_MISMATCH")

            if payment_amount_minor > intent.max_total.amount:
                discrepancies.append(
                    FieldDiscrepancy(
                        field_name="amount",
                        expected_value=intent.max_total.amount,
                        observed_value=payment_amount_minor,
                        description="Payment amount exceeds authorized maximum total",
                    )
                )
                if "PAYMENT_AMOUNT_EXCEEDED" not in findings:
                    findings.append("PAYMENT_AMOUNT_EXCEEDED")

        # Check gateway reported payment failure regardless of intent presence
        if payment.status in ("failed", "rejected"):
            discrepancies.append(
                FieldDiscrepancy(
                    field_name="status",
                    expected_value="captured",
                    observed_value=payment.status,
                    description=f"Gateway payment failed with status '{payment.status}'",
                )
            )
            if "PAYMENT_FAILED" not in findings:
                findings.append("PAYMENT_FAILED")

        status = StageIntegrityStatus.DIVERGENCE_DETECTED if findings else StageIntegrityStatus.CONFIRMED_VALID

        return LifecycleStep(
            sequence=6,
            stage=LifecycleStage.PAYMENT,
            status=status,
            expected_context=exp_ctx,
            observed_context=obs_ctx,
            discrepancies=discrepancies,
            findings=findings,
            evidence_refs=evidence_refs,
            timestamp=getattr(payment, "created_at", None),
        )

    @classmethod
    def _evaluate_gateway_stage(
        cls,
        payment: Optional[ProviderPayment],
        events: Optional[List[CanonicalEvent]],
        binding_outcome: Optional[BindingVerificationOutcome],
        state_machine_state: Optional[TransactionState],
        evidence_ids: set,
        missing_evidence: List[str],
    ) -> LifecycleStep:
        discrepancies: List[FieldDiscrepancy] = []
        findings: List[str] = []
        evidence_refs = [eid for eid in evidence_ids if "gateway" in eid.lower() or "razorpay" in eid.lower()]

        sig_failed = False
        if events:
            for ev in events:
                payload_str = str(getattr(ev, "payload_summary", getattr(ev, "payload", ""))).lower()
                event_type = str(getattr(ev, "event_type", "")).lower()
                if "signature" in event_type and ("fail" in event_type or "invalid" in event_type):
                    sig_failed = True
                    break
                if "signature_verification_failed" in payload_str or "invalid_signature" in payload_str:
                    sig_failed = True
                    break

        if sig_failed:
            findings.append("SIGNATURE_VERIFICATION_FAILED")
            discrepancies.append(
                FieldDiscrepancy(
                    field_name="provider_signature",
                    expected_value="valid_hmac_sha256",
                    observed_value="[REDACTED_INVALID_SIGNATURE]",
                    description="Provider webhook or checkout signature failed cryptographic verification",
                )
            )
            return LifecycleStep(
                sequence=7,
                stage=LifecycleStage.GATEWAY,
                status=StageIntegrityStatus.DIVERGENCE_DETECTED,
                expected_context={"signature_status": "valid"},
                observed_context={"signature_status": "failed"},
                discrepancies=discrepancies,
                findings=findings,
                evidence_refs=evidence_refs,
                timestamp=None,
            )

        if binding_outcome and BindingViolationCode.UNRESOLVED_PROVIDER_STATE in binding_outcome.violations:
            return LifecycleStep(
                sequence=7,
                stage=LifecycleStage.GATEWAY,
                status=StageIntegrityStatus.UNKNOWN,
                expected_context={"provider_settlement": "settled"},
                observed_context={"provider_settlement": "unresolved"},
                discrepancies=[],
                findings=["UNRESOLVED_PROVIDER_STATE"],
                evidence_refs=evidence_refs,
                timestamp=binding_outcome.verified_at,
            )

        if payment is None and state_machine_state in (TransactionState.CREATED, TransactionState.EXECUTING):
            return LifecycleStep(
                sequence=7,
                stage=LifecycleStage.GATEWAY,
                status=StageIntegrityStatus.UNREACHED,
                expected_context={},
                observed_context={},
                discrepancies=[],
                findings=[],
                evidence_refs=[],
                timestamp=None,
            )

        return LifecycleStep(
            sequence=7,
            stage=LifecycleStage.GATEWAY,
            status=StageIntegrityStatus.CONFIRMED_VALID,
            expected_context={"signature_verification": "verified"},
            observed_context={"signature_verification": "verified"},
            discrepancies=[],
            findings=[],
            evidence_refs=evidence_refs,
            timestamp=None,
        )

    @classmethod
    def _evaluate_completion_stage(
        cls,
        steps: List[LifecycleStep],
        mrdp: Optional[MRDP],
        state_machine_state: Optional[TransactionState],
        integrity_result: Optional[IntegrityResult],
        evidence_ids: set,
        missing_evidence: List[str],
    ) -> LifecycleStep:
        discrepancies: List[FieldDiscrepancy] = []
        findings: List[str] = []
        evidence_refs = [eid for eid in evidence_ids if "mrdp" in eid.lower()]

        earlier_divergence = any(s.status == StageIntegrityStatus.DIVERGENCE_DETECTED for s in steps)

        if earlier_divergence:
            return LifecycleStep(
                sequence=8,
                stage=LifecycleStage.COMPLETION,
                status=StageIntegrityStatus.UNREACHED,
                expected_context={"terminal_state": "PASS"},
                observed_context={"terminal_state": state_machine_state.value if state_machine_state else "HALTED"},
                discrepancies=[],
                findings=[],
                evidence_refs=evidence_refs,
                timestamp=None,
            )

        if state_machine_state == TransactionState.PASS or (mrdp is not None and integrity_result and integrity_result.status == IntegrityStatus.PASS):
            return LifecycleStep(
                sequence=8,
                stage=LifecycleStage.COMPLETION,
                status=StageIntegrityStatus.CONFIRMED_VALID,
                expected_context={"outcome": "PASS"},
                observed_context={"outcome": "PASS", "mrdp_id": mrdp.mrdp_id if mrdp else None},
                discrepancies=[],
                findings=[],
                evidence_refs=evidence_refs,
                timestamp=mrdp.generated_at if mrdp else None,
            )

        if state_machine_state == TransactionState.UNKNOWN or (integrity_result and integrity_result.status == IntegrityStatus.UNKNOWN):
            return LifecycleStep(
                sequence=8,
                stage=LifecycleStage.COMPLETION,
                status=StageIntegrityStatus.UNKNOWN,
                expected_context={"outcome": "PASS"},
                observed_context={"outcome": "UNKNOWN"},
                discrepancies=[],
                findings=["TERMINAL_OUTCOME_UNKNOWN"],
                evidence_refs=evidence_refs,
                timestamp=None,
            )

        if state_machine_state in (TransactionState.CREATED, TransactionState.EXECUTING, TransactionState.OBSERVING, TransactionState.VERIFYING):
            return LifecycleStep(
                sequence=8,
                stage=LifecycleStage.COMPLETION,
                status=StageIntegrityStatus.UNREACHED,
                expected_context={},
                observed_context={},
                discrepancies=[],
                findings=[],
                evidence_refs=[],
                timestamp=None,
            )

        return LifecycleStep(
            sequence=8,
            stage=LifecycleStage.COMPLETION,
            status=StageIntegrityStatus.CONFIRMED_VALID,
            expected_context={"outcome": "PASS"},
            observed_context={"outcome": "PASS"},
            discrepancies=[],
            findings=[],
            evidence_refs=evidence_refs,
            timestamp=None,
        )

    # -------------------------------------------------------------------------
    # Helper & Redaction Methods
    # -------------------------------------------------------------------------

    @classmethod
    def _build_binding_snapshot(
        cls,
        transaction_id: str,
        intent: Optional[IntentContract],
        order: Optional[ProviderOrder],
        payment: Optional[ProviderPayment],
        binding_context: Optional[BindingContext],
        binding_outcome: Optional[BindingVerificationOutcome],
    ) -> ContextBindingSnapshot:
        intent_id = (
            binding_context.intent_id
            if binding_context
            else (intent.intent_id if intent else None)
        )
        agent_id = (
            binding_context.agent_id
            if binding_context
            else (intent.issued_by if intent else None)
        )
        merchant_id = (
            binding_context.merchant_id
            if binding_context
            else (getattr(order, "merchant_id", None) or (order.notes.get("merchant_id") if order and hasattr(order, "notes") else None))
        )
        order_id = (
            binding_context.order_id
            if binding_context
            else (order.order_id if order else None)
        )
        payment_id = (
            payment.payment_id
            if payment
            else (
                binding_outcome.details.get("payment_id")
                if binding_outcome and "payment_id" in binding_outcome.details
                else None
            )
        )
        attempt_id = binding_context.attempt_id if binding_context else "att_1"

        return ContextBindingSnapshot(
            transaction_id=transaction_id,
            intent_id=intent_id,
            agent_id=agent_id,
            merchant_id=merchant_id,
            order_id=order_id,
            payment_id=payment_id,
            attempt_id=attempt_id,
        )

    @classmethod
    def _map_component(cls, stage: LifecycleStage) -> str:
        mapping = {
            LifecycleStage.INTENT: "user_intent_contract",
            LifecycleStage.AGENT: "agent_identity_binding",
            LifecycleStage.MERCHANT: "merchant_catalog_adapter",
            LifecycleStage.ORDER: "gateway_order_service",
            LifecycleStage.ATTEMPT: "checkout_attempt_tracker",
            LifecycleStage.PAYMENT: "payment_capture_engine",
            LifecycleStage.GATEWAY: "provider_signature_verifier",
            LifecycleStage.COMPLETION: "mrdp_state_machine",
        }
        return mapping.get(stage, "tarkaraksha_core")

    @classmethod
    def _map_trigger_to_stage(cls, trigger: Optional[KillTrigger]) -> LifecycleStage:
        if not trigger:
            return LifecycleStage.COMPLETION
        mapping = {
            KillTrigger.EXPIRED_AUTHORIZATION: LifecycleStage.INTENT,
            KillTrigger.POLICY_VIOLATION: LifecycleStage.INTENT,
            KillTrigger.CAPABILITY_VIOLATION: LifecycleStage.AGENT,
            KillTrigger.BINDING_VIOLATION: LifecycleStage.ORDER,
            KillTrigger.ATTEMPT_LIMIT_EXCEEDED: LifecycleStage.ATTEMPT,
            KillTrigger.CRITICAL_DRIFT: LifecycleStage.PAYMENT,
            KillTrigger.REPEATED_UNKNOWN: LifecycleStage.GATEWAY,
            KillTrigger.ADMINISTRATIVE_KILL: LifecycleStage.COMPLETION,
            KillTrigger.ADMINISTRATIVE_PAUSE: LifecycleStage.COMPLETION,
        }
        return mapping.get(trigger, LifecycleStage.COMPLETION)

    @classmethod
    def _sanitize_dict(cls, d: Dict[str, Any]) -> Dict[str, Any]:
        return {k: cls._sanitize_value(v) for k, v in d.items()}

    @classmethod
    def _sanitize_value(cls, val: Any) -> Any:
        """Sanitizes raw values to prevent secret/credential leakage."""
        if isinstance(val, str):
            val = re.sub(
                r"(secret|token|api_key|password|signature|key)\s*=\s*[^\s,;]+",
                r"\1=[REDACTED]",
                val,
                flags=re.IGNORECASE,
            )
            val = re.sub(
                r"bearer\s+[a-zA-Z0-9_\-\.]{10,}",
                "Bearer [REDACTED]",
                val,
                flags=re.IGNORECASE,
            )
            return val
        elif isinstance(val, dict):
            clean = {}
            for k, v in val.items():
                k_lower = str(k).lower()
                if any(sec in k_lower for sec in ["secret", "api_key", "password", "token", "signature", "private_key"]):
                    clean[k] = "[REDACTED]"
                else:
                    clean[k] = cls._sanitize_value(v)
            return clean
        elif isinstance(val, list):
            return [cls._sanitize_value(item) for item in val]
        return val
