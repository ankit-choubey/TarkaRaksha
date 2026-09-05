"""
Replay Engine core execution and comparison service for TarkaRaksha (T13).

Requirements:
- Reconstruct what the system should have decided from recorded history.
- Pure function: zero live network calls, zero live AI calls, zero live Razorpay queries, zero financial side effects.
- Reuse T04 deterministic engine (evaluate_integrity).
- Reuse T05 state machine (TransactionStateMachine via reconstructor).
- Reuse T06 evidence normalization and authority hierarchy.
- Reuse T07 MRDP validation (verify_mrdp_integrity) and construction (build_mrdp).
- Strictly deterministic comparison:
  MATCH: Replay perfectly agrees with recorded outcome.
  MISMATCH: Replay differs from recorded outcome (drift/tampering/discrepancy).
  INVALID_REPLAY: Replay input violates invariants or is ambiguous.
"""
from datetime import datetime, timezone
from typing import List, Optional

from backend.app.domain.models import (
    Evidence,
    EvidenceBundle,
    IntegrityResult,
    IntegrityStatus,
    MRDP,
    TransactionState,
)
from backend.app.services.evaluation import evaluate_integrity
from backend.app.services.mrdp import build_mrdp, verify_mrdp_integrity
from backend.app.services.replay.contracts import (
    RULES_VERSION_DEFAULT,
    InvalidReplayInputError,
    ReplayAmbiguityError,
    ReplayDiscrepancy,
    ReplayResult,
    ReplaySnapshot,
    ReplayVerdict,
)
from backend.app.services.replay.ordering import (
    order_canonical_events,
    order_evidence_records,
)
from backend.app.services.replay.reconstructor import replay_state_transitions


