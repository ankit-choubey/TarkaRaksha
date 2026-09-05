"""Authoritative domain contracts for Innovation I15 — Integrity SLA Metrics.

Provides immutable SLA measurement models, metrics definitions, policy thresholds,
and compliance summary schemas.

Core Invariant:
AI proposes -> evidence proves -> deterministic logic decides.
I15 is a pure deterministic measurement/observability layer. Zero authoritative LLM logic.
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class MetricStatus(str, Enum):
    """
    Evaluation status of a specific SLA metric.
    Strictly distinguishes measurable success from missing evidence or inapplicable contexts.
    """
    MEASURABLE = "MEASURABLE"          # Required authoritative evidence exists and calculation succeeded
    UNKNOWN = "UNKNOWN"                # Insufficient, delayed, or missing evidence prevented calculation
    NOT_APPLICABLE = "NOT_APPLICABLE"  # Metric does not apply to this lifecycle path (e.g. clean PASS)
    INVALID = "INVALID"                # Evidence violates invariants (e.g. clock anomaly, reversed timestamps)


class MetricUnit(str, Enum):
    """Unit of measurement for an SLA metric."""
    MILLISECONDS = "MILLISECONDS"
    RATIO = "RATIO"
    COUNT = "COUNT"
    BOOLEAN = "BOOLEAN"


class MetricName(str, Enum):
    """
    Authoritative SLA metrics computed by TarkaRaksha.
    """
    TIME_TO_DETECT = "TIME_TO_DETECT"                      # Triggering event to divergence detection (ms)
    TIME_TO_PROVE = "TIME_TO_PROVE"                        # Divergence detection to MRDP proof creation (ms)
    TIME_TO_INTERVENE = "TIME_TO_INTERVENE"                # Drift detection to I9 safety state entry (ms)
    TIME_TO_REVALIDATE = "TIME_TO_REVALIDATE"              # Intervention to revalidation outcome (ms)
    TIME_TO_FINAL_DECISION = "TIME_TO_FINAL_DECISION"      # Transaction creation to final state commitment (ms)
    UNKNOWN_EXPOSURE_DURATION = "UNKNOWN_EXPOSURE_DURATION"# Duration transaction remained in UNKNOWN (ms)
    CHECKPOINT_COVERAGE_RATIO = "CHECKPOINT_COVERAGE_RATIO"# Ratio of reached checkpoints to total checkpoints
    CHECKPOINT_VALID_RATIO = "CHECKPOINT_VALID_RATIO"      # Ratio of valid checkpoints to total checkpoints
    TRACE_COMPLETENESS_RATIO = "TRACE_COMPLETENESS_RATIO"  # Ratio of reached lifecycle trace stages to total


class SLAPolicy(BaseModel):
    """
    Configurable, governed SLA compliance policy with deterministic thresholds.
    """
    policy_id: str = "default_sla_policy"
    governance_version: str = "gov_v1.0.0"
    max_time_to_detect_ms: Optional[float] = 5000.0
    max_time_to_prove_ms: Optional[float] = 3000.0
    max_time_to_intervene_ms: Optional[float] = 2000.0
    max_time_to_revalidate_ms: Optional[float] = 10000.0
    max_time_to_final_decision_ms: Optional[float] = 30000.0
    max_unknown_exposure_ms: Optional[float] = 15000.0
    min_checkpoint_coverage_ratio: Optional[float] = 0.75
    min_checkpoint_valid_ratio: Optional[float] = 0.5
    min_trace_completeness_ratio: Optional[float] = 0.75

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    @field_validator("policy_id", "governance_version")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("String field cannot be empty")
        return v.strip()


class SLAMetric(BaseModel):
    """
    Immutable representation of an individual deterministic SLA measurement.
    """
    metric_name: MetricName
    metric_definition_version: str = "gov_v1.0.0"
    transaction_id: str
    status: MetricStatus
    value: Optional[float] = None
    unit: MetricUnit
    threshold: Optional[float] = None
    is_compliant: Optional[bool] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    start_evidence_ref: Optional[str] = None
    end_evidence_ref: Optional[str] = None
    evidence_refs: List[str] = Field(default_factory=list)
    calculation_reason: str
    details: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    @field_validator("transaction_id", "calculation_reason")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("String field cannot be empty")
        return v.strip()

    @field_validator("start_time", "end_time")
    @classmethod
    def validate_timezone(cls, v: Optional[datetime]) -> Optional[datetime]:
        if v is not None and v.tzinfo is None:
            raise ValueError("Timestamps must be timezone-aware (UTC)")
        return v

    @field_validator("value")
    @classmethod
    def validate_value(cls, v: Optional[float], info) -> Optional[float]:
        status = info.data.get("status")
        if status == MetricStatus.MEASURABLE and v is None:
            raise ValueError("MEASURABLE metric must have a numeric value")
        if status in (MetricStatus.UNKNOWN, MetricStatus.NOT_APPLICABLE, MetricStatus.INVALID) and v is not None:
            raise ValueError(f"{status.value} metric must not have a numeric value")
        return v


class SLAComplianceSummary(BaseModel):
    """
    Deterministic aggregation of SLA metrics compliance.
    """
    total_metrics: int
    measurable_count: int
    compliant_count: int
    breached_count: int
    unknown_count: int
    not_applicable_count: int
    invalid_count: int
    is_overall_compliant: Optional[bool] = None

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class IntegritySLAMetricsReport(BaseModel):
    """
    Authoritative, immutable SLA metrics report for a transaction.
    """
    report_id: str
    transaction_id: str
    metrics: List[SLAMetric]
    summary: SLAComplianceSummary
    policy: SLAPolicy
    governance_version: str = "gov_v1.0.0"
    reproducibility_reference: Optional[str] = None
    generated_at: datetime

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    @field_validator("report_id", "transaction_id")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("String field cannot be empty")
        return v.strip()

    @field_validator("generated_at")
    @classmethod
    def validate_timezone(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("generated_at must be timezone-aware (UTC)")
        return v
