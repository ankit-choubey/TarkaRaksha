"""
Service implementation for E5 — Transaction Passport.

Composes existing authoritative transaction records into an immutable, read-only
TransactionPassport representation.

Invariants:
- "AI proposes. Evidence proves. Deterministic logic decides."
- Downstream & observational: zero state mutations, zero network or payment calls.
- Preserves evidence hierarchy: Authoritative Provider != Merchant Attested != Advisory Agent.
- UNKNOWN state preservation: UNKNOWN is never coerced to PASS.
- Payment separation: Payment CAPTURED != Transaction Integrity PASS.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.app.domain.integration.contracts import IntegrationExecutionRecord
from backend.app.domain.models import (
    Evidence,
    EvidenceAuthority,
    IntegrityResult,
    IntegrityStatus,
    IntentContract,
    MRDP,
    Money,
    ProviderOrder,
    ProviderPayment,
    TransactionState,
)
from backend.app.domain.orchestration.contracts import LifecycleOutcome
from backend.app.domain.passport.contracts import (
    PassportAgentContextSection,
    PassportAuthorizationSection,
    PassportCheckpointsAndTraceSection,
    PassportDriftSection,
    PassportEvidenceSection,
    PassportIdentitySection,
    PassportIntegritySection,
    PassportLifecycleStateSection,
    PassportMerchantContextSection,
    PassportPaymentSection,
    PassportRecoverySection,
    PassportReplaySection,
    PassportRevalidationSection,
    PassportSecuritySection,
    PassportSLAMetricsSection,
    PassportUnknownResolutionSection,
    TransactionPassport,
)
from backend.app.domain.states.machine import TransactionStateMachine


class TransactionPassportService:
    """
    Pure observational composition service for Transaction Passports.
    Aggregates authoritative records into a frozen Passport audit artifact.
    """

    def compose_passport(
        self,
        transaction_id: str,
        record: Optional[IntegrationExecutionRecord] = None,
        state_machine: Optional[TransactionStateMachine] = None,
        evidence_list: Optional[List[Evidence]] = None,
        lifecycle_outcome: Optional[LifecycleOutcome] = None,
        hero_record: Optional[Any] = None,
        reference_time: Optional[datetime] = None,
    ) -> TransactionPassport:
        """
        Deterministically builds a TransactionPassport from existing records.
        Zero state mutations or side-effects.
        """
        ref_time = reference_time or datetime.now(timezone.utc)
        if ref_time.tzinfo is None:
            ref_time = ref_time.replace(tzinfo=timezone.utc)

        ev_list = evidence_list if evidence_list is not None else []

        # ----------------------------------------------------------------------
        # A. Identity Section
        # ----------------------------------------------------------------------
        intent_id = ""
        agent_ids: List[str] = []
        merchant_id = ""
        order_id: Optional[str] = None
        payment_id: Optional[str] = None
        attempt_id: Optional[str] = None
        binding_verified = False
        binding_details: Dict[str, Any] = {}

        if record:
            intent_id = record.context.intent_id
            if record.context.agent_id and record.context.agent_id not in agent_ids:
                agent_ids.append(record.context.agent_id)
            if record.buyer_proposal and record.buyer_proposal.buyer_agent_id not in agent_ids:
                agent_ids.append(record.buyer_proposal.buyer_agent_id)
            merchant_id = record.context.merchant_id
            order_id = record.context.order_id or (record.order.order_id if record.order else None)
            payment_id = record.context.payment_id or (record.payment.payment_id if record.payment else None)
            attempt_id = record.context.attempt_id
            if record.binding_outcome:
                binding_verified = record.binding_outcome.is_valid
                binding_details = record.binding_outcome.model_dump()
        elif lifecycle_outcome:
            intent_id = lifecycle_outcome.intent_id
            agent_ids = [lifecycle_outcome.agent_id]
            merchant_id = lifecycle_outcome.merchant_id
            order_id = lifecycle_outcome.order_id
            payment_id = lifecycle_outcome.payment_id

        identity_sec = PassportIdentitySection(
            transaction_id=transaction_id,
            intent_id=intent_id or f"intent_{transaction_id}",
            agent_ids=agent_ids or ["unknown_agent"],
            merchant_id=merchant_id or "unknown_merchant",
            order_id=order_id,
            payment_id=payment_id,
            attempt_id=attempt_id or "att_1",
            binding_verified=binding_verified,
            binding_details=binding_details,
        )

        # ----------------------------------------------------------------------
        # B. Authorization Section
        # ----------------------------------------------------------------------
        intent: Optional[IntentContract] = record.intent if record else None
        if not intent and hero_record and hasattr(hero_record, "intent"):
            intent = hero_record.intent

        if intent:
            auth_items = [
                {
                    "item_id": item.item_id,
                    "sku": item.sku,
                    "name": item.name,
                    "quantity": item.quantity,
                    "unit_price": item.unit_price.model_dump(),
                    "total_price": item.total_price.model_dump(),
                }
                for item in intent.items
            ]
            auth_sec = PassportAuthorizationSection(
                intent_id=intent.intent_id,
                issued_by=intent.issued_by,
                issued_at=intent.issued_at,
                expires_at=intent.expires_at,
                max_total=intent.max_total,
                currency=intent.currency,
                authorized_items=auth_items,
                allowed_substitutions=list(intent.allowed_substitutions),
                policy_version=intent.policy_version,
                contract_version=intent.contract_version,
                constraints_summary={
                    "max_total": intent.max_total.model_dump(),
                    "currency": intent.currency,
                    "sku_count": len(intent.items),
                    "substitutions_count": len(intent.allowed_substitutions),
                },
            )
        else:
            auth_sec = PassportAuthorizationSection(
                intent_id=identity_sec.intent_id,
                issued_by="unknown_issuer",
                issued_at=ref_time,
                expires_at=ref_time,
                max_total=Money(amount=0, currency="INR"),
                currency="INR",
                authorized_items=[],
                allowed_substitutions=[],
                policy_version="1.0.0",
                contract_version="1.0.0",
                constraints_summary={"status": "NO_INTENT_RECORDED"},
            )

        # ----------------------------------------------------------------------
        # C. Agent Context Section
        # ----------------------------------------------------------------------
        buyer_agent_id = identity_sec.agent_ids[0] if identity_sec.agent_ids else "agent_buyer_default"
        prop_id = None
        prop_sku = None
        prop_qty = None
        prop_max = None
        prop_rat = None
        cg_status = None
        cg_findings: List[Dict[str, Any]] = []

        if record and record.buyer_proposal:
            prop_id = record.buyer_proposal.proposal_id
            prop_sku = record.buyer_proposal.sku
            prop_qty = record.buyer_proposal.quantity
            prop_max = record.buyer_proposal.max_total
            prop_rat = record.buyer_proposal.rationale

        if record and record.consumer_gate_result:
            cg_status = record.consumer_gate_result.status.value
            cg_findings = [f.model_dump() for f in record.consumer_gate_result.findings]

        agent_history = [
            h for h in (record.history if record else [])
            if any(k in h.lower() for k in ["buyer", "agent", "proposal", "consumer_gate"])
        ]

        agent_sec = PassportAgentContextSection(
            buyer_agent_id=buyer_agent_id,
            proposal_id=prop_id,
            proposed_sku=prop_sku,
            proposed_quantity=prop_qty,
            proposed_max_total=prop_max,
            proposal_rationale=prop_rat,
            consumer_gate_status=cg_status,
            consumer_gate_findings=cg_findings,
            agent_lifecycle_events=agent_history,
        )

        # ----------------------------------------------------------------------
        # D. Merchant Context Section
        # ----------------------------------------------------------------------
        merchant_name = None
        off_id = None
        off_items: List[Dict[str, Any]] = []
        off_subtotal = None
        off_shipping = None
        off_total = None
        inv_status = None
        mg_status = None
        mg_findings: List[Dict[str, Any]] = []
        capabilities: List[str] = []

        if record and record.merchant_response:
            resp = record.merchant_response
            off_id = resp.offer_id or resp.response_id
            off_items = [
                {
                    "sku": item.sku,
                    "title": item.title,
                    "quantity": item.quantity,
                    "unit_price": item.unit_price.model_dump(),
                    "total_price": item.total_price.model_dump(),
                }
                for item in resp.items
            ]
            off_subtotal = resp.subtotal
            off_shipping = resp.shipping.cost if resp.shipping else None
            off_total = resp.total
            inv_status = resp.inventory_status.value

        if record and record.merchant_gate_result:
            mg_status = record.merchant_gate_result.status.value
            mg_findings = [f.model_dump() for f in record.merchant_gate_result.findings]

        merchant_sec = PassportMerchantContextSection(
            merchant_id=identity_sec.merchant_id,
            merchant_name=merchant_name,
            offer_id=off_id,
            offered_items=off_items,
            offered_subtotal=off_subtotal,
            offered_shipping=off_shipping,
            offered_total=off_total,
            inventory_status=inv_status,
            capabilities=capabilities,
            merchant_gate_status=mg_status,
            merchant_gate_findings=mg_findings,
        )

        # ----------------------------------------------------------------------
        # E. Lifecycle State Section (T05 Projection)
        # ----------------------------------------------------------------------
        current_state = TransactionState.CREATED
        transitions: List[Dict[str, Any]] = []
        attempt_count = 1

        if state_machine:
            current_state = state_machine.current_state
            transitions = [
                t.model_dump() if hasattr(t, "model_dump") else dict(t)
                for t in state_machine.history
            ]
            attempt_count = getattr(state_machine, "attempt_count", len(state_machine.history) if state_machine.history else 1)
        elif lifecycle_outcome:
            current_state = lifecycle_outcome.transaction_state
        elif record and record.integrity_result:
            if record.integrity_result.status == IntegrityStatus.PASS:
                current_state = TransactionState.PASS
            elif record.integrity_result.status == IntegrityStatus.DRIFT:
                current_state = TransactionState.DRIFT
            else:
                current_state = TransactionState.UNKNOWN

        terminal_states = {
            TransactionState.PASS,
            TransactionState.DRIFT,
            TransactionState.UNKNOWN,
            TransactionState.ABSTAIN,
        }
        is_terminal = current_state in terminal_states or (
            lifecycle_outcome.is_terminal if lifecycle_outcome else False
        )

        lifecycle_sec = PassportLifecycleStateSection(
            current_state=current_state,
            state_transitions=transitions,
            attempt_count=attempt_count,
            created_at=record.created_at if record else ref_time,
            updated_at=record.updated_at if record else ref_time,
            is_terminal=is_terminal,
        )

        # ----------------------------------------------------------------------
        # F. Integrity Section (T04 Projection)
        # ----------------------------------------------------------------------
        integ_status = IntegrityStatus.UNKNOWN
        rule_results: Dict[str, bool] = {}
        violations: List[str] = []
        eval_time = None

        if record and record.integrity_result:
            integ_status = record.integrity_result.status
            rule_results = record.integrity_result.rule_results
            violations = list(record.integrity_result.violations)
        elif lifecycle_outcome and lifecycle_outcome.integrity_status:
            integ_status = lifecycle_outcome.integrity_status
        elif current_state == TransactionState.PASS:
            integ_status = IntegrityStatus.PASS
        elif current_state == TransactionState.DRIFT:
            integ_status = IntegrityStatus.DRIFT

        # Classify violations into domains
        economic_findings: Dict[str, Any] = {}
        semantic_findings: Dict[str, Any] = {}
        temporal_findings: Dict[str, Any] = {}
        for v in violations:
            vl = v.lower()
            if any(k in vl for k in ["amount", "price", "currency", "total", "economic"]):
                economic_findings[v] = False
            elif any(k in vl for k in ["sku", "item", "quantity", "semantic", "merchant"]):
                semantic_findings[v] = False
            elif any(k in vl for k in ["time", "expired", "temporal", "clock"]):
                temporal_findings[v] = False
            else:
                semantic_findings[v] = False

        integrity_sec = PassportIntegritySection(
            status=integ_status,
            rules_version="1.0.0",
            economic_findings=economic_findings,
            semantic_findings=semantic_findings,
            temporal_findings=temporal_findings,
            rule_results=rule_results,
            violations=violations,
            evaluated_at=eval_time,
        )

        # ----------------------------------------------------------------------
        # G. Drift / MRDP Section (T07 Projection)
        # ----------------------------------------------------------------------
        has_drift = bool(integ_status == IntegrityStatus.DRIFT or (record is not None and record.mrdp is not None))
        mrdp_obj = record.mrdp if record else None
        mrdp_id = mrdp_obj.mrdp_id if mrdp_obj else (lifecycle_outcome.mrdp_id if lifecycle_outcome else None)
        mrdp_digest = mrdp_obj.proof_digest if mrdp_obj else None
        disc_amount = mrdp_obj.discrepancy_amount if mrdp_obj else None
        disc_details = {
            "expected_value": mrdp_obj.expected_value,
            "observed_value": mrdp_obj.observed_value,
            "error_code": mrdp_obj.error_code,
            "drift_source": mrdp_obj.drift_source,
        } if mrdp_obj else {}
        violated_rules = [mrdp_obj.violation] if mrdp_obj and mrdp_obj.violation else violations
        mrdp_summary = getattr(mrdp_obj, "explanation", mrdp_obj.violation if mrdp_obj else None) or ("Authoritative DRIFT detected" if has_drift else None)

        drift_sec = PassportDriftSection(
            has_drift=has_drift,
            drift_detected_at=mrdp_obj.generated_at if mrdp_obj else None,
            mrdp_id=mrdp_id,
            mrdp_digest=mrdp_digest,
            discrepancy_amount=disc_amount,
            discrepancy_details=disc_details,
            violated_rules=violated_rules,
            mrdp_summary=mrdp_summary,
        )

        # ----------------------------------------------------------------------
        # H. Evidence Section (T06 Projection)
        # ----------------------------------------------------------------------
        ev_records: List[Dict[str, Any]] = []
        auth_dist: Dict[str, int] = {
            EvidenceAuthority.AUTHORITATIVE.value: 0,
            EvidenceAuthority.MERCHANT_ATTESTED.value: 0,
            EvidenceAuthority.ADVISORY.value: 0,
        }

        for ev in ev_list:
            auth_val = ev.authority.value if hasattr(ev.authority, "value") else str(ev.authority)
            auth_dist[auth_val] = auth_dist.get(auth_val, 0) + 1
            ev_records.append(
                {
                    "evidence_id": ev.evidence_id,
                    "source": ev.source.value if hasattr(ev.source, "value") else str(ev.source),
                    "authority": auth_val,
                    "field_name": ev.field_name,
                    "field_value": str(ev.field_value),
                    "observed_at": ev.observed_at.isoformat(),
                    "provenance": ev.provenance,
                }
            )

        evidence_sec = PassportEvidenceSection(
            total_evidence_count=len(ev_records),
            evidence_records=ev_records,
            authority_distribution=auth_dist,
        )

        # ----------------------------------------------------------------------
        # I. Security Section (E4 Projection)
        # ----------------------------------------------------------------------
        sec_checked = False
        threat_status = "NOT_EVALUATED"
        threats: List[str] = []
        pi_detected = False
        cap_abuse = False
        rep_attack = False
        ev_tamper = False
        kill_state = None

        if record and record.security_guard_result:
            sec_checked = True
            res = record.security_guard_result
            threat_status = getattr(res, "status", "CLEAR")
            threats = getattr(res, "threats", [])
            pi_detected = any("prompt_injection" in t.lower() for t in threats)
            cap_abuse = any("capability" in t.lower() for t in threats)
            rep_attack = any("replay" in t.lower() for t in threats)
            ev_tamper = any("tamper" in t.lower() for t in threats)
        elif lifecycle_outcome and lifecycle_outcome.security_cleared:
            sec_checked = True
            threat_status = "CLEAR"

        security_sec = PassportSecuritySection(
            security_checked=sec_checked,
            threat_status=threat_status,
            threats_detected=threats,
            prompt_injection_detected=pi_detected,
            capability_abuse_detected=cap_abuse,
            replay_attack_detected=rep_attack,
            evidence_tampering_detected=ev_tamper,
            kill_switch_state=kill_state,
        )

        # ----------------------------------------------------------------------
        # J. Recovery Section (T11 Projection)
        # ----------------------------------------------------------------------
        rec_invoked = False
        rec_attempts = 0
        rec_act_type = None
        rec_act_amount = None
        rec_target = None
        rec_status = None
        rec_res_dict = None

        if record and record.recovery_result:
            rec_invoked = True
            res = record.recovery_result
            rec_attempts = getattr(res, "attempt_number", 1)
            act_req = getattr(res, "action_request", None)
            rec_act_type = act_req.action_type.value if (act_req and hasattr(act_req, "action_type")) else getattr(res, "action_type", None)
            rec_act_amount = act_req.amount if (act_req and hasattr(act_req, "amount")) else getattr(res, "amount", None)
            rec_target = act_req.target_reference if (act_req and hasattr(act_req, "target_reference")) else getattr(res, "target_reference", None)
            rec_status = str(getattr(res, "status", "SUCCESS"))
            rec_res_dict = res.model_dump() if hasattr(res, "model_dump") else dict(res)

        recovery_sec = PassportRecoverySection(
            recovery_invoked=rec_invoked,
            recovery_attempts=rec_attempts,
            action_type=rec_act_type,
            action_amount=rec_act_amount,
            target_reference=rec_target,
            recovery_status=rec_status,
            recovery_result=rec_res_dict,
        )

        # ----------------------------------------------------------------------
        # K. Unknown Resolution Section (T12 Projection)
        # ----------------------------------------------------------------------
        unk_encountered = (
            integ_status == IntegrityStatus.UNKNOWN
            or current_state in (TransactionState.UNKNOWN, TransactionState.RESOLVING, TransactionState.ABSTAIN)
        )
        unk_reason = None
        res_attempts = 0
        res_outcome = None
        final_unresolved = False

        if record and record.resolution_result:
            r = record.resolution_result
            res_attempts = getattr(r, "attempts", 1)
            res_outcome = getattr(r, "outcome", "RESOLVED")
            unk_reason = getattr(r, "reason", "Ambiguous provider telemetry")

        if lifecycle_outcome:
            res_attempts = max(res_attempts, lifecycle_outcome.resolution_attempts)

        if current_state == TransactionState.ABSTAIN and integ_status == IntegrityStatus.UNKNOWN:
            final_unresolved = True
            res_outcome = "ABSTAINED"

        unknown_sec = PassportUnknownResolutionSection(
            unknown_encountered=unk_encountered,
            unknown_reason=unk_reason,
            resolution_attempts=res_attempts,
            resolution_outcome=res_outcome,
            final_unresolved=final_unresolved,
        )

        # ----------------------------------------------------------------------
        # L. Revalidation Section (E3 / I7 Projection)
        # ----------------------------------------------------------------------
        reval_invoked = False
        replan_rounds = 0
        revised_prop_present = False
        revised_off_present = False
        rev_cg_status = None
        rev_mg_status = None
        rev_integ_status = None

        if lifecycle_outcome and lifecycle_outcome.replan_rounds > 0:
            reval_invoked = True
            replan_rounds = lifecycle_outcome.replan_rounds
            revised_prop_present = True
            revised_off_present = True
            rev_cg_status = "VALID"
            rev_mg_status = "VALID"
            rev_integ_status = lifecycle_outcome.integrity_status.value if lifecycle_outcome.integrity_status else None
        elif record and record.negotiation_session:
            reval_invoked = True
            replan_rounds = getattr(record.negotiation_session, "rounds", 1)

        revalidation_sec = PassportRevalidationSection(
            revalidation_invoked=reval_invoked,
            replan_rounds=replan_rounds,
            revised_proposal_present=revised_prop_present,
            revised_offer_present=revised_off_present,
            revised_consumer_gate_status=rev_cg_status,
            revised_merchant_gate_status=rev_mg_status,
            revalidation_integrity_status=rev_integ_status,
        )

        # ----------------------------------------------------------------------
        # M. Checkpoints and Trace Section (I14 & I13 Projection)
        # ----------------------------------------------------------------------
        chk_count = 0
        chk_valid = None
        chk_fp = None
        tr_stages = 0
        div_stage = None
        root_cause = None

        if hero_record:
            if hasattr(hero_record, "checkpoint_timeline") and hero_record.checkpoint_timeline:
                tl = hero_record.checkpoint_timeline
                chk_count = len(tl.checkpoints)
                chk_valid = tl.is_valid
                chk_fp = tl.timeline_fingerprint
            if hasattr(hero_record, "trace") and hero_record.trace:
                tr = hero_record.trace
                tr_stages = len(tr.stages)
                div_stage = tr.first_divergence_stage.value if tr.first_divergence_stage else None
                root_cause = tr.root_cause

        checkpoints_trace_sec = PassportCheckpointsAndTraceSection(
            checkpoint_count=chk_count,
            checkpoint_timeline_valid=chk_valid,
            checkpoint_fingerprint=chk_fp,
            trace_stages_evaluated=tr_stages,
            divergence_stage=div_stage,
            trace_root_cause=root_cause,
        )

        # ----------------------------------------------------------------------
        # N. SLA Metrics Section (I15 Projection)
        # ----------------------------------------------------------------------
        sla_avail = False
        t_detect = None
        t_prove = None
        t_reval = None
        t_total = None

        if hero_record and hasattr(hero_record, "sla_report") and hero_record.sla_report:
            rep = hero_record.sla_report
            sla_avail = True
            t_detect = rep.metrics.get("TIME_TO_DETECT").duration_ms if "TIME_TO_DETECT" in rep.metrics else None
            t_prove = rep.metrics.get("TIME_TO_PROVE").duration_ms if "TIME_TO_PROVE" in rep.metrics else None
            t_reval = rep.metrics.get("TIME_TO_REVALIDATE").duration_ms if "TIME_TO_REVALIDATE" in rep.metrics else None
            t_total = rep.metrics.get("TIME_TO_FINAL_DECISION").duration_ms if "TIME_TO_FINAL_DECISION" in rep.metrics else None

        sla_sec = PassportSLAMetricsSection(
            sla_available=sla_avail,
            time_to_detect_ms=t_detect,
            time_to_prove_ms=t_prove,
            time_to_revalidate_ms=t_reval,
            total_lifecycle_duration_ms=t_total,
        )

        # ----------------------------------------------------------------------
        # O. Payment Section (T09 Projection - CAPTURED != PASS)
        # ----------------------------------------------------------------------
        pay_order_id = identity_sec.order_id
        pay_payment_id = identity_sec.payment_id
        pay_status = None
        pay_amount = None
        pay_method = None
        pay_captured = False

        if record and record.payment:
            pay_status = record.payment.status
            pay_amount = record.payment.amount
            pay_method = record.payment.method
            pay_captured = record.payment.status == "captured"
        elif hero_record and hasattr(hero_record, "payment_result") and hero_record.payment_result:
            p = hero_record.payment_result
            pay_status = p.status
            pay_amount = p.amount
            pay_method = p.method
            pay_captured = p.status == "captured"

        payment_sec = PassportPaymentSection(
            provider="RAZORPAY",
            payment_id=pay_payment_id,
            order_id=pay_order_id,
            payment_status=pay_status,
            amount=pay_amount,
            method=pay_method,
            payment_captured=pay_captured,
            integrity_status_distinction="payment_state != integrity_state (CAPTURED != PASS)",
        )

        # ----------------------------------------------------------------------
        # P. Replay Section (T13 Projection)
        # ----------------------------------------------------------------------
        rep_avail = False
        rep_verdict = None
        rep_state = None
        rep_disc_count = 0

        if record and record.replay_result:
            rep_avail = True
            r = record.replay_result
            rep_verdict = r.verdict.value if hasattr(r.verdict, "value") else str(r.verdict)
            rep_state = r.replayed_state.value if hasattr(r.replayed_state, "value") else str(r.replayed_state)
            rep_disc_count = len(getattr(r, "discrepancies", []))

        replay_sec = PassportReplaySection(
            replay_available=rep_avail,
            replay_verdict=rep_verdict,
            replayed_state=rep_state,
            is_cpu_only=True,
            discrepancy_count=rep_disc_count,
        )

        # ----------------------------------------------------------------------
        # Final Proven & Digest
        # ----------------------------------------------------------------------
        final_outcome_str = integ_status.value
        if current_state == TransactionState.ABSTAIN:
            final_outcome_str = "ABSTAIN"

        if final_outcome_str == "PASS":
            final_proven = "PASS: Deterministic verification confirmed economic, semantic, and temporal integrity bounds."
        elif final_outcome_str == "DRIFT":
            final_proven = f"DRIFT: Discrepancy detected and bound to cryptographic MRDP proof ({mrdp_id or 'proven'})."
        elif final_outcome_str == "ABSTAIN":
            final_proven = "ABSTAIN: Ambiguous or unresolvable evidence safely escalated without coercing PASS."
        else:
            final_proven = "UNKNOWN: Authoritative provider evidence absent, delayed, or conflicting."

        passport = TransactionPassport(
            passport_id=f"passport_{transaction_id}",
            transaction_id=transaction_id,
            final_outcome=final_outcome_str,
            final_proven=final_proven,
            generated_at=ref_time,
            identity=identity_sec,
            authorization=auth_sec,
            agent_context=agent_sec,
            merchant_context=merchant_sec,
            lifecycle_state=lifecycle_sec,
            integrity=integrity_sec,
            drift=drift_sec,
            evidence=evidence_sec,
            security=security_sec,
            recovery=recovery_sec,
            unknown_resolution=unknown_sec,
            revalidation=revalidation_sec,
            checkpoints_trace=checkpoints_trace_sec,
            sla_metrics=sla_sec,
            payment=payment_sec,
            replay=replay_sec,
        )

        digest = passport.compute_digest()
        return passport.model_copy(update={"passport_digest": digest})