class ReplayEngine:
    """
    Deterministic transaction audit and replay engine for TarkaRaksha.
    """

    @classmethod
    def replay(cls, snapshot: ReplaySnapshot) -> ReplayResult:
        """
        Executes a deterministic replay over the given immutable ReplaySnapshot.
        
        Steps:
        1. Validate replay input structural invariants.
        2. Establish canonical deterministic ordering for events and evidence.
        3. Replay state transitions using the authoritative T05 state machine.
        4. Re-run deterministic integrity evaluation (T04).
        5. Verify/reconstruct MRDP proof if applicable (T07).
        6. Compare replayed outcome against recorded outcome.
        7. Classify into MATCH, MISMATCH, or INVALID_REPLAY.
        """
        executed_at = snapshot.reference_time
        discrepancies: List[ReplayDiscrepancy] = []

        # 1. Input validation & sanity check
        if not snapshot.replay_id or not snapshot.replay_id.strip():
            raise InvalidReplayInputError("Replay ID cannot be empty.")
        if not snapshot.transaction_id or not snapshot.transaction_id.strip():
            raise InvalidReplayInputError("Transaction ID cannot be empty.")
        if snapshot.contract is None:
            raise InvalidReplayInputError("IntentContract is mandatory for replay.")

        # Check rules version match
        rules_match = (snapshot.rules_version == RULES_VERSION_DEFAULT)
        if not rules_match:
            discrepancies.append(
                ReplayDiscrepancy(
                    field="rules_version",
                    recorded_value=snapshot.rules_version,
                    replayed_value=RULES_VERSION_DEFAULT,
                    explanation=(
                        f"Rules version mismatch: recorded version {snapshot.rules_version} "
                        f"differs from engine version {RULES_VERSION_DEFAULT}."
                    ),
                )
            )

        # 2. Canonical deterministic ordering
        try:
            ordered_events = order_canonical_events(snapshot.events)
            ordered_evidence = order_evidence_records(snapshot.evidence)
        except ReplayAmbiguityError as err:
            discrepancies.append(
                ReplayDiscrepancy(
                    field="event_ordering",
                    recorded_value="ambiguous_or_conflicting",
                    replayed_value="REJECTED",
                    explanation=str(err),
                )
            )
            # Ambiguous/tampered event ordering is an INVALID_REPLAY condition
            return ReplayResult(
                replay_id=snapshot.replay_id,
                transaction_id=snapshot.transaction_id,
                verdict=ReplayVerdict.INVALID_REPLAY,
                replayed_state=TransactionState.UNKNOWN,
                replayed_integrity_result=IntegrityResult(
                    evaluation_id=f"replay-eval-{snapshot.transaction_id}",
                    intent_id=snapshot.contract.intent_id,
                    status=IntegrityStatus.UNKNOWN,
                    evaluated_at=executed_at,
                    rule_results={},
                    violations=[str(err)],
                    evidence_ids=[],
                ),
                replayed_mrdp=None,
                discrepancies=discrepancies,
                ordered_event_ids=[],
                ordered_evidence_ids=[],
                is_mrdp_valid=None,
                rules_version_match=rules_match,
                executed_at=executed_at,
                metadata={"reason": "ReplayAmbiguityError"},
            )

        ordered_event_ids = [e.event_id for e in ordered_events]
        ordered_evidence_ids = [e.evidence_id for e in ordered_evidence]

        # 3. State machine replay & transition reconstruction
        state_outcome = replay_state_transitions(
            transaction_id=snapshot.transaction_id,
            contract=snapshot.contract,
            recorded_transitions=snapshot.state_transitions,
            expected_final_state=snapshot.recorded_final_state,
        )
        discrepancies.extend(state_outcome.discrepancies)

        # If state transition replay failed due to an illegal jump or forbidden state transition,
        # it is an invalid replay condition
        if state_outcome.has_illegal_transition:
            # Reconstruct evaluation for audit visibility
            replayed_integrity = evaluate_integrity(
                contract=snapshot.contract,
                evidence_list=ordered_evidence,
                events=ordered_events,
                evaluation_id=f"replay-eval-{snapshot.transaction_id}",
                reference_time=snapshot.reference_time,
            )
            return ReplayResult(
                replay_id=snapshot.replay_id,
                transaction_id=snapshot.transaction_id,
                verdict=ReplayVerdict.INVALID_REPLAY,
                replayed_state=state_outcome.final_state,
                replayed_integrity_result=replayed_integrity,
                replayed_mrdp=None,
                discrepancies=discrepancies,
                ordered_event_ids=ordered_event_ids,
                ordered_evidence_ids=ordered_evidence_ids,
                is_mrdp_valid=None,
                rules_version_match=rules_match,
                executed_at=executed_at,
                metadata={"reason": "InvalidStateTransition"},
            )

        # 4. Deterministic integrity evaluation (T04)
        replayed_integrity = evaluate_integrity(
            contract=snapshot.contract,
            evidence_list=ordered_evidence,
            events=ordered_events,
            evaluation_id=f"replay-eval-{snapshot.transaction_id}",
            reference_time=snapshot.reference_time,
        )

        # Compare replayed integrity result against recorded result
        if snapshot.recorded_integrity_result:
            rec_status = snapshot.recorded_integrity_result.status
            rep_status = replayed_integrity.status
            if rec_status != rep_status:
                discrepancies.append(
                    ReplayDiscrepancy(
                        field="integrity_result.status",
                        recorded_value=rec_status.value,
                        replayed_value=rep_status.value,
                        explanation=(
                            f"Integrity status divergence: recorded was {rec_status.value}, "
                            f"replayed evaluation yielded {rep_status.value}."
                        ),
                    )
                )

        # If recorded final state was PASS but replayed evaluation detects DRIFT or UNKNOWN, record discrepancy
        if snapshot.recorded_final_state == TransactionState.PASS and replayed_integrity.status != IntegrityStatus.PASS:
            discrepancies.append(
                ReplayDiscrepancy(
                    field="transaction_state.integrity_divergence",
                    recorded_value=TransactionState.PASS.value,
                    replayed_value=replayed_integrity.status.value,
                    explanation=(
                        f"Fraud/tamper detected: recorded transaction reached terminal PASS, "
                        f"but deterministic replay evaluated integrity as {replayed_integrity.status.value}."
                    ),
                )
            )

        # 5. MRDP proof verification & reconstruction (T07)
        replayed_mrdp: Optional[MRDP] = None
        is_mrdp_valid: Optional[bool] = None

        if snapshot.recorded_mrdp:
            # Step A: Validate the recorded MRDP's cryptographic digest integrity
            is_mrdp_valid = verify_mrdp_integrity(snapshot.recorded_mrdp)
            if not is_mrdp_valid:
                discrepancies.append(
                    ReplayDiscrepancy(
                        field="recorded_mrdp.proof_digest",
                        recorded_value=snapshot.recorded_mrdp.proof_digest,
                        replayed_value="INVALID_DIGEST",
                        explanation="Recorded MRDP failed cryptographic integrity check: payload was tampered with.",
                    )
                )

            # Step B: If replayed integrity found non-PASS, reconstruct replayed MRDP and compare
            if replayed_integrity.status in (IntegrityStatus.DRIFT, IntegrityStatus.UNKNOWN):
                evidence_bundle = EvidenceBundle(
                    bundle_id=f"replay-bundle-{snapshot.transaction_id}",
                    intent_id=snapshot.contract.intent_id,
                    transaction_id=snapshot.transaction_id,
                    created_at=snapshot.reference_time,
                    records=ordered_evidence,
                    events=ordered_events,
                )
                replayed_mrdp = build_mrdp(
                    contract=snapshot.contract,
                    integrity_result=replayed_integrity,
                    evidence_bundle=evidence_bundle,
                    generated_at=snapshot.recorded_mrdp.generated_at,
                    mrdp_id=snapshot.recorded_mrdp.mrdp_id,
                )

                # Compare error code and status
                if snapshot.recorded_mrdp.error_code != replayed_mrdp.error_code:
                    discrepancies.append(
                        ReplayDiscrepancy(
                            field="mrdp.error_code",
                            recorded_value=snapshot.recorded_mrdp.error_code,
                            replayed_value=replayed_mrdp.error_code,
                            explanation=(
                                f"MRDP error code mismatch: recorded {snapshot.recorded_mrdp.error_code} "
                                f"vs replayed {replayed_mrdp.error_code}."
                            ),
                        )
                    )
                if snapshot.recorded_mrdp.proof_digest != replayed_mrdp.proof_digest:
                    discrepancies.append(
                        ReplayDiscrepancy(
                            field="mrdp.proof_digest",
                            recorded_value=snapshot.recorded_mrdp.proof_digest,
                            replayed_value=replayed_mrdp.proof_digest,
                            explanation="MRDP proof digest divergence between recorded and replayed drift proof.",
                        )
                    )

        # 6. Overall verdict calculation (§15)
        # Any discrepancy implies MISMATCH
        if not discrepancies:
            verdict = ReplayVerdict.MATCH
        else:
            verdict = ReplayVerdict.MISMATCH

        return ReplayResult(
            replay_id=snapshot.replay_id,
            transaction_id=snapshot.transaction_id,
            verdict=verdict,
            replayed_state=state_outcome.final_state,
            replayed_integrity_result=replayed_integrity,
            replayed_mrdp=replayed_mrdp,
            discrepancies=discrepancies,
            ordered_event_ids=ordered_event_ids,
            ordered_evidence_ids=ordered_evidence_ids,
            is_mrdp_valid=is_mrdp_valid,
            rules_version_match=rules_match,
            executed_at=executed_at,
            metadata={"total_discrepancies": len(discrepancies)},
        )
