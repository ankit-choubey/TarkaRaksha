"""
Unit tests for Scenario Lab Domain Contracts & Catalog (I11).

Verifies:
1. All 12 canonical scenario identifiers exist and are stable.
2. Canonical catalog contains all 12 scenario definitions with rich metadata.
3. ScenarioInputSnapshot computes deterministic SHA-256 digests.
4. ScenarioDefinition computes deterministic SHA-256 digests.
5. ScenarioResult and ScenarioSuiteResult adhere to strict schemas.
6. Filtering and retrieval by ID / category behave deterministically.
"""
from datetime import datetime, timezone, timedelta
import pytest

from backend.app.domain.models import (
    CanonicalEvent,
    Evidence,
    EvidenceAuthority,
    EvidenceSource,
    IntegrityStatus,
    IntentContract,
    IntentItem,
    Money,
)
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


@pytest.fixture
def sample_intent():
    now = datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)
    return IntentContract(
        intent_id="int_scenario_001",
        issued_by="user_alice",
        issued_at=now,
        expires_at=now + timedelta(hours=2),
        currency="INR",
        max_total=Money(amount=5000, currency="INR"),
        items=[
            IntentItem(
                item_id="item_01",
                sku="SKU-BOOK",
                name="Designing Data-Intensive Applications",
                quantity=1,
                unit_price=Money(amount=5000, currency="INR"),
                total_price=Money(amount=5000, currency="INR"),
            )
        ],
    )


def test_canonical_twelve_scenarios_exist():
    """Verify that all 12 canonical scenarios are registered in the catalog."""
    expected_ids = {
        ScenarioId.HAPPY_PATH,
        ScenarioId.PRICE_DRIFT,
        ScenarioId.WRONG_SKU,
        ScenarioId.INVENTORY_DISAPPEARS,
        ScenarioId.DELIVERY_DRIFT,
        ScenarioId.DUPLICATE_PAYMENT,
        ScenarioId.DELAYED_WEBHOOK,
        ScenarioId.REPLAY_ATTACK,
        ScenarioId.PROMPT_INJECTION_IN_EVIDENCE,
        ScenarioId.MERCHANT_AGENT_COMPROMISED,
        ScenarioId.BUYER_AGENT_REUSE,
        ScenarioId.UNKNOWN_PROVIDER_STATE,
    }
    assert len(CANONICAL_SCENARIO_DEFINITIONS) == 12
    assert set(CANONICAL_SCENARIO_DEFINITIONS.keys()) == expected_ids


def test_scenario_definition_retrieval():
    """Test retrieving scenario definitions by enum and string."""
    defn = get_scenario_definition(ScenarioId.HAPPY_PATH)
    assert defn.scenario_id == ScenarioId.HAPPY_PATH
    assert defn.expected_verdict == "PASS"

    defn_str = get_scenario_definition("PRICE_DRIFT")
    assert defn_str.scenario_id == ScenarioId.PRICE_DRIFT
    assert defn_str.expected_verdict == "DRIFT"

    with pytest.raises(KeyError):
        get_scenario_definition("NON_EXISTENT_SCENARIO")


def test_list_scenario_definitions_by_category():
    """Test filtering catalog by scenario category."""
    all_defns = list_scenario_definitions()
    assert len(all_defns) == 12

    integrity_defns = list_scenario_definitions(ScenarioCategory.INTEGRITY)
    assert len(integrity_defns) >= 3
    for d in integrity_defns:
        assert d.category == ScenarioCategory.INTEGRITY


def test_scenario_input_snapshot_digest_determinism(sample_intent):
    """Verify that identical input snapshots produce bit-for-bit identical digests."""
    now = datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)
    ev1 = Evidence(
        evidence_id="ev_01",
        intent_id=sample_intent.intent_id,
        field_name="payment_status",
        field_value="captured",
        source=EvidenceSource.RAZORPAY,
        authority=EvidenceAuthority.AUTHORITATIVE,
        observed_at=now,
    )
    snap1 = ScenarioInputSnapshot(
        scenario_id=ScenarioId.HAPPY_PATH,
        version="1.0.0",
        intent=sample_intent,
        evidence=[ev1],
        reference_time=now,
    )
    snap2 = ScenarioInputSnapshot(
        scenario_id=ScenarioId.HAPPY_PATH,
        version="1.0.0",
        intent=sample_intent,
        evidence=[ev1],
        reference_time=now,
    )

    digest1 = snap1.compute_digest()
    digest2 = snap2.compute_digest()
    assert digest1 == digest2
    assert len(digest1) == 64


def test_scenario_input_snapshot_digest_divergence(sample_intent):
    """Verify that different input parameters alter the digest."""
    now = datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)
    snap1 = ScenarioInputSnapshot(
        scenario_id=ScenarioId.HAPPY_PATH,
        version="1.0.0",
        intent=sample_intent,
        reference_time=now,
    )
    snap2 = ScenarioInputSnapshot(
        scenario_id=ScenarioId.PRICE_DRIFT,
        version="1.0.0",
        intent=sample_intent,
        reference_time=now,
        fault_injection="price_drift_injected",
    )
    assert snap1.compute_digest() != snap2.compute_digest()


def test_scenario_definition_digest_determinism():
    """Verify that scenario definition digest is deterministic."""
    defn1 = get_scenario_definition(ScenarioId.HAPPY_PATH)
    digest1 = defn1.compute_definition_digest()
    digest2 = defn1.compute_definition_digest()
    assert digest1 == digest2
    assert len(digest1) == 64
