"""Unit tests for Innovation I15 — Integrity SLA Metrics domain contracts."""
from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from backend.app.domain.sla.contracts import (
    MetricStatus,
    MetricUnit,
    MetricName,
    SLAPolicy,
    SLAMetric,
    SLAComplianceSummary,
    IntegritySLAMetricsReport,
)


def test_sla_enums():
    """Validates SLA domain enums."""
    assert MetricStatus.MEASURABLE == "MEASURABLE"
    assert MetricStatus.UNKNOWN == "UNKNOWN"
    assert MetricStatus.NOT_APPLICABLE == "NOT_APPLICABLE"
    assert MetricStatus.INVALID == "INVALID"

    assert MetricUnit.MILLISECONDS == "MILLISECONDS"
    assert MetricUnit.RATIO == "RATIO"
    assert MetricUnit.COUNT == "COUNT"
    assert MetricUnit.BOOLEAN == "BOOLEAN"

    assert MetricName.TIME_TO_DETECT == "TIME_TO_DETECT"
    assert MetricName.TIME_TO_PROVE == "TIME_TO_PROVE"
    assert MetricName.TIME_TO_INTERVENE == "TIME_TO_INTERVENE"
    assert MetricName.TIME_TO_REVALIDATE == "TIME_TO_REVALIDATE"
    assert MetricName.TIME_TO_FINAL_DECISION == "TIME_TO_FINAL_DECISION"
    assert MetricName.UNKNOWN_EXPOSURE_DURATION == "UNKNOWN_EXPOSURE_DURATION"
    assert MetricName.CHECKPOINT_COVERAGE_RATIO == "CHECKPOINT_COVERAGE_RATIO"
    assert MetricName.CHECKPOINT_VALID_RATIO == "CHECKPOINT_VALID_RATIO"
    assert MetricName.TRACE_COMPLETENESS_RATIO == "TRACE_COMPLETENESS_RATIO"


def test_sla_policy_defaults_and_validation():
    """Validates SLAPolicy defaults and immutability."""
    policy = SLAPolicy()
    assert policy.policy_id == "default_sla_policy"
    assert policy.governance_version == "gov_v1.0.0"
    assert policy.max_time_to_detect_ms == 5000.0
    assert policy.min_checkpoint_coverage_ratio == 0.75

    with pytest.raises(ValidationError):
        policy.max_time_to_detect_ms = 1000.0  # frozen


def test_sla_metric_measurable_validation():
    """Validates SLAMetric requires value when MEASURABLE, and prohibits value when UNKNOWN/NOT_APPLICABLE/INVALID."""
    dt = datetime.now(timezone.utc)

    # Valid measurable
    m = SLAMetric(
        metric_name=MetricName.TIME_TO_DETECT,
        transaction_id="tx_123",
        status=MetricStatus.MEASURABLE,
        value=150.5,
        unit=MetricUnit.MILLISECONDS,
        threshold=5000.0,
        is_compliant=True,
        calculation_reason="Valid calculation",
    )
    assert m.value == 150.5
    assert m.is_compliant is True

    # Missing value for MEASURABLE raises error
    with pytest.raises(ValidationError):
        SLAMetric(
            metric_name=MetricName.TIME_TO_DETECT,
            transaction_id="tx_123",
            status=MetricStatus.MEASURABLE,
            value=None,
            unit=MetricUnit.MILLISECONDS,
            calculation_reason="No value provided",
        )

    # Value provided for UNKNOWN raises error
    with pytest.raises(ValidationError):
        SLAMetric(
            metric_name=MetricName.TIME_TO_DETECT,
            transaction_id="tx_123",
            status=MetricStatus.UNKNOWN,
            value=100.0,
            unit=MetricUnit.MILLISECONDS,
            calculation_reason="Unknown but value provided",
        )


def test_sla_metric_timezone_validation():
    """Validates that timestamps on SLAMetric must be timezone-aware."""
    naive_dt = datetime(2026, 9, 6, 12, 0, 0)
    with pytest.raises(ValidationError):
        SLAMetric(
            metric_name=MetricName.TIME_TO_DETECT,
            transaction_id="tx_123",
            status=MetricStatus.MEASURABLE,
            value=200.0,
            unit=MetricUnit.MILLISECONDS,
            start_time=naive_dt,
            calculation_reason="Naive start timestamp",
        )


def test_sla_compliance_summary_logic():
    """Validates SLAComplianceSummary creation and immutability."""
    summary = SLAComplianceSummary(
        total_metrics=5,
        measurable_count=4,
        compliant_count=4,
        breached_count=0,
        unknown_count=1,
        not_applicable_count=0,
        invalid_count=0,
        is_overall_compliant=None,  # unknown present
    )
    assert summary.total_metrics == 5
    assert summary.is_overall_compliant is None

    with pytest.raises(ValidationError):
        summary.total_metrics = 10  # frozen


def test_integrity_sla_metrics_report():
    """Validates IntegritySLAMetricsReport structure and JSON serialization."""
    dt = datetime.now(timezone.utc)
    policy = SLAPolicy()
    metric = SLAMetric(
        metric_name=MetricName.CHECKPOINT_COVERAGE_RATIO,
        transaction_id="tx_test",
        status=MetricStatus.MEASURABLE,
        value=1.0,
        unit=MetricUnit.RATIO,
        threshold=0.75,
        is_compliant=True,
        calculation_reason="All reached",
    )
    summary = SLAComplianceSummary(
        total_metrics=1,
        measurable_count=1,
        compliant_count=1,
        breached_count=0,
        unknown_count=0,
        not_applicable_count=0,
        invalid_count=0,
        is_overall_compliant=True,
    )
    report = IntegritySLAMetricsReport(
        report_id="sla_rep_tx_test",
        transaction_id="tx_test",
        metrics=[metric],
        summary=summary,
        policy=policy,
        generated_at=dt,
    )
    assert report.transaction_id == "tx_test"
    json_data = report.model_dump_json()
    assert "CHECKPOINT_COVERAGE_RATIO" in json_data
