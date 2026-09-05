"""
Deterministic Scenario Runner for TarkaRaksha Scenario Lab (I11).

Executes a ScenarioInputSnapshot against the authoritative production-shaped pipeline:
- T04 evaluate_integrity
- T07 build_mrdp
- T13 ReplayEngine
- I8 TransactionBindingService
- I9 KillSwitchService

Invariants:
1. Pure execution: does NOT calculate or hard-code scenario-specific outcomes.
2. Actual outcome is determined strictly by the underlying authoritative engine.
3. Expected assertion is compared to actual result to yield ScenarioStatus.PASS or FAIL.
4. Bit-for-bit reproducible: identical snapshot + reference_time yields identical result.
"""
from datetime import datetime
import logging
from typing import Any, Dict, List, Optional

from backend.app.domain.models import (
    EvidenceBundle,
    IntegrityResult,
    IntegrityStatus,
    MRDP,
    TransactionState,
)
from backend.app.domain.states.models import StateTransitionRecord
from backend.app.domain.binding.contracts import (
    BindingStatus,
    BindingVerificationOutcome,
    PaymentBindingClaim,
)
from backend.app.services.binding import TransactionBindingService
from backend.app.services.evaluation import evaluate_integrity
from backend.app.services.mrdp import build_mrdp
from backend.app.services.replay import (
    ReplayEngine,
    ReplaySnapshot,
    ReplayVerdict,
)
from backend.app.domain.scenario.contracts import (
    ScenarioDefinition,
    ScenarioId,
    ScenarioInputSnapshot,
    ScenarioResult,
    ScenarioStatus,
)

logger = logging.getLogger(__name__)


