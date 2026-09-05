"""Authoritative Domain Contracts for I19 Merchant-Side Capability Graph.

Defines:
- CapabilityNodeType: Typed entities within the merchant capability graph.
- CapabilityEdgeType: Explicit semantic relationships between graph nodes.
- CapabilityEvaluationStatus: Deterministic evaluation outcomes (SUPPORTED, CONSTRAINED, UNSUPPORTED, UNAVAILABLE, UNKNOWN).
- ConstraintType: Formal capability constraint categories.
- CapabilityNode & CapabilityEdge: Immutable graph graph primitives with deterministic identity.
- CapabilityConstraint & CapabilityViolation: Expressive, verifiable boundary conditions.
- CapabilityTransactionContext: Contextual transaction facts tested against graph boundaries.
- CapabilityEvaluationResult: Explainable, audit-grade verification outcome.
- CapabilityGraphSnapshot: Versioned, cryptographic snapshot for deterministic audit and historical replay.
- Custom exceptions: CrossMerchantCapabilityReuseError, InvalidCapabilityGraphError, etc.

Scope Boundary (§3, §34):
Contains NO reputation score, trust score, fraud rating, or quality score.
Strictly answers: What can this merchant do? Under what conditions? Supported by what evidence?
"""
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.domain.models.money import Money


class CapabilityNodeType(str, Enum):
    """Deterministic node categories within the merchant capability graph."""
    MERCHANT = "MERCHANT"
    CAPABILITY = "CAPABILITY"
    OPERATION = "OPERATION"
    CONSTRAINT = "CONSTRAINT"
    POLICY = "POLICY"
    EVIDENCE = "EVIDENCE"
    RESOURCE = "RESOURCE"


class CapabilityEdgeType(str, Enum):
    """Explicit, typed directional relationships between capability nodes."""
    OFFERS_CAPABILITY = "OFFERS_CAPABILITY"    # MERCHANT -> CAPABILITY
    ENABLES = "ENABLES"                        # CAPABILITY -> OPERATION
    CONSTRAINED_BY = "CONSTRAINED_BY"          # CAPABILITY -> CONSTRAINT or OPERATION -> CONSTRAINT
    GOVERNED_BY = "GOVERNED_BY"                # CAPABILITY -> POLICY or CONSTRAINT -> POLICY
    SUPPORTED_BY = "SUPPORTED_BY"              # CAPABILITY -> EVIDENCE or CONSTRAINT -> EVIDENCE
    REQUIRES = "REQUIRES"                      # OPERATION -> CAPABILITY
    TARGETS_RESOURCE = "TARGETS_RESOURCE"      # OPERATION -> RESOURCE or CAPABILITY -> RESOURCE


class CapabilityEvaluationStatus(str, Enum):
    """Deterministic capability evaluation statuses (§11)."""
    SUPPORTED = "SUPPORTED"          # Capability exists, enabled, and all constraints satisfied
    CONSTRAINED = "CONSTRAINED"      # Capability exists, but one or more transaction constraints violated
    UNSUPPORTED = "UNSUPPORTED"      # Capability does not exist for this merchant
    UNAVAILABLE = "UNAVAILABLE"      # Capability is declared but currently disabled/offline
    UNKNOWN = "UNKNOWN"              # Insufficient evidence or conflicting inputs prevent verification


class ConstraintType(str, Enum):
    """Standardized deterministic constraint categories."""
    MAX_AMOUNT = "MAX_AMOUNT"
    MAX_QUANTITY = "MAX_QUANTITY"
    ALLOWED_CURRENCIES = "ALLOWED_CURRENCIES"
    ALLOWED_REGIONS = "ALLOWED_REGIONS"
    MAX_DISCOUNT_BPS = "MAX_DISCOUNT_BPS"
    ALLOWED_SKUS = "ALLOWED_SKUS"
    MAX_WINDOW_DAYS = "MAX_WINDOW_DAYS"
    DELIVERY_DAYS_WINDOW = "DELIVERY_DAYS_WINDOW"
    CUSTOM = "CUSTOM"


class CapabilityNode(BaseModel):
    """
    Deterministic node entity in the merchant capability graph.
    Identity is stable, canonical, and based on semantic keys.
    """
    node_id: str
    node_type: CapabilityNodeType
    label: str
    attributes: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )

    @field_validator("node_id", "label")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("node_id and label must be non-empty strings")
        return v.strip()


class CapabilityEdge(BaseModel):
    """
    Typed, directed relationship connecting two nodes in the capability graph.
    """
    edge_id: str
    from_node_id: str
    to_node_id: str
    edge_type: CapabilityEdgeType
    attributes: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )

    @field_validator("edge_id", "from_node_id", "to_node_id")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Edge identifiers and endpoints cannot be empty or whitespace")
        return v.strip()


