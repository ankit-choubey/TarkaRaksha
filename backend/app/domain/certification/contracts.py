"""
Ground-Truth Certification Domain Contracts for TarkaRaksha (I12).

Provides immutable, canonical data structures for:
- GroundTruthDefinition: Explicit expected behavior for a scenario.
- CertificationStatus: CERTIFIED / FAILED / INVALID.
- CertificationResult: Detailed dimensional comparison and tamper-evident digests.
- CertificationSuiteResult: Complete suite certification summary and matrix.

Invariants:
1. Ground truth is a test/verification assertion; it NEVER authoritatively decides transactions.
2. Actual results MUST come from the underlying authoritative pipeline (I11 / T04 / T05 / T07 / T13 / I8 / I9).
3. Hash integrity: input_snapshot_hash, ground_truth_hash, and actual_result_hash are cryptographically verified.
4. INVALID is distinct from FAILED (never silently downgrade certification invalidity to a test failure).
5. Zero AI dependencies, zero network dependencies, zero live side effects.
"""
from datetime import datetime
from enum import Enum
import hashlib
import json
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.domain.models import (
    EvidenceAuthority,
    IntegrityStatus,
    TransactionState,
)
from backend.app.domain.scenario.contracts import ScenarioId


class CertificationStatus(str, Enum):
    """Authoritative outcome of ground-truth certification."""
    CERTIFIED = "CERTIFIED"  # Actual pipeline outcome perfectly matches ground truth
    FAILED = "FAILED"        # Pipeline executed normally but output diverged from ground truth
    INVALID = "INVALID"      # Certification artifact invalid (tampered hash, malformed input, missing context)


class GroundTruthDefinition(BaseModel):
    """
    Typed, immutable declaration of ground truth for a known transaction scenario.
    """
    scenario_id: ScenarioId
    ground_truth_id: str
    description: str
    version: str = "1.0.0"
    expected_integrity_verdict: Optional[str] = None  # e.g., "PASS", "DRIFT", "UNKNOWN"
    expected_security_state: Optional[str] = None     # e.g., "REJECTED", "MISMATCH"
    expected_terminal_state: Optional[TransactionState] = None
    expected_mrdp_presence: bool = False
    expected_abstention: bool = False
    expected_violation_codes: List[str] = Field(default_factory=list)
    expected_authority_level: Optional[EvidenceAuthority] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )

    def compute_ground_truth_hash(self) -> str:
        """Computes a deterministic SHA-256 digest of the ground truth definition."""
        canonical_data = {
            "scenario_id": self.scenario_id.value,
            "ground_truth_id": self.ground_truth_id,
            "version": self.version,
            "expected_integrity_verdict": self.expected_integrity_verdict,
            "expected_security_state": self.expected_security_state,
            "expected_terminal_state": self.expected_terminal_state.value if self.expected_terminal_state else None,
            "expected_mrdp_presence": self.expected_mrdp_presence,
            "expected_abstention": self.expected_abstention,
            "expected_violation_codes": sorted(self.expected_violation_codes),
            "expected_authority_level": self.expected_authority_level.value if self.expected_authority_level else None,
        }
        encoded = json.dumps(canonical_data, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


class CertificationResult(BaseModel):
    """
    Immutable, tamper-evident record of certifying a scenario execution against ground truth.
    """
    certification_id: str
    scenario_id: ScenarioId
    ground_truth_id: str
    version: str = "1.0.0"

    # Dimensional comparison outcomes
    integrity_match: bool
    security_match: bool
    state_match: bool
    mrdp_match: bool
    abstention_match: bool
    violation_match: bool
    authority_match: bool

    # Overall verdict and diagnostics
    overall_status: CertificationStatus
    failure_reasons: List[str] = Field(default_factory=list)

    # Expected vs Actual details
    expected_result: Dict[str, Any]
    actual_result: Dict[str, Any]

    # Cryptographic integrity chain
    input_snapshot_hash: str
    ground_truth_hash: str
    actual_result_hash: str
    certification_hash: str

    certified_at: datetime

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    @field_validator("certified_at", mode="before")
    @classmethod
    def validate_certified_at_tz(cls, v: Any) -> datetime:
        if isinstance(v, str):
            dt = datetime.fromisoformat(v)
        elif isinstance(v, datetime):
            dt = v
        else:
            raise TypeError(f"Timestamp must be datetime or ISO string, got {type(v).__name__}")
        if dt.tzinfo is None:
            raise ValueError("certified_at must be timezone-aware (e.g. UTC)")
        return dt


class CertificationMatrixRow(BaseModel):
    """
    Typed, machine-readable matrix row for scenario certification results (I12).
    """
    scenario_id: str
    ground_truth_id: str
    actual_verdict: str
    expected_verdict: str
    integrity_match: bool
    security_match: bool
    state_match: bool
    mrdp_match: bool
    abstention_match: bool
    violation_match: bool
    authority_match: bool
    overall_certification: str
    certification_hash: str

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )


class CertificationSuiteResult(BaseModel):
    """
    Deterministic summary of certifying an entire scenario suite against ground truth.
    """
    suite_version: str = "1.0.0"
    total_scenarios: int
    certified_scenarios: int
    failed_scenarios: int
    invalid_scenarios: int
    results: List[CertificationResult]
    is_fully_certified: bool
    summary: str
    matrix: List[CertificationMatrixRow] = Field(default_factory=list)

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )


class EndToEndCertificationItem(BaseModel):
    """Factual proof item for a single end-to-end certification requirement (E9)."""
    requirement: str
    status: str  # PASS / FAIL / NOT_APPLICABLE
    evidence_type: str  # LIVE_VERIFIED / SYNTHETIC_OFFLINE_FIXTURE
    verified_fact: str
    evidence_digest: Optional[str] = None
    transaction_id: Optional[str] = None
    proof_ref: Optional[str] = None

    model_config = ConfigDict(frozen=True, extra="forbid")


class EndToEndCertificationReport(BaseModel):
    """
    Immutable, tamper-evident final demonstration certification report (E9).
    Aggregates verifiable proof across all 12 canonical certification areas.
    """
    certification_id: str
    overall_status: str  # PASS / CONDITIONAL / FAIL
    baseline_sha: str
    target_sha: str
    items: List[EndToEndCertificationItem]
    invariants_verified: Dict[str, bool]
    live_verified_count: int
    synthetic_fixture_count: int
    generated_at: datetime
    certification_digest: str

    model_config = ConfigDict(frozen=True, extra="forbid")

