"""Deterministic calculation engine for Innovation I15 — Integrity SLA Metrics.

Consumes authoritative outputs from:
- T04 Deterministic Integrity Engine (IntegrityResult)
- I13 Integrity Trace & Fault Localization (IntegrityTrace)
- I14 Integrity Checkpoints (IntegrityCheckpointTimeline)
- I8 Binding (BindingVerificationOutcome)
- I9 Kill Switch (KillSwitchRecord)
- Transaction lifecycle events and timestamps.

Core Invariant:
AI proposes -> evidence proves -> deterministic logic decides.
Pure deterministic measurement. Zero LLM authority. Zero wall-clock now() fabrication.
"""
from datetime import datetime, timezone
import re
from typing import Any, Dict, List, Optional

from backend.app.domain.models.enums import IntegrityStatus
from backend.app.domain.models.intent import IntentContract
from backend.app.domain.models.payment import ProviderOrder, ProviderPayment
from backend.app.domain.models.integrity import IntegrityResult
from backend.app.domain.models.evidence import CanonicalEvent
from backend.app.domain.binding.contracts import BindingVerificationOutcome
from backend.app.domain.kill_switch.contracts import KillSwitchRecord, KillSwitchState
from backend.app.domain.trace.contracts import IntegrityTrace, StageIntegrityStatus
from backend.app.domain.checkpoint.contracts import (
    IntegrityCheckpointTimeline,
    CheckpointStatus,
)
from backend.app.domain.sla.contracts import (
    MetricStatus,
    MetricUnit,
    MetricName,
    SLAPolicy,
    SLAMetric,
    SLAComplianceSummary,
    IntegritySLAMetricsReport,
)

# Sensitive credential patterns for redaction
SECRET_KEY_PATTERN = re.compile(r"(key|secret|token|auth|password|signature|bearer)", re.IGNORECASE)


def _sanitize_details(val: Any) -> Any:
    """Recursively redacts sensitive keys and values from detail dictionaries."""
    if isinstance(val, dict):
        sanitized = {}
        for k, v in val.items():
            if SECRET_KEY_PATTERN.search(k):
                sanitized[k] = "[REDACTED]"
            else:
                sanitized[k] = _sanitize_details(v)
        return sanitized
    if isinstance(val, list):
        return [_sanitize_details(item) for item in val]
    return val


