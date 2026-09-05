"""Integrity SLA Metrics Service for Innovation I15 — Integrity SLA Metrics.

Orchestrates deterministic SLA metric computation by consuming authoritative outputs
from the deterministic integrity engine, I13 Integrity Trace, and I14 Checkpoints.
"""
from datetime import datetime
from typing import Any, List, Optional

from backend.app.domain.sla.contracts import (
    SLAPolicy,
    IntegritySLAMetricsReport,
)
from backend.app.domain.sla.engine import DeterministicSLAEngine
from backend.app.domain.models.intent import IntentContract
from backend.app.domain.models.payment import ProviderOrder, ProviderPayment
from backend.app.domain.models.integrity import IntegrityResult
from backend.app.domain.models.evidence import CanonicalEvent
from backend.app.domain.binding.contracts import BindingVerificationOutcome
from backend.app.domain.kill_switch.contracts import KillSwitchRecord, KillSwitchState
from backend.app.domain.trace.contracts import IntegrityTrace
from backend.app.domain.checkpoint.contracts import IntegrityCheckpointTimeline
from backend.app.services.trace.service import IntegrityTraceService
from backend.app.services.checkpoint.service import IntegrityCheckpointService


class IntegritySLAMetricsService:
    """
    Service layer coordinator for calculating deterministic SLA metrics and compliance reports.
    """

    def __init__(
        self,
        engine: Optional[DeterministicSLAEngine] = None,
        trace_service: Optional[IntegrityTraceService] = None,
        checkpoint_service: Optional[IntegrityCheckpointService] = None,
    ):
        self._engine = engine or DeterministicSLAEngine
        self._trace_service = trace_service or IntegrityTraceService()
        self._checkpoint_service = checkpoint_service or IntegrityCheckpointService(trace_service=self._trace_service)

    def compute_sla_report(
        self,
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
        Computes a complete, deterministic IntegritySLAMetricsReport.
        """
        # If trace or checkpoint timeline is missing and session components exist, build them
        trace = integrity_trace
        if trace is None and (intent or order or payment or integrity_result):
            trace = self._trace_service.build_trace(
                transaction_id=transaction_id,
                intent=intent,
                order=order,
                payment=payment,
                integrity_result=integrity_result,
                binding_outcome=binding_outcome,
                kill_switch_record=kill_switch_record,
                events=events,
                reference_time=reference_time,
            )

        timeline = checkpoint_timeline
        if timeline is None and (intent or order or payment or integrity_result):
            timeline = self._checkpoint_service.build_timeline(
                transaction_id=transaction_id,
                intent=intent,
                order=order,
                payment=payment,
                integrity_result=integrity_result,
                binding_outcome=binding_outcome,
                kill_switch_record=kill_switch_record,
                events=events,
                integrity_trace=trace,
                reference_time=reference_time,
            )

        return self._engine.compute_report(
            transaction_id=transaction_id,
            policy=policy,
            intent=intent,
            order=order,
            payment=payment,
            integrity_result=integrity_result,
            integrity_trace=trace,
            checkpoint_timeline=timeline,
            binding_outcome=binding_outcome,
            kill_switch_record=kill_switch_record,
            events=events,
            created_at=created_at,
            completed_at=completed_at,
            reference_time=reference_time,
            reproducibility_reference=reproducibility_reference,
        )

    def get_sla_report_for_session(
        self,
        session: Any,
        policy: Optional[SLAPolicy] = None,
        kill_switch_state: KillSwitchState = KillSwitchState.RUNNING,
        reference_time: Optional[datetime] = None,
    ) -> IntegritySLAMetricsReport:
        """
        Computes an IntegritySLAMetricsReport directly from an active runtime TransactionSession.
        """
        completed_at = None
        if hasattr(session, "completed_response") and session.completed_response:
            # If transaction completed, use session.updated_at
            completed_at = getattr(session, "updated_at", None)

        # Build trace and checkpoints from session
        trace = self._trace_service.build_trace_from_session(
            session=session,
            kill_switch_state=kill_switch_state,
            reference_time=reference_time,
        )

        timeline = self._checkpoint_service.build_timeline_from_session(
            session=session,
            kill_switch_state=kill_switch_state,
            reference_time=reference_time,
        )

        return self._engine.compute_report(
            transaction_id=session.transaction_id,
            policy=policy,
            intent=getattr(session, "intent", None),
            order=getattr(session, "order", None),
            payment=getattr(session, "payment", None),
            integrity_result=getattr(session, "integrity_result", None),
            integrity_trace=trace,
            checkpoint_timeline=timeline,
            binding_outcome=getattr(session, "binding_outcome", None),
            kill_switch_record=getattr(session, "kill_switch_record", None),
            events=getattr(session, "events", None),
            created_at=getattr(session, "created_at", None),
            completed_at=completed_at,
            reference_time=reference_time,
        )
