"""
Scenario Lab Service for TarkaRaksha (I11).

Provides high-level coordination for running scenarios individually or as a complete suite:
- run_scenario(scenario_id, reference_time)
- run_all(reference_time)
- get_catalog()
"""
from datetime import datetime, timezone
import logging
from typing import Dict, List, Optional

from backend.app.domain.scenario.contracts import (
    ScenarioCategory,
    ScenarioDefinition,
    ScenarioId,
    ScenarioInputSnapshot,
    ScenarioResult,
    ScenarioStatus,
    ScenarioSuiteResult,
)
from backend.app.domain.scenario.catalog import (
    CANONICAL_SCENARIO_DEFINITIONS,
    get_scenario_definition,
    list_scenario_definitions,
)
from backend.app.services.scenario.definitions import build_scenario_snapshot
from backend.app.services.scenario.runner import ScenarioRunner

logger = logging.getLogger(__name__)


class ScenarioLabService:
    """
    Control Plane service for executing deterministic scenarios against the
    authoritative TarkaRaksha pipeline.
    """

    def __init__(self):
        self._runner = ScenarioRunner

    def get_catalog(
        self,
        category: Optional[ScenarioCategory] = None,
    ) -> List[ScenarioDefinition]:
        """Returns all canonical scenario definitions, optionally filtered by category."""
        return list_scenario_definitions(category=category)

    def run_scenario(
        self,
        scenario_id: ScenarioId | str,
        reference_time: Optional[datetime] = None,
        snapshot_override: Optional[ScenarioInputSnapshot] = None,
    ) -> ScenarioResult:
        """
        Runs a single scenario deterministically and returns its ScenarioResult.
        """
        if isinstance(scenario_id, str):
            scenario_id = ScenarioId(scenario_id)

        definition = get_scenario_definition(scenario_id)
        snapshot = snapshot_override or build_scenario_snapshot(scenario_id, reference_time=reference_time)

        logger.info("Executing scenario %s (version=%s)", scenario_id.value, definition.version)
        result = self._runner.run(definition=definition, snapshot=snapshot)
        logger.info(
            "Completed scenario %s: status=%s, expected=%s, actual=%s",
            scenario_id.value,
            result.scenario_status.value,
            result.expected_verdict,
            result.actual_verdict,
        )
        return result

    def run_all(
        self,
        category: Optional[ScenarioCategory] = None,
        reference_time: Optional[datetime] = None,
    ) -> ScenarioSuiteResult:
        """
        Runs all registered canonical scenarios (or those in a category) and compiles a ScenarioSuiteResult.
        """
        ref_time = reference_time or datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)
        definitions = self.get_catalog(category=category)

        results: List[ScenarioResult] = []
        passed_count = 0
        failed_count = 0

        for defn in definitions:
            snapshot = build_scenario_snapshot(defn.scenario_id, reference_time=ref_time)
            res = self._runner.run(definition=defn, snapshot=snapshot)
            results.append(res)
            if res.scenario_status == ScenarioStatus.PASS:
                passed_count += 1
            else:
                failed_count += 1

        total = len(results)
        is_all_passed = (passed_count == total and total > 0)
        summary = (
            f"Scenario Lab Suite: {passed_count}/{total} passed "
            f"({failed_count} failed) at {ref_time.isoformat()}"
        )

        return ScenarioSuiteResult(
            suite_version="1.0.0",
            total_scenarios=total,
            passed_scenarios=passed_count,
            failed_scenarios=failed_count,
            results=results,
            is_all_passed=is_all_passed,
            summary=summary,
        )