class DeterministicSLAEngine:
    """
    Pure deterministic calculation engine for transaction integrity SLA metrics.
    Does not invent timestamps, does not mutate decisions, does not use LLM.
    """

    @classmethod
    def compute_report(
        cls,
        transaction_id: str,
        policy: Optional[SLAPolicy] = None,
        intent: Optional[IntentContract] = None,
        order: Optional[ProviderOrder] = None,
        payment: Optional[ProviderPayment] = None,
        integrity_result: Optional[IntegrityResult] = None,
        integrity_trace: Optional[IntegrityTrace] = None,
        checkpoint_timeline: Optional[IntegrityCheckpointTimeline] = None,
        binding_outcome: Optional[BindingVerificationOutcome] = None,
        kill_switch_record: Optional[KillSwitchRecord] = None,
        events: Optional[List[CanonicalEvent]] = None,
        created_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        reference_time: Optional[datetime] = None,
        reproducibility_reference: Optional[str] = None,
    ) -> IntegritySLAMetricsReport:
        """
        Computes an immutable, deterministic IntegritySLAMetricsReport.
        """
        pol = policy or SLAPolicy()
        gen_time = reference_time or datetime.now(timezone.utc)
        if gen_time.tzinfo is None:
            gen_time = gen_time.replace(tzinfo=timezone.utc)

        ev_list = events or []

        metrics: List[SLAMetric] = []

        # 1. TIME_TO_DETECT
        m_detect = cls._compute_time_to_detect(
            transaction_id=transaction_id,
            policy=pol,
            integrity_result=integrity_result,
            integrity_trace=integrity_trace,
            created_at=created_at,
            events=ev_list,
        )
        metrics.append(m_detect)

        # 2. TIME_TO_PROVE
        m_prove = cls._compute_time_to_prove(
            transaction_id=transaction_id,
            policy=pol,
            integrity_result=integrity_result,
            integrity_trace=integrity_trace,
            events=ev_list,
            completed_at=completed_at,
        )
        metrics.append(m_prove)

        # 3. TIME_TO_INTERVENE
        m_intervene = cls._compute_time_to_intervene(
            transaction_id=transaction_id,
            policy=pol,
            integrity_result=integrity_result,
            integrity_trace=integrity_trace,
            kill_switch_record=kill_switch_record,
            events=ev_list,
        )
        metrics.append(m_intervene)

        # 4. TIME_TO_REVALIDATE
        m_reval = cls._compute_time_to_revalidate(
            transaction_id=transaction_id,
            policy=pol,
            kill_switch_record=kill_switch_record,
            events=ev_list,
            reference_time=gen_time,
        )
        metrics.append(m_reval)

        # 5. TIME_TO_FINAL_DECISION
        m_final = cls._compute_time_to_final_decision(
            transaction_id=transaction_id,
            policy=pol,
            created_at=created_at,
            completed_at=completed_at,
            integrity_result=integrity_result,
            intent=intent,
            events=ev_list,
        )
        metrics.append(m_final)

        # 6. UNKNOWN_EXPOSURE_DURATION
        m_unknown = cls._compute_unknown_duration(
            transaction_id=transaction_id,
            policy=pol,
            integrity_result=integrity_result,
            integrity_trace=integrity_trace,
            checkpoint_timeline=checkpoint_timeline,
            events=ev_list,
            reference_time=gen_time,
        )
        metrics.append(m_unknown)

        # 7. CHECKPOINT_COVERAGE_RATIO
        m_cp_cov = cls._compute_checkpoint_coverage(
            transaction_id=transaction_id,
            policy=pol,
            checkpoint_timeline=checkpoint_timeline,
        )
        metrics.append(m_cp_cov)

        # 8. CHECKPOINT_VALID_RATIO
        m_cp_val = cls._compute_checkpoint_valid_ratio(
            transaction_id=transaction_id,
            policy=pol,
            checkpoint_timeline=checkpoint_timeline,
        )
        metrics.append(m_cp_val)

        # 9. TRACE_COMPLETENESS_RATIO
        m_trace_comp = cls._compute_trace_completeness(
            transaction_id=transaction_id,
            policy=pol,
            integrity_trace=integrity_trace,
        )
        metrics.append(m_trace_comp)

        # Compute summary
        summary = cls._compute_summary(metrics)

        report_id = f"sla_rep_{transaction_id}"
        return IntegritySLAMetricsReport(
            report_id=report_id,
            transaction_id=transaction_id,
            metrics=metrics,
            summary=summary,
            policy=pol,
            governance_version=pol.governance_version,
            reproducibility_reference=reproducibility_reference,
            generated_at=gen_time,
        )

    # -------------------------------------------------------------------------
    # Individual Metric Calculators
    # -------------------------------------------------------------------------

    @classmethod
    def _compute_time_to_detect(
        cls,
        transaction_id: str,
        policy: SLAPolicy,
        integrity_result: Optional[IntegrityResult],
        integrity_trace: Optional[IntegrityTrace],
        created_at: Optional[datetime],
        events: List[CanonicalEvent],
    ) -> SLAMetric:
        # Check if divergence occurred
        is_divergent = False
        if integrity_result and integrity_result.status == IntegrityStatus.DRIFT:
            is_divergent = True
        elif integrity_trace and integrity_trace.first_divergence:
            is_divergent = True

        if not is_divergent:
            # Clean transaction or not evaluated to drift
            if integrity_result and integrity_result.status == IntegrityStatus.PASS:
                return SLAMetric(
                    metric_name=MetricName.TIME_TO_DETECT,
                    metric_definition_version=policy.governance_version,
                    transaction_id=transaction_id,
                    status=MetricStatus.NOT_APPLICABLE,
                    value=None,
                    unit=MetricUnit.MILLISECONDS,
                    threshold=policy.max_time_to_detect_ms,
                    is_compliant=True,
                    calculation_reason="No divergence or drift occurred in this transaction lifecycle",
                    details={"integrity_status": integrity_result.status.value},
                )
            if not integrity_result and not integrity_trace:
                return SLAMetric(
                    metric_name=MetricName.TIME_TO_DETECT,
                    metric_definition_version=policy.governance_version,
                    transaction_id=transaction_id,
                    status=MetricStatus.UNKNOWN,
                    value=None,
                    unit=MetricUnit.MILLISECONDS,
                    threshold=policy.max_time_to_detect_ms,
                    is_compliant=None,
                    calculation_reason="No integrity evaluation or trace available to measure detection time",
                )

        # Resolve detection time
        detected_at: Optional[datetime] = None
        det_ref = "integrity_result"
        if integrity_trace and integrity_trace.first_divergence and integrity_trace.first_divergence.detected_at:
            detected_at = integrity_trace.first_divergence.detected_at
            det_ref = "first_divergence.detected_at"
        elif integrity_result and integrity_result.evaluated_at:
            detected_at = integrity_result.evaluated_at
            det_ref = "integrity_result.evaluated_at"

        # Resolve triggering event time
        trigger_at: Optional[datetime] = None
        trig_ref = "trigger_event"
        if integrity_trace and integrity_trace.first_divergence:
            step_seq = integrity_trace.first_divergence.step_sequence
            for s in integrity_trace.steps:
                if s.sequence == step_seq and s.timestamp:
                    trigger_at = s.timestamp
                    trig_ref = f"lifecycle_step_{step_seq}"
                    break

        if trigger_at is None:
            # Fall back to transaction created_at
            if created_at:
                trigger_at = created_at
                trig_ref = "transaction_created_at"
            elif events:
                sorted_evs = sorted([e for e in events if e.timestamp], key=lambda e: e.timestamp)
                if sorted_evs:
                    trigger_at = sorted_evs[0].timestamp
                    trig_ref = f"event_{sorted_evs[0].event_id}"

        if detected_at is None or trigger_at is None:
            return SLAMetric(
                metric_name=MetricName.TIME_TO_DETECT,
                metric_definition_version=policy.governance_version,
                transaction_id=transaction_id,
                status=MetricStatus.UNKNOWN,
                value=None,
                unit=MetricUnit.MILLISECONDS,
                threshold=policy.max_time_to_detect_ms,
                is_compliant=None,
                start_time=trigger_at,
                end_time=detected_at,
                start_evidence_ref=trig_ref if trigger_at else None,
                end_evidence_ref=det_ref if detected_at else None,
                calculation_reason="Missing authoritative timestamp for divergence trigger or detection",
            )

        if detected_at < trigger_at:
            return SLAMetric(
                metric_name=MetricName.TIME_TO_DETECT,
                metric_definition_version=policy.governance_version,
                transaction_id=transaction_id,
                status=MetricStatus.INVALID,
                value=None,
                unit=MetricUnit.MILLISECONDS,
                threshold=policy.max_time_to_detect_ms,
                is_compliant=False,
                start_time=trigger_at,
                end_time=detected_at,
                start_evidence_ref=trig_ref,
                end_evidence_ref=det_ref,
                calculation_reason=f"Clock anomaly: detection timestamp {detected_at.isoformat()} precedes trigger timestamp {trigger_at.isoformat()}",
            )

        delta_ms = (detected_at - trigger_at).total_seconds() * 1000.0
        val = max(0.0, delta_ms)
        thresh = policy.max_time_to_detect_ms
        is_comp = (val <= thresh) if thresh is not None else True

        return SLAMetric(
            metric_name=MetricName.TIME_TO_DETECT,
            metric_definition_version=policy.governance_version,
            transaction_id=transaction_id,
            status=MetricStatus.MEASURABLE,
            value=round(val, 2),
            unit=MetricUnit.MILLISECONDS,
            threshold=thresh,
            is_compliant=is_comp,
            start_time=trigger_at,
            end_time=detected_at,
            start_evidence_ref=trig_ref,
            end_evidence_ref=det_ref,
            evidence_refs=[trig_ref, det_ref],
            calculation_reason="Deterministic latency between trigger event and divergence detection",
            details=_sanitize_details({"trigger_source": trig_ref, "detection_source": det_ref}),
        )

    @classmethod
    def _compute_time_to_prove(
        cls,
        transaction_id: str,
        policy: SLAPolicy,
        integrity_result: Optional[IntegrityResult],
        integrity_trace: Optional[IntegrityTrace],
        events: List[CanonicalEvent],
        completed_at: Optional[datetime],
    ) -> SLAMetric:
        # Time to generate deterministic proof (MRDP)
        if integrity_result and integrity_result.status == IntegrityStatus.PASS:
            return SLAMetric(
                metric_name=MetricName.TIME_TO_PROVE,
                metric_definition_version=policy.governance_version,
                transaction_id=transaction_id,
                status=MetricStatus.NOT_APPLICABLE,
                value=None,
                unit=MetricUnit.MILLISECONDS,
                threshold=policy.max_time_to_prove_ms,
                is_compliant=True,
                calculation_reason="Transaction is PASS; drift proof generation not required",
            )

        # Detection time
        start_time: Optional[datetime] = None
        start_ref = "detection_event"
        if integrity_trace and integrity_trace.first_divergence and integrity_trace.first_divergence.detected_at:
            start_time = integrity_trace.first_divergence.detected_at
            start_ref = "first_divergence.detected_at"
        elif integrity_result and integrity_result.evaluated_at:
            start_time = integrity_result.evaluated_at
            start_ref = "integrity_result.evaluated_at"

        # Look for proof generation event or completed_at
        end_time: Optional[datetime] = None
        end_ref = "proof_event"
        for ev in events:
            if "mrdp" in ev.event_type.lower() or "proof" in ev.event_type.lower():
                end_time = ev.timestamp
                end_ref = f"event_{ev.event_id}"
                break

        if end_time is None:
            if completed_at:
                end_time = completed_at
                end_ref = "transaction_completed_at"
            elif integrity_result and integrity_result.evaluated_at and start_time:
                # Same tick proof creation during completion
                end_time = integrity_result.evaluated_at
                end_ref = "integrity_result.evaluated_at"

        if start_time is None or end_time is None:
            return SLAMetric(
                metric_name=MetricName.TIME_TO_PROVE,
                metric_definition_version=policy.governance_version,
                transaction_id=transaction_id,
                status=MetricStatus.UNKNOWN,
                value=None,
                unit=MetricUnit.MILLISECONDS,
                threshold=policy.max_time_to_prove_ms,
                is_compliant=None,
                start_time=start_time,
                end_time=end_time,
                calculation_reason="Missing timestamps for divergence detection or proof generation",
            )

        if end_time < start_time:
            return SLAMetric(
                metric_name=MetricName.TIME_TO_PROVE,
                metric_definition_version=policy.governance_version,
                transaction_id=transaction_id,
                status=MetricStatus.INVALID,
                value=None,
                unit=MetricUnit.MILLISECONDS,
                threshold=policy.max_time_to_prove_ms,
                is_compliant=False,
                start_time=start_time,
                end_time=end_time,
                calculation_reason="Proof timestamp precedes divergence detection timestamp",
            )

        val = max(0.0, (end_time - start_time).total_seconds() * 1000.0)
        thresh = policy.max_time_to_prove_ms
        is_comp = (val <= thresh) if thresh is not None else True

        return SLAMetric(
            metric_name=MetricName.TIME_TO_PROVE,
            metric_definition_version=policy.governance_version,
            transaction_id=transaction_id,
            status=MetricStatus.MEASURABLE,
            value=round(val, 2),
            unit=MetricUnit.MILLISECONDS,
            threshold=thresh,
            is_compliant=is_comp,
            start_time=start_time,
            end_time=end_time,
            start_evidence_ref=start_ref,
            end_evidence_ref=end_ref,
            evidence_refs=[start_ref, end_ref],
            calculation_reason="Elapsed milliseconds from drift detection to proof generation",
        )

    @classmethod
    def _compute_time_to_intervene(
        cls,
        transaction_id: str,
        policy: SLAPolicy,
        integrity_result: Optional[IntegrityResult],
        integrity_trace: Optional[IntegrityTrace],
        kill_switch_record: Optional[KillSwitchRecord],
        events: List[CanonicalEvent],
    ) -> SLAMetric:
        # Time to intervene via Kill Switch
        if kill_switch_record is None or kill_switch_record.resulting_state == KillSwitchState.RUNNING:
            return SLAMetric(
                metric_name=MetricName.TIME_TO_INTERVENE,
                metric_definition_version=policy.governance_version,
                transaction_id=transaction_id,
                status=MetricStatus.NOT_APPLICABLE,
                value=None,
                unit=MetricUnit.MILLISECONDS,
                threshold=policy.max_time_to_intervene_ms,
                is_compliant=True,
                calculation_reason="No safety intervention occurred; execution state remained RUNNING",
            )

        start_time: Optional[datetime] = None
        start_ref = "detection_event"
        if integrity_trace and integrity_trace.first_divergence and integrity_trace.first_divergence.detected_at:
            start_time = integrity_trace.first_divergence.detected_at
            start_ref = "first_divergence.detected_at"
        elif integrity_result and integrity_result.evaluated_at:
            start_time = integrity_result.evaluated_at
            start_ref = "integrity_result.evaluated_at"

        end_time: Optional[datetime] = getattr(kill_switch_record, "timestamp", getattr(kill_switch_record, "evaluated_at", None))
        end_ref = f"kill_switch_record_{kill_switch_record.resulting_state.value}"

        if start_time is None or end_time is None:
            return SLAMetric(
                metric_name=MetricName.TIME_TO_INTERVENE,
                metric_definition_version=policy.governance_version,
                transaction_id=transaction_id,
                status=MetricStatus.UNKNOWN,
                value=None,
                unit=MetricUnit.MILLISECONDS,
                threshold=policy.max_time_to_intervene_ms,
                is_compliant=None,
                start_time=start_time,
                end_time=end_time,
                calculation_reason="Missing detection or safety intervention timestamp",
            )

        if end_time < start_time:
            return SLAMetric(
                metric_name=MetricName.TIME_TO_INTERVENE,
                metric_definition_version=policy.governance_version,
                transaction_id=transaction_id,
                status=MetricStatus.INVALID,
                value=None,
                unit=MetricUnit.MILLISECONDS,
                threshold=policy.max_time_to_intervene_ms,
                is_compliant=False,
                start_time=start_time,
                end_time=end_time,
                calculation_reason="Intervention timestamp precedes detection timestamp",
            )

        val = max(0.0, (end_time - start_time).total_seconds() * 1000.0)
        thresh = policy.max_time_to_intervene_ms
        is_comp = (val <= thresh) if thresh is not None else True

        return SLAMetric(
            metric_name=MetricName.TIME_TO_INTERVENE,
            metric_definition_version=policy.governance_version,
            transaction_id=transaction_id,
            status=MetricStatus.MEASURABLE,
            value=round(val, 2),
            unit=MetricUnit.MILLISECONDS,
            threshold=thresh,
            is_compliant=is_comp,
            start_time=start_time,
            end_time=end_time,
            start_evidence_ref=start_ref,
            end_evidence_ref=end_ref,
            evidence_refs=[start_ref, end_ref],
            calculation_reason="Elapsed milliseconds from detection to safety intervention",
            details=_sanitize_details({"resulting_state": kill_switch_record.resulting_state.value}),
        )

    @classmethod
    def _compute_time_to_revalidate(
        cls,
        transaction_id: str,
        policy: SLAPolicy,
        kill_switch_record: Optional[KillSwitchRecord],
        events: List[CanonicalEvent],
        reference_time: datetime,
    ) -> SLAMetric:
        # Revalidation timing
        if kill_switch_record is None or kill_switch_record.resulting_state != KillSwitchState.REQUIRES_REVALIDATION:
            # Did an intervention require revalidation?
            return SLAMetric(
                metric_name=MetricName.TIME_TO_REVALIDATE,
                metric_definition_version=policy.governance_version,
                transaction_id=transaction_id,
                status=MetricStatus.NOT_APPLICABLE,
                value=None,
                unit=MetricUnit.MILLISECONDS,
                threshold=policy.max_time_to_revalidate_ms,
                is_compliant=True,
                calculation_reason="Transaction did not require safety revalidation",
            )

        start_time = getattr(kill_switch_record, "timestamp", getattr(kill_switch_record, "evaluated_at", None))
        start_ref = "kill_switch_requires_revalidation"

        # Check for revalidation event in events
        end_time: Optional[datetime] = None
        end_ref = "revalidation_event"
        for ev in events:
            if "revalidat" in ev.event_type.lower() or "recovery" in ev.event_type.lower():
                end_time = ev.timestamp
                end_ref = f"event_{ev.event_id}"
                break

        if end_time is None:
            return SLAMetric(
                metric_name=MetricName.TIME_TO_REVALIDATE,
                metric_definition_version=policy.governance_version,
                transaction_id=transaction_id,
                status=MetricStatus.UNKNOWN,
                value=None,
                unit=MetricUnit.MILLISECONDS,
                threshold=policy.max_time_to_revalidate_ms,
                is_compliant=None,
                start_time=start_time,
                calculation_reason="Revalidation is required but has not yet concluded",
            )

        if end_time < start_time:
            return SLAMetric(
                metric_name=MetricName.TIME_TO_REVALIDATE,
                metric_definition_version=policy.governance_version,
                transaction_id=transaction_id,
                status=MetricStatus.INVALID,
                value=None,
                unit=MetricUnit.MILLISECONDS,
                threshold=policy.max_time_to_revalidate_ms,
                is_compliant=False,
                start_time=start_time,
                end_time=end_time,
                calculation_reason="Revalidation timestamp precedes requirement timestamp",
            )

        val = max(0.0, (end_time - start_time).total_seconds() * 1000.0)
        thresh = policy.max_time_to_revalidate_ms
        is_comp = (val <= thresh) if thresh is not None else True

        return SLAMetric(
            metric_name=MetricName.TIME_TO_REVALIDATE,
            metric_definition_version=policy.governance_version,
            transaction_id=transaction_id,
            status=MetricStatus.MEASURABLE,
            value=round(val, 2),
            unit=MetricUnit.MILLISECONDS,
            threshold=thresh,
            is_compliant=is_comp,
            start_time=start_time,
            end_time=end_time,
            start_evidence_ref=start_ref,
            end_evidence_ref=end_ref,
            evidence_refs=[start_ref, end_ref],
            calculation_reason="Elapsed milliseconds to perform authoritative revalidation",
        )

    @classmethod
    def _compute_time_to_final_decision(
        cls,
        transaction_id: str,
        policy: SLAPolicy,
        created_at: Optional[datetime],
        completed_at: Optional[datetime],
        integrity_result: Optional[IntegrityResult],
        intent: Optional[IntentContract],
        events: List[CanonicalEvent],
    ) -> SLAMetric:
        start_time: Optional[datetime] = created_at
        start_ref = "created_at"
        if start_time is None and intent:
            start_time = intent.issued_at
            start_ref = "intent_issued_at"
        if start_time is None and events:
            sorted_evs = sorted([e for e in events if e.timestamp], key=lambda e: e.timestamp)
            if sorted_evs:
                start_time = sorted_evs[0].timestamp
                start_ref = f"event_{sorted_evs[0].event_id}"

        end_time: Optional[datetime] = completed_at
        end_ref = "completed_at"
        if end_time is None and integrity_result and integrity_result.evaluated_at:
            end_time = integrity_result.evaluated_at
            end_ref = "integrity_result.evaluated_at"

        if start_time is None or end_time is None:
            return SLAMetric(
                metric_name=MetricName.TIME_TO_FINAL_DECISION,
                metric_definition_version=policy.governance_version,
                transaction_id=transaction_id,
                status=MetricStatus.UNKNOWN,
                value=None,
                unit=MetricUnit.MILLISECONDS,
                threshold=policy.max_time_to_final_decision_ms,
                is_compliant=None,
                start_time=start_time,
                end_time=end_time,
                calculation_reason="Transaction has not reached final decision or missing lifecycle start timestamp",
            )

        if end_time < start_time:
            return SLAMetric(
                metric_name=MetricName.TIME_TO_FINAL_DECISION,
                metric_definition_version=policy.governance_version,
                transaction_id=transaction_id,
                status=MetricStatus.INVALID,
                value=None,
                unit=MetricUnit.MILLISECONDS,
                threshold=policy.max_time_to_final_decision_ms,
                is_compliant=False,
                start_time=start_time,
                end_time=end_time,
                calculation_reason="Final decision timestamp precedes transaction creation timestamp",
            )

        val = max(0.0, (end_time - start_time).total_seconds() * 1000.0)
        thresh = policy.max_time_to_final_decision_ms
        is_comp = (val <= thresh) if thresh is not None else True

        return SLAMetric(
            metric_name=MetricName.TIME_TO_FINAL_DECISION,
            metric_definition_version=policy.governance_version,
            transaction_id=transaction_id,
            status=MetricStatus.MEASURABLE,
            value=round(val, 2),
            unit=MetricUnit.MILLISECONDS,
            threshold=thresh,
            is_compliant=is_comp,
            start_time=start_time,
            end_time=end_time,
            start_evidence_ref=start_ref,
            end_evidence_ref=end_ref,
            evidence_refs=[start_ref, end_ref],
            calculation_reason="Elapsed milliseconds from transaction creation to final decision commitment",
        )

    @classmethod
    def _compute_unknown_duration(
        cls,
        transaction_id: str,
        policy: SLAPolicy,
        integrity_result: Optional[IntegrityResult],
        integrity_trace: Optional[IntegrityTrace],
        checkpoint_timeline: Optional[IntegrityCheckpointTimeline],
        events: List[CanonicalEvent],
        reference_time: datetime,
    ) -> SLAMetric:
        # Was the transaction ever in UNKNOWN?
        had_unknown = False
        start_time: Optional[datetime] = None
        start_ref = "unknown_state_entry"

        if integrity_result and integrity_result.status == IntegrityStatus.UNKNOWN:
            had_unknown = True
            start_time = integrity_result.evaluated_at
            start_ref = "integrity_result.evaluated_at"
        elif integrity_trace:
            for s in integrity_trace.steps:
                if s.status == StageIntegrityStatus.UNKNOWN:
                    had_unknown = True
                    start_time = s.timestamp
                    start_ref = f"trace_step_{s.sequence}"
                    break
        elif checkpoint_timeline:
            for cp in checkpoint_timeline.checkpoints:
                if cp.status == CheckpointStatus.UNKNOWN:
                    had_unknown = True
                    start_time = cp.created_at
                    start_ref = f"checkpoint_{cp.checkpoint_id}"
                    break

        if not had_unknown:
            return SLAMetric(
                metric_name=MetricName.UNKNOWN_EXPOSURE_DURATION,
                metric_definition_version=policy.governance_version,
                transaction_id=transaction_id,
                status=MetricStatus.NOT_APPLICABLE,
                value=None,
                unit=MetricUnit.MILLISECONDS,
                threshold=policy.max_unknown_exposure_ms,
                is_compliant=True,
                calculation_reason="Transaction never entered or exhibited UNKNOWN integrity state",
            )

        # Check for resolution timestamp in events or reference_time
        end_time: Optional[datetime] = None
        end_ref = "resolution_event"
        for ev in events:
            if "resolve" in ev.event_type.lower() or "resolution" in ev.event_type.lower():
                end_time = ev.timestamp
                end_ref = f"event_{ev.event_id}"
                break

        if end_time is None:
            # Active duration up to reference_time
            end_time = reference_time
            end_ref = "current_observation_time"

        if start_time is None:
            return SLAMetric(
                metric_name=MetricName.UNKNOWN_EXPOSURE_DURATION,
                metric_definition_version=policy.governance_version,
                transaction_id=transaction_id,
                status=MetricStatus.UNKNOWN,
                value=None,
                unit=MetricUnit.MILLISECONDS,
                threshold=policy.max_unknown_exposure_ms,
                is_compliant=None,
                calculation_reason="Missing timestamp for when UNKNOWN state was entered",
            )

        if end_time < start_time:
            return SLAMetric(
                metric_name=MetricName.UNKNOWN_EXPOSURE_DURATION,
                metric_definition_version=policy.governance_version,
                transaction_id=transaction_id,
                status=MetricStatus.INVALID,
                value=None,
                unit=MetricUnit.MILLISECONDS,
                threshold=policy.max_unknown_exposure_ms,
                is_compliant=False,
                start_time=start_time,
                end_time=end_time,
                calculation_reason="Resolution timestamp precedes UNKNOWN entry timestamp",
            )

        val = max(0.0, (end_time - start_time).total_seconds() * 1000.0)
        thresh = policy.max_unknown_exposure_ms
        is_comp = (val <= thresh) if thresh is not None else True

        return SLAMetric(
            metric_name=MetricName.UNKNOWN_EXPOSURE_DURATION,
            metric_definition_version=policy.governance_version,
            transaction_id=transaction_id,
            status=MetricStatus.MEASURABLE,
            value=round(val, 2),
            unit=MetricUnit.MILLISECONDS,
            threshold=thresh,
            is_compliant=is_comp,
            start_time=start_time,
            end_time=end_time,
            start_evidence_ref=start_ref,
            end_evidence_ref=end_ref,
            evidence_refs=[start_ref, end_ref],
            calculation_reason="Elapsed milliseconds transaction remained in UNKNOWN state",
        )

    @classmethod
    def _compute_checkpoint_coverage(
        cls,
        transaction_id: str,
        policy: SLAPolicy,
        checkpoint_timeline: Optional[IntegrityCheckpointTimeline],
    ) -> SLAMetric:
        if checkpoint_timeline is None or not checkpoint_timeline.checkpoints:
            return SLAMetric(
                metric_name=MetricName.CHECKPOINT_COVERAGE_RATIO,
                metric_definition_version=policy.governance_version,
                transaction_id=transaction_id,
                status=MetricStatus.UNKNOWN,
                value=None,
                unit=MetricUnit.RATIO,
                threshold=policy.min_checkpoint_coverage_ratio,
                is_compliant=None,
                calculation_reason="No checkpoint timeline available for this transaction",
            )

        total = 8  # Canonical 8 lifecycle checkpoints
        reached = sum(1 for cp in checkpoint_timeline.checkpoints if cp.status != CheckpointStatus.NOT_REACHED)
        ratio = reached / float(total)
        thresh = policy.min_checkpoint_coverage_ratio
        is_comp = (ratio >= thresh) if thresh is not None else True

        return SLAMetric(
            metric_name=MetricName.CHECKPOINT_COVERAGE_RATIO,
            metric_definition_version=policy.governance_version,
            transaction_id=transaction_id,
            status=MetricStatus.MEASURABLE,
            value=round(ratio, 4),
            unit=MetricUnit.RATIO,
            threshold=thresh,
            is_compliant=is_comp,
            evidence_refs=[f"cp_{cp.checkpoint_id}" for cp in checkpoint_timeline.checkpoints],
            calculation_reason=f"Reached {reached}/{total} canonical checkpoints",
            details={
                "total_checkpoints": total,
                "reached_checkpoints": reached,
                "unreached_checkpoints": total - reached,
            },
        )

    @classmethod
    def _compute_checkpoint_valid_ratio(
        cls,
        transaction_id: str,
        policy: SLAPolicy,
        checkpoint_timeline: Optional[IntegrityCheckpointTimeline],
    ) -> SLAMetric:
        if checkpoint_timeline is None or not checkpoint_timeline.checkpoints:
            return SLAMetric(
                metric_name=MetricName.CHECKPOINT_VALID_RATIO,
                metric_definition_version=policy.governance_version,
                transaction_id=transaction_id,
                status=MetricStatus.UNKNOWN,
                value=None,
                unit=MetricUnit.RATIO,
                threshold=policy.min_checkpoint_valid_ratio,
                is_compliant=None,
                calculation_reason="No checkpoint timeline available for this transaction",
            )

        total = 8
        valid = sum(1 for cp in checkpoint_timeline.checkpoints if cp.status == CheckpointStatus.VALID)
        invalid = sum(1 for cp in checkpoint_timeline.checkpoints if cp.status == CheckpointStatus.INVALID)
        unknown = sum(1 for cp in checkpoint_timeline.checkpoints if cp.status == CheckpointStatus.UNKNOWN)
        not_reached = sum(1 for cp in checkpoint_timeline.checkpoints if cp.status == CheckpointStatus.NOT_REACHED)

        ratio = valid / float(total)
        thresh = policy.min_checkpoint_valid_ratio
        is_comp = (ratio >= thresh) if thresh is not None else True

        return SLAMetric(
            metric_name=MetricName.CHECKPOINT_VALID_RATIO,
            metric_definition_version=policy.governance_version,
            transaction_id=transaction_id,
            status=MetricStatus.MEASURABLE,
            value=round(ratio, 4),
            unit=MetricUnit.RATIO,
            threshold=thresh,
            is_compliant=is_comp,
            evidence_refs=[f"cp_{cp.checkpoint_id}" for cp in checkpoint_timeline.checkpoints],
            calculation_reason=f"Verified {valid}/{total} checkpoints as VALID",
            details={
                "valid": valid,
                "invalid": invalid,
                "unknown": unknown,
                "not_reached": not_reached,
                "total": total,
            },
        )

    @classmethod
    def _compute_trace_completeness(
        cls,
        transaction_id: str,
        policy: SLAPolicy,
        integrity_trace: Optional[IntegrityTrace],
    ) -> SLAMetric:
        if integrity_trace is None or not integrity_trace.steps:
            return SLAMetric(
                metric_name=MetricName.TRACE_COMPLETENESS_RATIO,
                metric_definition_version=policy.governance_version,
                transaction_id=transaction_id,
                status=MetricStatus.UNKNOWN,
                value=None,
                unit=MetricUnit.RATIO,
                threshold=policy.min_trace_completeness_ratio,
                is_compliant=None,
                calculation_reason="No integrity trace available for this transaction",
            )

        total = 8  # Canonical 8 lifecycle stages
        reached = sum(1 for s in integrity_trace.steps if s.status != StageIntegrityStatus.UNREACHED)
        ratio = reached / float(total)
        thresh = policy.min_trace_completeness_ratio
        is_comp = (ratio >= thresh) if thresh is not None else True

        return SLAMetric(
            metric_name=MetricName.TRACE_COMPLETENESS_RATIO,
            metric_definition_version=policy.governance_version,
            transaction_id=transaction_id,
            status=MetricStatus.MEASURABLE,
            value=round(ratio, 4),
            unit=MetricUnit.RATIO,
            threshold=thresh,
            is_compliant=is_comp,
            evidence_refs=[f"trace_step_{s.sequence}" for s in integrity_trace.steps],
            calculation_reason=f"Reached {reached}/{total} lifecycle trace stages",
            details={
                "total_stages": total,
                "reached_stages": reached,
                "unreached_stages": total - reached,
            },
        )

    @classmethod
    def _compute_summary(cls, metrics: List[SLAMetric]) -> SLAComplianceSummary:
        total = len(metrics)
        measurable = sum(1 for m in metrics if m.status == MetricStatus.MEASURABLE)
        unknown = sum(1 for m in metrics if m.status == MetricStatus.UNKNOWN)
        not_applicable = sum(1 for m in metrics if m.status == MetricStatus.NOT_APPLICABLE)
        invalid = sum(1 for m in metrics if m.status == MetricStatus.INVALID)

        compliant = sum(1 for m in metrics if m.is_compliant is True)
        breached = sum(1 for m in metrics if m.is_compliant is False)

        # Overall compliance:
        # If any metric is breached or invalid -> overall not compliant (False)
        # If any metric is UNKNOWN -> overall compliance is UNKNOWN (None)
        # If all evaluated metrics are compliant -> True
        if breached > 0 or invalid > 0:
            overall = False
        elif unknown > 0:
            overall = None
        elif measurable + not_applicable == total:
            overall = True
        else:
            overall = None

        return SLAComplianceSummary(
            total_metrics=total,
            measurable_count=measurable,
            compliant_count=compliant,
            breached_count=breached,
            unknown_count=unknown,
            not_applicable_count=not_applicable,
            invalid_count=invalid,
            is_overall_compliant=overall,
        )
