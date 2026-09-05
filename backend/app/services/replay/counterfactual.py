"""
Counterfactual Replay Analysis Module for TarkaRaksha (I3.5 - Optional Component).

Requirements:
- Named strictly 'Counterfactual replay analysis' (NOT causal inference / formal causal proof).
- Evaluates what deterministic decision WOULD have been reached if a candidate event were modified or removed.
- Purely side-effect-free, isolated CPU execution reusing T13 ReplayEngine.
- Does NOT mutate production state, historical snapshot, or perform any network/provider calls.
- Produces a structured, machine-readable comparison between the baseline and counterfactual trace.
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from backend.app.domain.models import (
    CanonicalEvent,
    Evidence,
    IntegrityResult,
    IntegrityStatus,
    TransactionState,
)
from backend.app.services.replay.contracts import (
    ReplayResult,
    ReplaySnapshot,
    ReplayVerdict,
)
from backend.app.services.replay.engine import ReplayEngine


class CounterfactualMutationType(str, Enum):
    """Classification of event-level intervention tested during counterfactual replay."""
    REMOVE_EVENT = "REMOVE_EVENT"
    MODIFY_EVENT_PAYLOAD = "MODIFY_EVENT_PAYLOAD"
    SUBSTITUTE_EVENT = "SUBSTITUTE_EVENT"


class CounterfactualComparison(BaseModel):
    """
    Detailed audit comparison between the historical baseline replay and counterfactual replay.
    """
    transaction_id: str
    mutation_type: CounterfactualMutationType
    target_event_id: str
    baseline_integrity_status: IntegrityStatus
    counterfactual_integrity_status: IntegrityStatus
    baseline_verdict: ReplayVerdict
    counterfactual_verdict: ReplayVerdict
    discrepancy_eliminated: bool
    explanation: str
    baseline_replayed_state: TransactionState
    counterfactual_replayed_state: TransactionState

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )


class CounterfactualReplayAnalysisService:
    """
    Deterministic counterfactual replay analyzer for transaction audit and anomaly diagnosis.
    Never alters historical recordings or triggers live side effects.
    """

    @classmethod
    def analyze_event_removal(
        cls,
        snapshot: ReplaySnapshot,
        candidate_event_id: str,
        counterfactual_replay_id: Optional[str] = None,
    ) -> CounterfactualComparison:
        """
        Tests whether removing a candidate event resolves or alters an observed DRIFT / UNKNOWN outcome.
        
        Example from canonical doc:
        WITH RETRY: duplicate capture → DRIFT
        WITHOUT RETRY: single capture → PASS
        """
        # 1. Baseline replay
        baseline_res = ReplayEngine.replay(snapshot)

        # 2. Construct isolated counterfactual event sequence (pure filter, no mutation to original)
        cf_events = [e for e in snapshot.events if e.event_id != candidate_event_id]

        cf_snapshot = snapshot.model_copy(
            update={
                "replay_id": counterfactual_replay_id or f"cf-remove-{candidate_event_id}",
                "events": cf_events,
            }
        )

        # 3. Counterfactual replay
        cf_res = ReplayEngine.replay(cf_snapshot)

        # 4. Compare results
        discrepancy_eliminated = (
            baseline_res.replayed_integrity_result.status != IntegrityStatus.PASS
            and cf_res.replayed_integrity_result.status == IntegrityStatus.PASS
        )

        explanation = (
            f"Counterfactual removal of event '{candidate_event_id}' shifted integrity status from "
            f"{baseline_res.replayed_integrity_result.status.value} to {cf_res.replayed_integrity_result.status.value}. "
            f"Discrepancy eliminated: {discrepancy_eliminated}."
        )

        return CounterfactualComparison(
            transaction_id=snapshot.transaction_id,
            mutation_type=CounterfactualMutationType.REMOVE_EVENT,
            target_event_id=candidate_event_id,
            baseline_integrity_status=baseline_res.replayed_integrity_result.status,
            counterfactual_integrity_status=cf_res.replayed_integrity_result.status,
            baseline_verdict=baseline_res.verdict,
            counterfactual_verdict=cf_res.verdict,
            discrepancy_eliminated=discrepancy_eliminated,
            explanation=explanation,
            baseline_replayed_state=baseline_res.replayed_state,
            counterfactual_replayed_state=cf_res.replayed_state,
        )

    @classmethod
    def analyze_event_modification(
        cls,
        snapshot: ReplaySnapshot,
        target_event_id: str,
        modifier_fn: Callable[[CanonicalEvent], CanonicalEvent],
        counterfactual_replay_id: Optional[str] = None,
    ) -> CounterfactualComparison:
        """
        Tests whether modifying attributes of a candidate event alters the replay outcome.
        """
        # 1. Baseline replay
        baseline_res = ReplayEngine.replay(snapshot)

        # 2. Construct isolated counterfactual event sequence
        cf_events: List[CanonicalEvent] = []
        for e in snapshot.events:
            if e.event_id == target_event_id:
                cf_events.append(modifier_fn(e))
            else:
                cf_events.append(e)

        cf_snapshot = snapshot.model_copy(
            update={
                "replay_id": counterfactual_replay_id or f"cf-modify-{target_event_id}",
                "events": cf_events,
            }
        )

        # 3. Counterfactual replay
        cf_res = ReplayEngine.replay(cf_snapshot)

        # 4. Compare results
        discrepancy_eliminated = (
            baseline_res.replayed_integrity_result.status != IntegrityStatus.PASS
            and cf_res.replayed_integrity_result.status == IntegrityStatus.PASS
        )

        explanation = (
            f"Counterfactual modification of event '{target_event_id}' shifted integrity status from "
            f"{baseline_res.replayed_integrity_result.status.value} to {cf_res.replayed_integrity_result.status.value}. "
            f"Discrepancy eliminated: {discrepancy_eliminated}."
        )

        return CounterfactualComparison(
            transaction_id=snapshot.transaction_id,
            mutation_type=CounterfactualMutationType.MODIFY_EVENT_PAYLOAD,
            target_event_id=target_event_id,
            baseline_integrity_status=baseline_res.replayed_integrity_result.status,
            counterfactual_integrity_status=cf_res.replayed_integrity_result.status,
            baseline_verdict=baseline_res.verdict,
            counterfactual_verdict=cf_res.verdict,
            discrepancy_eliminated=discrepancy_eliminated,
            explanation=explanation,
            baseline_replayed_state=baseline_res.replayed_state,
            counterfactual_replayed_state=cf_res.replayed_state,
        )
