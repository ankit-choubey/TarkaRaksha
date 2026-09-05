"""
Deterministic Certification Comparator for TarkaRaksha (I12).

Compares authoritative ScenarioResult outputs against declared GroundTruthDefinition
contracts across all verification dimensions:
- integrity_verdict
- security_state
- terminal_state
- mrdp_presence
- abstention
- violation_codes
- authority_level

Invariants:
1. Strict Hash Integrity: Validates input_snapshot_hash and generates canonical certification digests.
2. INVALID Separation: Mismatched scenarios, tampered hashes, or corrupted inputs produce INVALID (not FAILED).
3. Zero Heuristics: Exact deterministic evaluation; no statistical scoring or probability.
4. Pure Function: Zero side-effects, zero live I/O.
"""
from datetime import datetime, timezone
import hashlib
import json
import logging
from typing import Any, Dict, List, Optional

from backend.app.domain.scenario.contracts import (
    ScenarioInputSnapshot,
    ScenarioResult,
)
from backend.app.domain.certification.contracts import (
    CertificationResult,
    CertificationStatus,
    GroundTruthDefinition,
)

logger = logging.getLogger(__name__)


def compute_actual_result_hash(result: ScenarioResult) -> str:
    """Computes a deterministic SHA-256 digest of the actual scenario outcome."""
    canonical_data = {
        "scenario_id": result.scenario_id.value,
        "scenario_version": result.scenario_version,
        "input_snapshot_hash": result.input_snapshot_hash,
        "actual_verdict": result.actual_verdict,
        "scenario_status": result.scenario_status.value,
        "integrity_status": result.integrity_status.value if result.integrity_status else None,
        "mrdp_digest": result.mrdp_digest,
        "violations": sorted(result.violations),
        "evidence_count": result.evidence_count,
        "events_processed": result.events_processed,
    }
    encoded = json.dumps(canonical_data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class CertificationComparator:
    """
    Authoritative comparator verifying scenario execution results against declared ground truth.
    """

    @classmethod
    def compare(
        cls,
        ground_truth: GroundTruthDefinition,
        actual_result: ScenarioResult,
        snapshot: ScenarioInputSnapshot,
        certified_at: Optional[datetime] = None,
    ) -> CertificationResult:
        """
        Executes multi-dimensional verification between ground truth and actual engine outcome.
        """
        cert_time = certified_at or actual_result.reference_time
        if cert_time.tzinfo is None:
            cert_time = cert_time.replace(tzinfo=timezone.utc)

        certification_id = f"cert_{ground_truth.scenario_id.value}"
        failure_reasons: List[str] = []

        gt_hash = ground_truth.compute_ground_truth_hash()
        snapshot_hash = snapshot.compute_digest()
        actual_hash = compute_actual_result_hash(actual_result)

        # ----------------------------------------------------------------------
        # 1. Certification Validity Verification (INVALID Checks)
        # ----------------------------------------------------------------------
        # Check scenario ID alignment
        if ground_truth.scenario_id != actual_result.scenario_id:
            failure_reasons.append(
                f"CrossScenarioReuseError: Ground truth scenario '{ground_truth.scenario_id.value}' "
                f"does not match actual result scenario '{actual_result.scenario_id.value}'"
            )
            return cls._build_invalid_result(
                certification_id=certification_id,
                ground_truth=ground_truth,
                actual_result=actual_result,
                snapshot_hash=snapshot_hash,
                gt_hash=gt_hash,
                actual_hash=actual_hash,
                failure_reasons=failure_reasons,
                certified_at=cert_time,
            )

        if snapshot.scenario_id != ground_truth.scenario_id:
            failure_reasons.append(
                f"CrossScenarioSnapshotError: Snapshot scenario '{snapshot.scenario_id.value}' "
                f"does not match ground truth scenario '{ground_truth.scenario_id.value}'"
            )
            return cls._build_invalid_result(
                certification_id=certification_id,
                ground_truth=ground_truth,
                actual_result=actual_result,
                snapshot_hash=snapshot_hash,
                gt_hash=gt_hash,
                actual_hash=actual_hash,
                failure_reasons=failure_reasons,
                certified_at=cert_time,
            )

        # Check snapshot hash integrity
        if actual_result.input_snapshot_hash != snapshot_hash:
            failure_reasons.append(
                f"SnapshotHashMismatchError: Actual result snapshot hash '{actual_result.input_snapshot_hash}' "
                f"does not match computed snapshot hash '{snapshot_hash}'"
            )
            return cls._build_invalid_result(
                certification_id=certification_id,
                ground_truth=ground_truth,
                actual_result=actual_result,
                snapshot_hash=snapshot_hash,
                gt_hash=gt_hash,
                actual_hash=actual_hash,
                failure_reasons=failure_reasons,
                certified_at=cert_time,
            )

        # ----------------------------------------------------------------------
        # 2. Multi-Dimensional Dimensional Evaluation
        # ----------------------------------------------------------------------
        # Dimension A: Integrity Verdict
        if ground_truth.expected_integrity_verdict is not None:
            integrity_match = (actual_result.actual_verdict == ground_truth.expected_integrity_verdict)
            if not integrity_match:
                failure_reasons.append(
                    f"IntegrityMismatch: Expected '{ground_truth.expected_integrity_verdict}', "
                    f"got '{actual_result.actual_verdict}'"
                )
        else:
            integrity_match = True

        # Dimension B: Security State
        if ground_truth.expected_security_state is not None:
            security_match = (actual_result.actual_verdict == ground_truth.expected_security_state)
            if not security_match:
                failure_reasons.append(
                    f"SecurityMismatch: Expected security state '{ground_truth.expected_security_state}', "
                    f"got '{actual_result.actual_verdict}'"
                )
        else:
            security_match = True

        # Dimension C: Terminal State
        if ground_truth.expected_terminal_state is not None:
            state_match = (actual_result.transaction_state == ground_truth.expected_terminal_state)
            if not state_match:
                failure_reasons.append(
                    f"StateMismatch: Expected state '{ground_truth.expected_terminal_state}', "
                    f"got '{actual_result.transaction_state}'"
                )
        else:
            state_match = True

        # Dimension D: MRDP Presence
        has_mrdp = bool(actual_result.mrdp_digest)
        mrdp_match = (has_mrdp == ground_truth.expected_mrdp_presence)
        if not mrdp_match:
            failure_reasons.append(
                f"MRDPMismatch: Expected MRDP presence={ground_truth.expected_mrdp_presence}, "
                f"observed={has_mrdp}"
            )

        # Dimension E: Abstention (UNKNOWN states require abstention from automated capture)
        actual_abstains = (actual_result.actual_verdict == "UNKNOWN")
        abstention_match = (actual_abstains == ground_truth.expected_abstention)
        if not abstention_match:
            failure_reasons.append(
                f"AbstentionMismatch: Expected abstention={ground_truth.expected_abstention}, "
                f"observed={actual_abstains}"
            )

        # Dimension F: Violation Codes / Keywords
        if ground_truth.expected_violation_codes:
            all_viols_str = " ".join(actual_result.violations).lower()
            violation_match = any(code.lower() in all_viols_str for code in ground_truth.expected_violation_codes)
            if not violation_match:
                failure_reasons.append(
                    f"ViolationMismatch: None of expected violation keywords {ground_truth.expected_violation_codes} "
                    f"were found in actual violations: {actual_result.violations}"
                )
        else:
            violation_match = True

        # Dimension G: Authority Level
        if ground_truth.expected_authority_level is not None:
            authority_match = any(e.authority == ground_truth.expected_authority_level for e in snapshot.evidence)
            if not authority_match:
                failure_reasons.append(
                    f"AuthorityMismatch: Expected evidence with authority level '{ground_truth.expected_authority_level.value}'"
                )
        else:
            authority_match = True

        # ----------------------------------------------------------------------
        # 3. Overall Certification Status
        # ----------------------------------------------------------------------
        is_all_match = (
            integrity_match
            and security_match
            and state_match
            and mrdp_match
            and abstention_match
            and violation_match
            and authority_match
        )

        if actual_result.actual_verdict == "ERROR":
            overall_status = CertificationStatus.FAILED
            failure_reasons.append(f"ExecutionError: Scenario terminated with unhandled error")
        elif is_all_match:
            overall_status = CertificationStatus.CERTIFIED
        else:
            overall_status = CertificationStatus.FAILED

        # ----------------------------------------------------------------------
        # 4. Canonical Certification Hash
        # ----------------------------------------------------------------------
        cert_hash = cls._compute_certification_hash(
            certification_id=certification_id,
            scenario_id=ground_truth.scenario_id.value,
            ground_truth_id=ground_truth.ground_truth_id,
            overall_status=overall_status.value,
            integrity_match=integrity_match,
            security_match=security_match,
            state_match=state_match,
            mrdp_match=mrdp_match,
            abstention_match=abstention_match,
            violation_match=violation_match,
            authority_match=authority_match,
            snapshot_hash=snapshot_hash,
            gt_hash=gt_hash,
            actual_hash=actual_hash,
            certified_at=cert_time.isoformat(),
        )

        return CertificationResult(
            certification_id=certification_id,
            scenario_id=ground_truth.scenario_id,
            ground_truth_id=ground_truth.ground_truth_id,
            version="1.0.0",
            integrity_match=integrity_match,
            security_match=security_match,
            state_match=state_match,
            mrdp_match=mrdp_match,
            abstention_match=abstention_match,
            violation_match=violation_match,
            authority_match=authority_match,
            overall_status=overall_status,
            failure_reasons=failure_reasons,
            expected_result={
                "integrity_verdict": ground_truth.expected_integrity_verdict,
                "security_state": ground_truth.expected_security_state,
                "terminal_state": ground_truth.expected_terminal_state.value if ground_truth.expected_terminal_state else None,
                "mrdp_presence": ground_truth.expected_mrdp_presence,
                "abstention": ground_truth.expected_abstention,
            },
            actual_result={
                "verdict": actual_result.actual_verdict,
                "has_mrdp": bool(actual_result.mrdp_digest),
                "abstains": actual_abstains,
                "violations": actual_result.violations,
            },
            input_snapshot_hash=snapshot_hash,
            ground_truth_hash=gt_hash,
            actual_result_hash=actual_hash,
            certification_hash=cert_hash,
            certified_at=cert_time,
        )

    @classmethod
    def _build_invalid_result(
        cls,
        certification_id: str,
        ground_truth: GroundTruthDefinition,
        actual_result: ScenarioResult,
        snapshot_hash: str,
        gt_hash: str,
        actual_hash: str,
        failure_reasons: List[str],
        certified_at: datetime,
    ) -> CertificationResult:
        """Helper to construct an INVALID certification result."""
        cert_hash = cls._compute_certification_hash(
            certification_id=certification_id,
            scenario_id=ground_truth.scenario_id.value,
            ground_truth_id=ground_truth.ground_truth_id,
            overall_status=CertificationStatus.INVALID.value,
            integrity_match=False,
            security_match=False,
            state_match=False,
            mrdp_match=False,
            abstention_match=False,
            violation_match=False,
            authority_match=False,
            snapshot_hash=snapshot_hash,
            gt_hash=gt_hash,
            actual_hash=actual_hash,
            certified_at=certified_at.isoformat(),
        )
        return CertificationResult(
            certification_id=certification_id,
            scenario_id=ground_truth.scenario_id,
            ground_truth_id=ground_truth.ground_truth_id,
            version="1.0.0",
            integrity_match=False,
            security_match=False,
            state_match=False,
            mrdp_match=False,
            abstention_match=False,
            violation_match=False,
            authority_match=False,
            overall_status=CertificationStatus.INVALID,
            failure_reasons=failure_reasons,
            expected_result={},
            actual_result={"verdict": actual_result.actual_verdict},
            input_snapshot_hash=snapshot_hash,
            ground_truth_hash=gt_hash,
            actual_result_hash=actual_hash,
            certification_hash=cert_hash,
            certified_at=certified_at,
        )

    @classmethod
    def _compute_certification_hash(
        cls,
        certification_id: str,
        scenario_id: str,
        ground_truth_id: str,
        overall_status: str,
        integrity_match: bool,
        security_match: bool,
        state_match: bool,
        mrdp_match: bool,
        abstention_match: bool,
        violation_match: bool,
        authority_match: bool,
        snapshot_hash: str,
        gt_hash: str,
        actual_hash: str,
        certified_at: str,
    ) -> str:
        """Computes a tamper-evident SHA-256 digest of the certification record."""
        canonical_data = {
            "certification_id": certification_id,
            "scenario_id": scenario_id,
            "ground_truth_id": ground_truth_id,
            "overall_status": overall_status,
            "integrity_match": integrity_match,
            "security_match": security_match,
            "state_match": state_match,
            "mrdp_match": mrdp_match,
            "abstention_match": abstention_match,
            "violation_match": violation_match,
            "authority_match": authority_match,
            "snapshot_hash": snapshot_hash,
            "gt_hash": gt_hash,
            "actual_hash": actual_hash,
            "certified_at": certified_at,
        }
        encoded = json.dumps(canonical_data, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()
