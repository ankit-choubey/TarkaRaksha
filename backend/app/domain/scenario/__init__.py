"""
Scenario Domain Package for TarkaRaksha (I11).
"""
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
    get_scenario_catalog,
    get_scenario_definition,
    list_scenario_definitions,
)

__all__ = [
    "ScenarioCategory",
    "ScenarioDefinition",
    "ScenarioId",
    "ScenarioInputSnapshot",
    "ScenarioResult",
    "ScenarioStatus",
    "ScenarioSuiteResult",
    "CANONICAL_SCENARIO_DEFINITIONS",
    "get_scenario_catalog",
    "get_scenario_definition",
    "list_scenario_definitions",
]