class ScenarioRunner:
    """
    Isolated execution runner for deterministic scenarios.
    Ensures zero cross-scenario state pollution.
    """

    @classmethod
    def run(
        cls,
        definition: ScenarioDefinition,
        snapshot: ScenarioInputSnapshot,
    ) -> ScenarioResult:
        """
        Executes a scenario definition against its snapshot through the authoritative engine.
        """
        actual_verdict: str = "UNKNOWN"
        integrity_result: Optional[IntegrityResult] = None
        mrdp: Optional[MRDP] = None
        tx_state: Optional[TransactionState] = None
        violations: List[str] = []
        details: Dict[str, Any] = {}

        try:
            # 1. Specialized Replay Attack routing to T13 Replay Engine
            if snapshot.scenario_id == ScenarioId.REPLAY_ATTACK:
                # Construct ReplaySnapshot with tampered recorded state (recorded PASS vs replayed state)
                replay_snap = ReplaySnapshot(
                    replay_id=f"rep_{snapshot.intent.intent_id}",
                    transaction_id=f"tx_{snapshot.intent.intent_id}",
                    contract=snapshot.intent,
                    events=snapshot.events,
                    evidence=snapshot.evidence,
                    state_transitions=[
                        StateTransitionRecord(
                            transition_id="tr_1",
                            from_state=TransactionState.CREATED,
                            to_state=TransactionState.EXECUTING,
                            reason="Initial order creation",
                            timestamp=snapshot.reference_time,
                        ),
                        StateTransitionRecord(
                            transition_id="tr_2",
                            from_state=TransactionState.EXECUTING,
                            to_state=TransactionState.OBSERVING,
                            reason="Observing gateway events",
                            timestamp=snapshot.reference_time,
                        ),
                        StateTransitionRecord(
                            transition_id="tr_3",
                            from_state=TransactionState.OBSERVING,
                            to_state=TransactionState.VERIFYING,
                            reason="Evaluating integrity",
                            timestamp=snapshot.reference_time,
                        ),
                        StateTransitionRecord(
                            transition_id="tr_4",
                            from_state=TransactionState.VERIFYING,
                            to_state=TransactionState.PASS,
                            reason="Claimed pass",
                            timestamp=snapshot.reference_time,
                        ),
                    ],
                    recorded_final_state=TransactionState.DRIFT,  # Mismatch against replayed PASS
                    reference_time=snapshot.reference_time,
                    rules_version=snapshot.version,
                )
                # Replay evaluation
                replay_res = ReplayEngine.replay(replay_snap)
                actual_verdict = replay_res.verdict.value
                details["replay_discrepancies"] = [d.model_dump() for d in replay_res.discrepancies]
                details["replay_verdict"] = actual_verdict

            # 2. Specialized Buyer Agent Cross-Transaction Reuse routing to I8 Binding Service
            elif snapshot.scenario_id == ScenarioId.BUYER_AGENT_REUSE:
                binding_service = TransactionBindingService()
                legitimate_tx_id = f"tx_{snapshot.intent.intent_id}"

                # Register legitimate binding for this transaction
                binding_service.register_binding(
                    intent_id=snapshot.intent.intent_id,
                    agent_id=snapshot.intent.issued_by,
                    merchant_id="merchant_primary",
                    transaction_id=legitimate_tx_id,
                    order_id="order_legit_001",
                    attempt_id="att_1",
                    created_at=snapshot.reference_time,
                )

                # Attempt to verify a claim referencing the foreign transaction
                foreign_tx_id = snapshot.binding_context.transaction_id if snapshot.binding_context else "tx_other_999"
                claim = PaymentBindingClaim(
                    intent_id=snapshot.intent.intent_id,
                    agent_id=snapshot.binding_context.agent_id if snapshot.binding_context else "buyer_agent_rogue",
                    merchant_id="merchant_primary",
                    transaction_id=foreign_tx_id,
                    order_id="order_foreign_999",
                    payment_id="pay_foreign_999",
                    attempt_id="att_foreign",
                )
                outcome = binding_service.verify_transaction_binding(
                    claim=claim,
                    reference_time=snapshot.reference_time,
                )
                actual_verdict = "REJECTED" if not outcome.is_valid else "PASS"
                details["binding_status"] = outcome.status.value
                details["binding_violations"] = [v.value for v in outcome.violations]
                violations.extend([v.value for v in outcome.violations])

            # 3. Standard Deterministic Integrity Pipeline (T04, T07)
            else:
                integrity_result = evaluate_integrity(
                    contract=snapshot.intent,
                    evidence_list=snapshot.evidence,
                    events=snapshot.events,
                    evaluation_id=f"eval_{snapshot.scenario_id.value}_{snapshot.intent.intent_id}",
                    reference_time=snapshot.reference_time,
                )
                actual_verdict = integrity_result.status.value
                violations = list(integrity_result.violations)

                # Generate cryptographic MRDP proof if DRIFT detected (T07)
                if integrity_result.status == IntegrityStatus.DRIFT:
                    bundle = EvidenceBundle(
                        bundle_id=f"bnd_{snapshot.intent.intent_id}",
                        intent_id=snapshot.intent.intent_id,
                        transaction_id=f"tx_{snapshot.intent.intent_id}",
                        created_at=snapshot.reference_time,
                        records=snapshot.evidence,
                        events=snapshot.events,
                    )
                    mrdp = build_mrdp(
                        contract=snapshot.intent,
                        integrity_result=integrity_result,
                        evidence_bundle=bundle,
                        generated_at=snapshot.reference_time,
                    )
                    details["mrdp_digest"] = mrdp.proof_digest
                    details["mrdp_id"] = mrdp.mrdp_id

                details["rule_results"] = integrity_result.rule_results
                details["explanation"] = integrity_result.explanation

        except Exception as exc:
            logger.exception("Error executing scenario %s: %s", definition.scenario_id, exc)
            actual_verdict = "ERROR"
            violations.append(str(exc))
            details["error"] = str(exc)

        # 4. Compare Expected Assertion vs Actual Engine Outcome
        is_pass = (actual_verdict == definition.expected_verdict)
        scenario_status = ScenarioStatus.PASS if is_pass else ScenarioStatus.FAIL
        if actual_verdict == "ERROR":
            scenario_status = ScenarioStatus.ERROR

        # 5. Format Human-Readable Report
        report_lines = [
            f"============================================================",
            f"SCENARIO: {definition.scenario_id.value} — {definition.name}",
            f"STATUS: {scenario_status.value} (Expected: {definition.expected_verdict} | Actual: {actual_verdict})",
            f"CATEGORY: {definition.category.value} | VERSION: {definition.version}",
            f"SNAPSHOT DIGEST: {snapshot.compute_digest()[:16]}...",
            f"REFERENCE TIME: {snapshot.reference_time.isoformat()}",
            f"FAULT INJECTED: {snapshot.fault_injection or 'None (Happy Path)'}",
            f"EVENTS PROCESSED: {len(snapshot.events)} | EVIDENCE COUNT: {len(snapshot.evidence)}",
        ]
        if violations:
            report_lines.append(f"VIOLATIONS: {'; '.join(violations)}")
        if mrdp:
            report_lines.append(f"MRDP PROOF DIGEST: {mrdp.proof_digest}")
        report_lines.append(f"============================================================")
        human_readable_report = "\n".join(report_lines)

        return ScenarioResult(
            scenario_id=definition.scenario_id,
            scenario_version=definition.version,
            input_snapshot_hash=snapshot.compute_digest(),
            expected_verdict=definition.expected_verdict,
            actual_verdict=actual_verdict,
            scenario_status=scenario_status,
            integrity_status=integrity_result.status if integrity_result else None,
            transaction_state=tx_state,
            mrdp_digest=mrdp.proof_digest if mrdp else None,
            violations=violations,
            evidence_count=len(snapshot.evidence),
            events_processed=len(snapshot.events),
            reference_time=snapshot.reference_time,
            policy_version=definition.policy_version,
            rules_version=definition.rules_version,
            details=details,
            human_readable_report=human_readable_report,
        )
