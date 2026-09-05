"""
Ground-Truth Certification Service for TarkaRaksha (I12).

Provides high-level coordination for certifying scenarios against immutable ground truth:
- certify_scenario(scenario_id, reference_time, snapshot_override)
- certify_all(reference_time)
- get_certification_matrix(reference_time)
- get_ground_truth(scenario_id)
- list_ground_truths()
"""
from datetime import datetime, timezone
import logging
from typing import Dict, List, Optional

from backend.app.domain.scenario.contracts import (
    ScenarioCategory,
    ScenarioId,
    ScenarioInputSnapshot,
)
from backend.app.domain.scenario.catalog import get_scenario_definition
from backend.app.domain.certification.contracts import (
    CertificationMatrixRow,
    CertificationResult,
    CertificationStatus,
    CertificationSuiteResult,
    GroundTruthDefinition,
)
from backend.app.domain.certification.ground_truth import (
    CANONICAL_GROUND_TRUTH,
    get_ground_truth,
    list_ground_truths,
)
from backend.app.domain.certification.comparator import CertificationComparator
from backend.app.services.scenario.definitions import build_scenario_snapshot
from backend.app.services.scenario.service import ScenarioLabService

logger = logging.getLogger(__name__)


class GroundTruthCertificationService:
    """
    Control Plane service for certifying authoritative TarkaRaksha pipeline execution
    against immutable ground-truth contracts (I12).
    """

    def __init__(self, scenario_service: Optional[ScenarioLabService] = None):
        self._scenario_service = scenario_service or ScenarioLabService()
        self._comparator = CertificationComparator

    def get_ground_truth(self, scenario_id: ScenarioId | str) -> GroundTruthDefinition:
        """Retrieves ground truth definition for a scenario."""
        return get_ground_truth(scenario_id)

    def list_ground_truths(self) -> List[GroundTruthDefinition]:
        """Lists all registered ground truth definitions."""
        return list_ground_truths()

    def certify_scenario(
        self,
        scenario_id: ScenarioId | str,
        reference_time: Optional[datetime] = None,
        snapshot_override: Optional[ScenarioInputSnapshot] = None,
    ) -> CertificationResult:
        """
        Executes a scenario through the authoritative pipeline and certifies the result
        against canonical ground truth.
        """
        if isinstance(scenario_id, str):
            scenario_id = ScenarioId(scenario_id)

        ref_time = reference_time or datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)
        ground_truth = self.get_ground_truth(scenario_id)
        snapshot = snapshot_override or build_scenario_snapshot(scenario_id, reference_time=ref_time)

        logger.info("Certifying scenario %s against ground truth %s", scenario_id.value, ground_truth.ground_truth_id)

        # Execute through authoritative ScenarioLabService pipeline
        actual_result = self._scenario_service.run_scenario(
            scenario_id=scenario_id,
            reference_time=ref_time,
            snapshot_override=snapshot,
        )

        # Deterministic comparison
        cert_result = self._comparator.compare(
            ground_truth=ground_truth,
            actual_result=actual_result,
            snapshot=snapshot,
            certified_at=ref_time,
        )

        logger.info(
            "Certification outcome for %s: %s (hash=%s)",
            scenario_id.value,
            cert_result.overall_status.value,
            cert_result.certification_hash[:8],
        )
        return cert_result

    def certify_all(
        self,
        reference_time: Optional[datetime] = None,
    ) -> CertificationSuiteResult:
        """
        Executes all canonical scenarios and certifies each against its ground truth,
        producing a typed CertificationSuiteResult with a certification matrix.
        """
        ref_time = reference_time or datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)

        results: List[CertificationResult] = []
        matrix_rows: List[CertificationMatrixRow] = []

        certified_count = 0
        failed_count = 0
        invalid_count = 0

        # Execute in canonical scenario order
        for scenario_id in CANONICAL_GROUND_TRUTH.keys():
            res = self.certify_scenario(scenario_id, reference_time=ref_time)
            results.append(res)

            row = CertificationMatrixRow(
                scenario_id=res.scenario_id,
                ground_truth_id=res.ground_truth_id,
                actual_verdict=str(res.actual_result.get("actual_verdict", "UNKNOWN")),
                expected_verdict=str(res.expected_result.get("expected_integrity_verdict", "UNKNOWN")),
                integrity_match=res.integrity_match,
                security_match=res.security_match,
                state_match=res.state_match,
                mrdp_match=res.mrdp_match,
                abstention_match=res.abstention_match,
                violation_match=res.violation_match,
                authority_match=res.authority_match,
                overall_certification=res.overall_status.value,
                certification_hash=res.certification_hash,
            )
            matrix_rows.append(row)

            if res.overall_status == CertificationStatus.CERTIFIED:
                certified_count += 1
            elif res.overall_status == CertificationStatus.FAILED:
                failed_count += 1
            else:
                invalid_count += 1

        total = len(results)
        is_fully_certified = (certified_count == total and total > 0)
        summary = (
            f"Ground-Truth Certification Suite: {certified_count}/{total} certified "
            f"({failed_count} failed, {invalid_count} invalid) at {ref_time.isoformat()}"
        )

        return CertificationSuiteResult(
            suite_version="1.0.0",
            total_scenarios=total,
            certified_scenarios=certified_count,
            failed_scenarios=failed_count,
            invalid_scenarios=invalid_count,
            results=results,
            is_fully_certified=is_fully_certified,
            summary=summary,
            matrix=matrix_rows,
        )

    def get_certification_matrix(
        self,
        reference_time: Optional[datetime] = None,
    ) -> List[CertificationMatrixRow]:
        """Runs all certifications and returns solely the machine-readable matrix rows."""
        suite_res = self.certify_all(reference_time=reference_time)
        return suite_res.matrix
