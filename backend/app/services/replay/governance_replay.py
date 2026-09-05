"""
Governance and Replay Integration Service for TarkaRaksha (I3.4).

Provides an auditable wrapper around the existing T13 ReplayEngine:
1. Replay with explicit GovernanceVersion (rules_version & policy_version).
2. Deterministic ReproducibilityRecord generation from replay outcomes.
3. DecisionReproducibilityCertificate generation from verified replays.
4. Certificate and snapshot verification against recorded transaction reality.
5. Strict zero-side-effect, deterministic execution reusing T13 without modifying T01-T13.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from backend.app.domain.governance.certificate import (
    DecisionCertificateVerificationResult,
    DecisionReproducibilityCertificate,
)
from backend.app.domain.governance.contracts import (
    DEFAULT_POLICY_VERSION,
    DEFAULT_RULES_VERSION,
    GovernanceVersion,
)
from backend.app.domain.governance.record import (
    ReproducibilityRecord,
    compute_deterministic_hash,
)
from backend.app.domain.models import (
    IntegrityResult,
    IntegrityStatus,
    TransactionState,
)
from backend.app.services.replay.contracts import (
    ReplayDiscrepancy,
    ReplayResult,
    ReplaySnapshot,
    ReplayVerdict,
)
from backend.app.services.replay.engine import ReplayEngine


class GovernedReplayResult(BaseModel):
    """
    Enhanced replay output combining T13 deterministic replay with I3 governance:
    - Base T13 ReplayResult
    - Explicit GovernanceVersion (rules_version & policy_version)
    - Deterministic ReproducibilityRecord
    - Optional DecisionReproducibilityCertificate
    - Policy version consistency check
    """
    replay_result: ReplayResult
    governance_version: GovernanceVersion
    reproducibility_record: ReproducibilityRecord
    certificate: Optional[DecisionReproducibilityCertificate] = None
    policy_version_match: bool = True

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )

    @property
    def is_match(self) -> bool:
        return self.replay_result.is_match and self.policy_version_match

    @property
    def verdict(self) -> ReplayVerdict:
        if not self.policy_version_match:
            return ReplayVerdict.MISMATCH
        return self.replay_result.verdict


class GovernedReplayService:
    """
    Service integrating TarkaRaksha Governance with T13 ReplayEngine.
    Pure CPU execution: zero live network, zero live AI, zero financial side effects.
    """

    @classmethod
    def execute_governed_replay(
        cls,
        snapshot: ReplaySnapshot,
        governance: Optional[GovernanceVersion] = None,
        issue_certificate: bool = True,
    ) -> GovernedReplayResult:
        """
        Executes a deterministic governed replay over a ReplaySnapshot.
        
        Steps:
        1. Attribute decision rules_version and policy_version via GovernanceVersion.
        2. Run T13 ReplayEngine to obtain deterministic replay evaluation.
        3. Check policy_version consistency between IntentContract and GovernanceVersion.
        4. Produce immutable ReproducibilityRecord.
        5. Optionally generate a DecisionReproducibilityCertificate.
        """
        gov = governance or GovernanceVersion(
            rules_version=snapshot.rules_version,
            policy_version=getattr(snapshot.contract, "policy_version", DEFAULT_POLICY_VERSION),
        )

        # 1. Execute authoritative T13 replay
        t13_result = ReplayEngine.replay(snapshot)

        # 2. Check policy version match
        contract_policy = getattr(snapshot.contract, "policy_version", DEFAULT_POLICY_VERSION)
        policy_match = (contract_policy == gov.policy_version)

        discrepancies = list(t13_result.discrepancies)
        if not policy_match:
            discrepancies.append(
                ReplayDiscrepancy(
                    field="policy_version",
                    recorded_value=contract_policy,
                    replayed_value=gov.policy_version,
                    explanation=(
                        f"Policy version mismatch: IntentContract policy '{contract_policy}' "
                        f"differs from governed evaluation policy '{gov.policy_version}'."
                    ),
                )
            )

        # Re-wrap T13 result if discrepancies were added due to policy mismatch
        if not policy_match and t13_result.is_match:
            adjusted_t13 = t13_result.model_copy(
                update={
                    "verdict": ReplayVerdict.MISMATCH,
                    "discrepancies": discrepancies,
                }
            )
        else:
            adjusted_t13 = t13_result

        # 3. Create ReproducibilityRecord
        rec = ReproducibilityRecord.create(
            record_id=f"rec-{snapshot.replay_id}",
            transaction_id=snapshot.transaction_id,
            intent=snapshot.contract,
            events=snapshot.events,
            evidence=snapshot.evidence,
            reference_time=snapshot.reference_time,
            recorded_result=adjusted_t13.replayed_integrity_result,
            rules_version=gov.rules_version,
            policy_version=gov.policy_version,
            state_transitions=snapshot.state_transitions,
            recorded_final_state=adjusted_t13.replayed_state,
        )

        # 4. Optionally issue DecisionReproducibilityCertificate
        cert: Optional[DecisionReproducibilityCertificate] = None
        if issue_certificate:
            cert = DecisionReproducibilityCertificate.issue(
                certificate_id=f"cert-{snapshot.replay_id}",
                transaction_id=snapshot.transaction_id,
                decision=adjusted_t13.replayed_integrity_result.status,
                intent=snapshot.contract,
                events=snapshot.events,
                evidence=snapshot.evidence,
                decision_timestamp=snapshot.reference_time,
                rules_version=gov.rules_version,
                policy_version=gov.policy_version,
            )

        return GovernedReplayResult(
            replay_result=adjusted_t13,
            governance_version=gov,
            reproducibility_record=rec,
            certificate=cert,
            policy_version_match=policy_match,
        )

    @classmethod
    def verify_reproducibility(
        cls,
        record: ReproducibilityRecord,
        expected_status: Optional[IntegrityStatus] = None,
    ) -> bool:
        """
        Validates that a ReproducibilityRecord's snapshot hash is intact, and when replayed,
        yields the exact recorded integrity outcome.
        """
        if not record.verify_input_hash():
            return False

        snapshot = ReplaySnapshot(
            replay_id=f"audit-{record.record_id}",
            transaction_id=record.transaction_id,
            contract=record.intent,
            events=record.events,
            evidence=record.evidence,
            state_transitions=record.state_transitions,
            reference_time=record.reference_time,
            rules_version=record.rules_version,
        )

        result = ReplayEngine.replay(snapshot)
        if expected_status is not None:
            return result.replayed_integrity_result.status == expected_status
        return result.replayed_integrity_result.status == record.recorded_result.status