class CapabilityConstraint(BaseModel):
    """
    Structured, verifiable constraint attached to a capability or operation.
    """
    constraint_id: str
    name: str
    constraint_type: ConstraintType
    parameters: Dict[str, Any] = Field(default_factory=dict)
    description: str = ""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )

    @field_validator("constraint_id", "name")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("constraint_id and name cannot be empty")
        return v.strip()


class CapabilityViolation(BaseModel):
    """
    Deterministic explanation of a constraint breach during capability evaluation.
    """
    constraint_id: str
    constraint_type: ConstraintType
    expected: Any
    observed: Any
    message: str

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )


class CapabilityTransactionContext(BaseModel):
    """
    Transaction-specific facts presented for capability evaluation.
    Enforces I8 merchant identity binding.
    """
    merchant_id: str
    transaction_id: Optional[str] = None
    intent_id: Optional[str] = None
    agent_id: Optional[str] = None
    amount: Optional[Money] = None
    quantity: Optional[int] = None
    sku: Optional[str] = None
    skus: List[str] = Field(default_factory=list)
    destination_region: Optional[str] = None
    requested_discount_bps: Optional[int] = None
    delivery_days: Optional[int] = None
    refund_days_since_purchase: Optional[int] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )

    @field_validator("merchant_id")
    @classmethod
    def validate_merchant_id(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("merchant_id is mandatory and cannot be empty")
        return v.strip()


class CapabilityEvaluationResult(BaseModel):
    """
    Comprehensive, explainable audit record of a capability evaluation.
    """
    evaluation_id: str
    merchant_id: str
    operation: str
    status: CapabilityEvaluationStatus
    capability_id: Optional[str] = None
    satisfied_constraints: List[str] = Field(default_factory=list)
    violations: List[CapabilityViolation] = Field(default_factory=list)
    supporting_evidence_ids: List[str] = Field(default_factory=list)
    reason: str
    policy_version: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )

    @field_validator("evaluation_id", "merchant_id", "operation", "reason", "policy_version")
    @classmethod
    def validate_non_empty_strings(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Evaluation string fields cannot be empty")
        return v.strip()

    @field_validator("timestamp", mode="before")
    @classmethod
    def validate_timestamp(cls, v: Any) -> datetime:
        if isinstance(v, str):
            dt = datetime.fromisoformat(v)
        elif isinstance(v, datetime):
            dt = v
        else:
            raise TypeError(f"Timestamp must be datetime or ISO string, got {type(v).__name__}")
        if dt.tzinfo is None:
            raise ValueError("Timestamp must be timezone-aware (UTC)")
        return dt


class CapabilityGraphSnapshot(BaseModel):
    """
    Immutable, cryptographically hashed snapshot of a merchant's capability graph.
    Used for historical audit and deterministic replay (§25, §26).
    """
    merchant_id: str
    graph_version: str = "1.0.0"
    policy_version: str
    nodes: List[CapabilityNode]
    edges: List[CapabilityEdge]
    graph_hash: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )

    @field_validator("merchant_id", "graph_version", "policy_version", "graph_hash")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Snapshot metadata fields cannot be empty")
        return v.strip()

    @field_validator("created_at", mode="before")
    @classmethod
    def validate_created_at(cls, v: Any) -> datetime:
        if isinstance(v, str):
            dt = datetime.fromisoformat(v)
        elif isinstance(v, datetime):
            dt = v
        else:
            raise TypeError(f"Timestamp must be datetime or ISO string, got {type(v).__name__}")
        if dt.tzinfo is None:
            raise ValueError("created_at must be timezone-aware (UTC)")
        return dt


def compute_canonical_graph_hash(
    merchant_id: str,
    graph_version: str,
    policy_version: str,
    nodes: List[CapabilityNode],
    edges: List[CapabilityEdge],
) -> str:
    """
    Computes a deterministic SHA-256 hash over canonical representation of nodes and edges.
    Guarantees that identical graph topology yields identical digest.
    """
    sorted_nodes = sorted(nodes, key=lambda n: n.node_id)
    sorted_edges = sorted(edges, key=lambda e: e.edge_id)

    payload = {
        "merchant_id": merchant_id.strip(),
        "graph_version": graph_version.strip(),
        "policy_version": policy_version.strip(),
        "nodes": [n.model_dump(mode="json") for n in sorted_nodes],
        "edges": [e.model_dump(mode="json") for e in sorted_edges],
    }

    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


# Domain Exceptions
class CapabilityError(Exception):
    """Base exception for capability graph errors."""
    pass


class CrossMerchantCapabilityReuseError(CapabilityError):
    """Raised when attempting to apply one merchant's capability to another merchant (§18)."""
    pass


class InvalidCapabilityGraphError(CapabilityError):
    """Raised when graph validation fails (dangling edges, duplicates, merchant mismatches) (§24)."""
    pass


class CapabilityConstraintError(CapabilityError):
    """Raised when a capability constraint is breached or ill-formed."""
    pass
