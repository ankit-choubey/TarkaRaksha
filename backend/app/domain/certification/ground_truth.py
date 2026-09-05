"""
Canonical Ground Truth Registry for TarkaRaksha Scenario Certification (I12).

Defines the 12 immutable ground truth specifications corresponding to the
canonical I11 scenarios.
"""
from typing import Dict, List, Optional
from backend.app.domain.models import EvidenceAuthority
from backend.app.domain.scenario.contracts import ScenarioId
from backend.app.domain.certification.contracts import GroundTruthDefinition


CANONICAL_GROUND_TRUTH: Dict[ScenarioId, GroundTruthDefinition] = {
    ScenarioId.HAPPY_PATH: GroundTruthDefinition(
        scenario_id=ScenarioId.HAPPY_PATH,
        ground_truth_id="gt_01_happy_path",
        description="Clean, valid intent and capture leading to deterministic PASS without MRDP or abstention.",
        expected_integrity_verdict="PASS",
        expected_security_state=None,
        expected_terminal_state=None,
        expected_mrdp_presence=False,
        expected_abstention=False,
        expected_violation_codes=[],
        expected_authority_level=EvidenceAuthority.AUTHORITATIVE,
        metadata={"category": "HAPPY_PATH"},
    ),
    ScenarioId.PRICE_DRIFT: GroundTruthDefinition(
        scenario_id=ScenarioId.PRICE_DRIFT,
        ground_truth_id="gt_02_price_drift",
        description="Payment exceeds intent maximum total; triggers economic DRIFT and requires cryptographic MRDP proof.",
        expected_integrity_verdict="DRIFT",
        expected_security_state=None,
        expected_terminal_state=None,
        expected_mrdp_presence=True,
        expected_abstention=False,
        expected_violation_codes=["exceeded authorized", "amount"],
        expected_authority_level=EvidenceAuthority.AUTHORITATIVE,
        metadata={"category": "INTEGRITY"},
    ),
    ScenarioId.WRONG_SKU: GroundTruthDefinition(
        scenario_id=ScenarioId.WRONG_SKU,
        ground_truth_id="gt_03_wrong_sku",
        description="Observed SKU does not match authorized SKU or allowed substitutions; triggers semantic DRIFT and MRDP proof.",
        expected_integrity_verdict="DRIFT",
        expected_security_state=None,
        expected_terminal_state=None,
        expected_mrdp_presence=True,
        expected_abstention=False,
        expected_violation_codes=["unauthorized", "SKU"],
        expected_authority_level=EvidenceAuthority.AUTHORITATIVE,
        metadata={"category": "INTEGRITY"},
    ),
    ScenarioId.INVENTORY_DISAPPEARS: GroundTruthDefinition(
        scenario_id=ScenarioId.INVENTORY_DISAPPEARS,
        ground_truth_id="gt_04_inventory_disappears",
        description="Declared merchant inventory capability fails transaction reality due to 0 executed stock; triggers DRIFT.",
        expected_integrity_verdict="DRIFT",
        expected_security_state=None,
        expected_terminal_state=None,
        expected_mrdp_presence=True,
        expected_abstention=False,
        expected_violation_codes=["MissingAuthorizedItem"],
        metadata={"category": "AGENTIC"},
    ),
    ScenarioId.DELIVERY_DRIFT: GroundTruthDefinition(
        scenario_id=ScenarioId.DELIVERY_DRIFT,
        ground_truth_id="gt_05_delivery_drift",
        description="Fulfillment delivery estimate exceeds authorized intent expiry; triggers temporal DRIFT and MRDP proof.",
        expected_integrity_verdict="DRIFT",
        expected_security_state=None,
        expected_terminal_state=None,
        expected_mrdp_presence=True,
        expected_abstention=False,
        expected_violation_codes=["ExpiredExecution"],
        metadata={"category": "INTEGRITY"},
    ),
    ScenarioId.DUPLICATE_PAYMENT: GroundTruthDefinition(
        scenario_id=ScenarioId.DUPLICATE_PAYMENT,
        ground_truth_id="gt_06_duplicate_payment",
        description="Multiple capture events observed exceeding authorized capture count; triggers temporal DRIFT and MRDP proof.",
        expected_integrity_verdict="DRIFT",
        expected_security_state=None,
        expected_terminal_state=None,
        expected_mrdp_presence=True,
        expected_abstention=False,
        expected_violation_codes=["DoubleExecutionRisk"],
        metadata={"category": "SECURITY"},
    ),
    ScenarioId.DELAYED_WEBHOOK: GroundTruthDefinition(
        scenario_id=ScenarioId.DELAYED_WEBHOOK,
        ground_truth_id="gt_07_delayed_webhook",
        description="Provider capture timestamp is later than intent expiry; triggers temporal DRIFT and MRDP proof.",
        expected_integrity_verdict="DRIFT",
        expected_security_state=None,
        expected_terminal_state=None,
        expected_mrdp_presence=True,
        expected_abstention=False,
        expected_violation_codes=["ExpiredExecution"],
        metadata={"category": "PROVIDER"},
    ),
    ScenarioId.REPLAY_ATTACK: GroundTruthDefinition(
        scenario_id=ScenarioId.REPLAY_ATTACK,
        ground_truth_id="gt_08_replay_attack",
        description="Historical event replay with altered state detected by ReplayEngine; results in MISMATCH.",
        expected_integrity_verdict=None,
        expected_security_state="MISMATCH",
        expected_terminal_state=None,
        expected_mrdp_presence=False,
        expected_abstention=False,
        expected_violation_codes=[],
        metadata={"category": "SECURITY"},
    ),
    ScenarioId.PROMPT_INJECTION_IN_EVIDENCE: GroundTruthDefinition(
        scenario_id=ScenarioId.PROMPT_INJECTION_IN_EVIDENCE,
        ground_truth_id="gt_09_prompt_injection",
        description="Advisory evidence injection string is treated as raw data; missing authoritative payment yields UNKNOWN and abstention.",
        expected_integrity_verdict="UNKNOWN",
        expected_security_state=None,
        expected_terminal_state=None,
        expected_mrdp_presence=False,
        expected_abstention=True,
        expected_violation_codes=[],
        expected_authority_level=EvidenceAuthority.ADVISORY,
        metadata={"category": "EVIDENCE"},
    ),
    ScenarioId.MERCHANT_AGENT_COMPROMISED: GroundTruthDefinition(
        scenario_id=ScenarioId.MERCHANT_AGENT_COMPROMISED,
        ground_truth_id="gt_10_merchant_compromised",
        description="Compromised merchant attests capture without gateway confirmation; yields UNKNOWN and abstention.",
        expected_integrity_verdict="UNKNOWN",
        expected_security_state=None,
        expected_terminal_state=None,
        expected_mrdp_presence=False,
        expected_abstention=True,
        expected_violation_codes=[],
        expected_authority_level=EvidenceAuthority.MERCHANT_ATTESTED,
        metadata={"category": "AGENTIC"},
    ),
    ScenarioId.BUYER_AGENT_REUSE: GroundTruthDefinition(
        scenario_id=ScenarioId.BUYER_AGENT_REUSE,
        ground_truth_id="gt_11_buyer_agent_reuse",
        description="Buyer agent attempting cross-transaction context reuse is caught and rejected by binding verification.",
        expected_integrity_verdict=None,
        expected_security_state="REJECTED",
        expected_terminal_state=None,
        expected_mrdp_presence=False,
        expected_abstention=False,
        expected_violation_codes=["CROSS_TRANSACTION_REUSE", "TRANSACTION_MISMATCH"],
        metadata={"category": "SECURITY"},
    ),
    ScenarioId.UNKNOWN_PROVIDER_STATE: GroundTruthDefinition(
        scenario_id=ScenarioId.UNKNOWN_PROVIDER_STATE,
        ground_truth_id="gt_12_unknown_provider_state",
        description="Pending provider status without capture evidence; system strictly preserves UNKNOWN and abstains from capture.",
        expected_integrity_verdict="UNKNOWN",
        expected_security_state=None,
        expected_terminal_state=None,
        expected_mrdp_presence=False,
        expected_abstention=True,
        expected_violation_codes=[],
        metadata={"category": "PROVIDER"},
    ),
}


def get_ground_truth(scenario_id: ScenarioId | str) -> GroundTruthDefinition:
    """Retrieves ground truth definition by scenario enum or string identifier."""
    if isinstance(scenario_id, str):
        try:
            scenario_id = ScenarioId(scenario_id)
        except ValueError:
            raise KeyError(f"Unknown scenario ID '{scenario_id}'")
    if scenario_id not in CANONICAL_GROUND_TRUTH:
        raise KeyError(f"No ground truth registered for scenario '{scenario_id}'")
    return CANONICAL_GROUND_TRUTH[scenario_id]


def list_ground_truths() -> List[GroundTruthDefinition]:
    """Returns all canonical ground truth declarations in stable order."""
    return list(CANONICAL_GROUND_TRUTH.values())
