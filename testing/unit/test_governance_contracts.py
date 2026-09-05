"""
Unit tests for Governance & Policy Version Contracts (I3.1).
"""
import pytest
from backend.app.domain.governance import (
    DEFAULT_POLICY_VERSION,
    DEFAULT_RULES_VERSION,
    GovernanceVersion,
)


def test_governance_version_defaults():
    gv = GovernanceVersion()
    assert gv.rules_version == DEFAULT_RULES_VERSION
    assert gv.policy_version == DEFAULT_POLICY_VERSION
    assert gv.description is None
    assert gv.parameters == {}


def test_governance_version_custom_attribution():
    gv = GovernanceVersion(
        rules_version="integrity-2.1.0",
        policy_version="merchant-policy-v4-electronics",
        description="Updated electronics return threshold",
        parameters={"max_price_tolerance_bps": 50},
    )
    assert gv.rules_version == "integrity-2.1.0"
    assert gv.policy_version == "merchant-policy-v4-electronics"
    assert gv.parameters["max_price_tolerance_bps"] == 50


def test_governance_version_distinguishability():
    gv1 = GovernanceVersion(rules_version="integrity-1.0.0", policy_version="merchant-policy-1")
    gv2 = GovernanceVersion(rules_version="integrity-1.0.0", policy_version="merchant-policy-2")
    gv3 = GovernanceVersion(rules_version="integrity-2.0.0", policy_version="merchant-policy-1")

    assert gv1 != gv2
    assert gv1 != gv3
    assert gv2 != gv3


def test_governance_version_rejects_empty_or_whitespace():
    with pytest.raises(ValueError, match="cannot be empty or whitespace"):
        GovernanceVersion(rules_version="  ")

    with pytest.raises(ValueError, match="cannot be empty or whitespace"):
        GovernanceVersion(policy_version="")


def test_governance_version_immutability():
    gv = GovernanceVersion()
    with pytest.raises(Exception):
        gv.rules_version = "mutated-1.0"
