"""Authoritative In-Memory Deterministic Capability Graph for TarkaRaksha (I19).

Provides:
- MerchantCapabilityGraph: In-memory queryable graph structure with adjacency indexing.
- Factory method from_declaration_and_policy() integrating I4 MerchantCapabilityDeclaration and MerchantPolicyAsCode.
- Graph validation guaranteeing structural and semantic integrity (§24).
- Export to immutable, cryptographically verifiable CapabilityGraphSnapshot (§25).
- Clean query API for capability, operation, constraint, policy, and evidence lookups (§23).
"""
from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional, Set

from backend.app.domain.capability.contracts import (
    CapabilityConstraint,
    CapabilityEdge,
    CapabilityEdgeType,
    CapabilityGraphSnapshot,
    CapabilityNode,
    CapabilityNodeType,
    ConstraintType,
    InvalidCapabilityGraphError,
    compute_canonical_graph_hash,
)
from backend.app.domain.merchant.capabilities import (
    CommerceCapabilityType,
    MerchantCapability,
    MerchantCapabilityDeclaration,
    MerchantPolicyAsCode,
)


class MerchantCapabilityGraph:
    """
    Deterministic capability graph for a specific merchant agent.
    Represents what the merchant agent can do, under what conditions,
    governed by which policy, and supported by which evidence records.
    """

    def __init__(
        self,
        merchant_id: str,
        policy_version: str,
        graph_version: str = "1.0.0",
        nodes: Optional[List[CapabilityNode]] = None,
        edges: Optional[List[CapabilityEdge]] = None,
        constraints: Optional[Dict[str, CapabilityConstraint]] = None,
        created_at: Optional[datetime] = None,
    ):
        self.merchant_id: str = merchant_id.strip()
        self.policy_version: str = policy_version.strip()
        self.graph_version: str = graph_version.strip()
        self.created_at: datetime = created_at or datetime.now(timezone.utc)

        self._nodes: Dict[str, CapabilityNode] = {}
        self._edges: Dict[str, CapabilityEdge] = {}
        self._constraints: Dict[str, CapabilityConstraint] = constraints or {}

        # Adjacency indexes for deterministic O(1) query traversal
        self._outgoing: Dict[str, List[CapabilityEdge]] = {}
        self._incoming: Dict[str, List[CapabilityEdge]] = {}

        if nodes:
            for node in nodes:
                self.add_node(node)
        if edges:
            for edge in edges:
                self.add_edge(edge)

    @property
    def nodes(self) -> Dict[str, CapabilityNode]:
        return dict(self._nodes)

    @property
    def edges(self) -> Dict[str, CapabilityEdge]:
        return dict(self._edges)

    @property
    def constraints(self) -> Dict[str, CapabilityConstraint]:
        return dict(self._constraints)

    def add_node(self, node: CapabilityNode) -> None:
        """Adds a node to the graph and initializes adjacency lists."""
        if node.node_id in self._nodes:
            raise InvalidCapabilityGraphError(f"Duplicate node ID '{node.node_id}' in graph.")
        self._nodes[node.node_id] = node
        if node.node_id not in self._outgoing:
            self._outgoing[node.node_id] = []
        if node.node_id not in self._incoming:
            self._incoming[node.node_id] = []

    def add_edge(self, edge: CapabilityEdge) -> None:
        """Adds an edge to the graph after validating endpoints."""
        if edge.edge_id in self._edges:
            raise InvalidCapabilityGraphError(f"Duplicate edge ID '{edge.edge_id}' in graph.")
        if edge.from_node_id not in self._nodes:
            raise InvalidCapabilityGraphError(
                f"Edge '{edge.edge_id}' references unknown from_node '{edge.from_node_id}'."
            )
        if edge.to_node_id not in self._nodes:
            raise InvalidCapabilityGraphError(
                f"Edge '{edge.edge_id}' references unknown to_node '{edge.to_node_id}'."
            )
        self._edges[edge.edge_id] = edge
        self._outgoing[edge.from_node_id].append(edge)
        self._incoming[edge.to_node_id].append(edge)

    def add_constraint(self, constraint: CapabilityConstraint) -> None:
        """Registers a constraint definition."""
        self._constraints[constraint.constraint_id] = constraint

    def validate(self) -> None:
        """
        Validates the capability graph invariants (§24):
        - Root merchant node must exist with matching merchant_id.
        - All edges reference valid existing nodes.
        - No duplicate node or edge IDs exist.
        - Capability nodes must belong to this merchant.
        """
        merchant_node_id = f"merch:{self.merchant_id}"
        if merchant_node_id not in self._nodes:
            raise InvalidCapabilityGraphError(
                f"Merchant capability graph is missing root merchant node '{merchant_node_id}'."
            )
        merch_node = self._nodes[merchant_node_id]
        if merch_node.node_type != CapabilityNodeType.MERCHANT:
            raise InvalidCapabilityGraphError(
                f"Root node '{merchant_node_id}' must have type MERCHANT, got {merch_node.node_type}."
            )

        # Check all edges
        for edge in self._edges.values():
            if edge.from_node_id not in self._nodes or edge.to_node_id not in self._nodes:
                raise InvalidCapabilityGraphError(
                    f"Dangling edge detected: '{edge.edge_id}' ({edge.from_node_id} -> {edge.to_node_id})."
                )

        # Check capability merchant ownership
        for node in self._nodes.values():
            if node.node_type == CapabilityNodeType.CAPABILITY:
                node_merch = node.attributes.get("merchant_id")
                if node_merch and node_merch != self.merchant_id:
                    raise InvalidCapabilityGraphError(
                        f"Capability node '{node.node_id}' has merchant_id '{node_merch}', "
                        f"which does not match graph merchant '{self.merchant_id}'."
                    )

    # Query API (§23)
    def get_node(self, node_id: str) -> Optional[CapabilityNode]:
        return self._nodes.get(node_id)

    def get_edge(self, edge_id: str) -> Optional[CapabilityEdge]:
        return self._edges.get(edge_id)

    def get_outgoing_edges(
        self,
        from_node_id: str,
        edge_type: Optional[CapabilityEdgeType] = None,
    ) -> List[CapabilityEdge]:
        edges = self._outgoing.get(from_node_id, [])
        if edge_type is None:
            return list(edges)
        return [e for e in edges if e.edge_type == edge_type]

    def get_incoming_edges(
        self,
        to_node_id: str,
        edge_type: Optional[CapabilityEdgeType] = None,
    ) -> List[CapabilityEdge]:
        edges = self._incoming.get(to_node_id, [])
        if edge_type is None:
            return list(edges)
        return [e for e in edges if e.edge_type == edge_type]

    def get_capabilities(self) -> List[CapabilityNode]:
        """Returns all capability nodes for this merchant."""
        return [n for n in self._nodes.values() if n.node_type == CapabilityNodeType.CAPABILITY]

    def get_capability(self, capability_type: str) -> Optional[CapabilityNode]:
        """Looks up a capability node by type."""
        cap_id = f"cap:{self.merchant_id}:{capability_type.upper()}"
        return self._nodes.get(cap_id)

    def get_operations_for_capability(self, capability_node_id: str) -> List[CapabilityNode]:
        """Returns all operations enabled by a given capability node."""
        op_edges = self.get_outgoing_edges(capability_node_id, CapabilityEdgeType.ENABLES)
        return [self._nodes[e.to_node_id] for e in op_edges if e.to_node_id in self._nodes]

    def find_capabilities_for_operation(self, operation: str) -> List[CapabilityNode]:
        """Finds which capabilities enable a requested operation."""
        op_node_id = f"op:{operation.upper()}"
        if op_node_id not in self._nodes:
            return []
        req_edges = self.get_outgoing_edges(op_node_id, CapabilityEdgeType.REQUIRES)
        return [self._nodes[e.to_node_id] for e in req_edges if e.to_node_id in self._nodes]

    def get_constraints_for_capability(self, capability_node_id: str) -> List[CapabilityConstraint]:
        """Returns all constraints bound to a capability."""
        const_edges = self.get_outgoing_edges(capability_node_id, CapabilityEdgeType.CONSTRAINED_BY)
        res = []
        for e in const_edges:
            const_node = self._nodes.get(e.to_node_id)
            if const_node and const_node.node_type == CapabilityNodeType.CONSTRAINT:
                const_id = const_node.attributes.get("constraint_id")
                if const_id and const_id in self._constraints:
                    res.append(self._constraints[const_id])
        return res

    def get_constraints_for_operation(self, operation: str) -> List[CapabilityConstraint]:
        """Returns all constraints bound directly to an operation or its parent capability."""
        res: List[CapabilityConstraint] = []
        op_node_id = f"op:{operation.upper()}"
        if op_node_id in self._nodes:
            op_const_edges = self.get_outgoing_edges(op_node_id, CapabilityEdgeType.CONSTRAINED_BY)
            for e in op_const_edges:
                const_node = self._nodes.get(e.to_node_id)
                if const_node:
                    const_id = const_node.attributes.get("constraint_id")
                    if const_id and const_id in self._constraints:
                        res.append(self._constraints[const_id])

        for cap_node in self.find_capabilities_for_operation(operation):
            res.extend(self.get_constraints_for_capability(cap_node.node_id))

        # Deduplicate constraints by constraint_id
        seen = set()
        deduped = []
        for c in res:
            if c.constraint_id not in seen:
                seen.add(c.constraint_id)
                deduped.append(c)
        return deduped

    def get_policies(self) -> List[CapabilityNode]:
        """Returns policy nodes in the graph."""
        return [n for n in self._nodes.values() if n.node_type == CapabilityNodeType.POLICY]

    def get_evidence_references(self, node_id: Optional[str] = None) -> List[CapabilityNode]:
        """Returns evidence nodes either globally or supporting a specific node."""
        if node_id is None:
            return [n for n in self._nodes.values() if n.node_type == CapabilityNodeType.EVIDENCE]
        ev_edges = self.get_outgoing_edges(node_id, CapabilityEdgeType.SUPPORTED_BY)
        return [self._nodes[e.to_node_id] for e in ev_edges if e.to_node_id in self._nodes]

    def export_snapshot(self) -> CapabilityGraphSnapshot:
        """Exports an immutable, cryptographically verifiable snapshot of this graph."""
        node_list = list(self._nodes.values())
        edge_list = list(self._edges.values())
        digest = compute_canonical_graph_hash(
            merchant_id=self.merchant_id,
            graph_version=self.graph_version,
            policy_version=self.policy_version,
            nodes=node_list,
            edges=edge_list,
        )
        return CapabilityGraphSnapshot(
            merchant_id=self.merchant_id,
            graph_version=self.graph_version,
            policy_version=self.policy_version,
            nodes=node_list,
            edges=edge_list,
            graph_hash=digest,
            created_at=self.created_at,
        )

    @classmethod
    def from_snapshot(
        cls,
        snapshot: CapabilityGraphSnapshot,
        constraints: Optional[Dict[str, CapabilityConstraint]] = None,
    ) -> "MerchantCapabilityGraph":
        """Reconstructs a deterministic graph from a verified snapshot (§26)."""
        reconstructed_constraints = dict(constraints) if constraints else {}
        for node in snapshot.nodes:
            if node.node_type == CapabilityNodeType.CONSTRAINT:
                c_id = node.attributes.get("constraint_id", node.node_id)
                if c_id not in reconstructed_constraints:
                    c_type_str = node.attributes.get("type", "CUSTOM")
                    try:
                        c_type = ConstraintType(c_type_str)
                    except ValueError:
                        c_type = ConstraintType.CUSTOM
                    reconstructed_constraints[c_id] = CapabilityConstraint(
                        constraint_id=c_id,
                        name=node.attributes.get("name", node.label),
                        constraint_type=c_type,
                        parameters=node.attributes.get("parameters", {}),
                        description=node.attributes.get("description", ""),
                    )

        graph = cls(
            merchant_id=snapshot.merchant_id,
            policy_version=snapshot.policy_version,
            graph_version=snapshot.graph_version,
            nodes=snapshot.nodes,
            edges=snapshot.edges,
            constraints=reconstructed_constraints,
            created_at=snapshot.created_at,
        )
        graph.validate()
        return graph

    @classmethod
    def from_declaration_and_policy(
        cls,
        merchant_id: str,
        declaration: MerchantCapabilityDeclaration,
        policy: MerchantPolicyAsCode,
        evidence_refs: Optional[List[str]] = None,
        graph_version: str = "1.0.0",
        reference_time: Optional[datetime] = None,
    ) -> "MerchantCapabilityGraph":
        """
        Factory method constructing a canonical, fully-connected MerchantCapabilityGraph
        from an I4 MerchantCapabilityDeclaration and MerchantPolicyAsCode.
        """
        created_at = reference_time or datetime.now(timezone.utc)
        graph = cls(
            merchant_id=merchant_id,
            policy_version=policy.policy_version,
            graph_version=graph_version,
            created_at=created_at,
        )

        # 1. Root Merchant Node
        merch_node_id = f"merch:{merchant_id}"
        graph.add_node(
            CapabilityNode(
                node_id=merch_node_id,
                node_type=CapabilityNodeType.MERCHANT,
                label=declaration.merchant_name or f"Merchant {merchant_id}",
                attributes={
                    "merchant_id": merchant_id,
                    "agent_version": declaration.agent_version,
                },
            )
        )

        # 2. Policy Node
        pol_node_id = f"pol:{policy.policy_id}:{policy.policy_version}"
        graph.add_node(
            CapabilityNode(
                node_id=pol_node_id,
                node_type=CapabilityNodeType.POLICY,
                label=f"Merchant Policy {policy.policy_version}",
                attributes={
                    "policy_id": policy.policy_id,
                    "policy_version": policy.policy_version,
                    "max_order_value_amount": policy.max_order_value.amount,
                    "max_order_value_currency": policy.max_order_value.currency,
                    "max_discount_bps": policy.max_discount_bps,
                    "offer_ttl_seconds": policy.offer_ttl_seconds,
                    "min_delivery_days": policy.min_delivery_days,
                    "max_delivery_days": policy.max_delivery_days,
                },
            )
        )

        # 3. Canonical Constraints derived from Policy
        # 3a. Max Order Value
        c_max_order = CapabilityConstraint(
            constraint_id=f"const:{merchant_id}:max_order_value",
            name="Max Order Value Ceiling",
            constraint_type=ConstraintType.MAX_AMOUNT,
            parameters={
                "max_amount_paise": policy.max_order_value.amount,
                "currency": policy.max_order_value.currency,
            },
            description=f"Transaction amount cannot exceed {policy.max_order_value.amount} {policy.max_order_value.currency}",
        )
        graph.add_constraint(c_max_order)
        graph.add_node(
            CapabilityNode(
                node_id=c_max_order.constraint_id,
                node_type=CapabilityNodeType.CONSTRAINT,
                label=c_max_order.name,
                attributes={
                    "constraint_id": c_max_order.constraint_id,
                    "name": c_max_order.name,
                    "type": c_max_order.constraint_type.value,
                    "parameters": c_max_order.parameters,
                    "description": c_max_order.description,
                },
            )
        )

        # 3b. Max Discount
        c_max_discount = CapabilityConstraint(
            constraint_id=f"const:{merchant_id}:max_discount",
            name="Max Discount Rate",
            constraint_type=ConstraintType.MAX_DISCOUNT_BPS,
            parameters={"max_discount_bps": policy.max_discount_bps},
            description=f"Discount cannot exceed {policy.max_discount_bps} basis points",
        )
        graph.add_constraint(c_max_discount)
        graph.add_node(
            CapabilityNode(
                node_id=c_max_discount.constraint_id,
                node_type=CapabilityNodeType.CONSTRAINT,
                label=c_max_discount.name,
                attributes={
                    "constraint_id": c_max_discount.constraint_id,
                    "name": c_max_discount.name,
                    "type": c_max_discount.constraint_type.value,
                    "parameters": c_max_discount.parameters,
                    "description": c_max_discount.description,
                },
            )
        )

        # 3c. Delivery Timeline Window
        c_delivery = CapabilityConstraint(
            constraint_id=f"const:{merchant_id}:delivery_days_window",
            name="Delivery Timeline Window",
            constraint_type=ConstraintType.DELIVERY_DAYS_WINDOW,
            parameters={
                "min_delivery_days": policy.min_delivery_days,
                "max_delivery_days": policy.max_delivery_days,
            },
            description=f"Delivery estimate must be within [{policy.min_delivery_days}, {policy.max_delivery_days}] days",
        )
        graph.add_constraint(c_delivery)
        graph.add_node(
            CapabilityNode(
                node_id=c_delivery.constraint_id,
                node_type=CapabilityNodeType.CONSTRAINT,
                label=c_delivery.name,
                attributes={
                    "constraint_id": c_delivery.constraint_id,
                    "name": c_delivery.name,
                    "type": c_delivery.constraint_type.value,
                    "parameters": c_delivery.parameters,
                    "description": c_delivery.description,
                },
            )
        )

        # 3d. Refund Limit Window
        c_refund_window = CapabilityConstraint(
            constraint_id=f"const:{merchant_id}:refund_window",
            name="Maximum Refund Window",
            constraint_type=ConstraintType.MAX_WINDOW_DAYS,
            parameters={"max_window_days": 14},
            description="Refunds permitted only within 14 days of purchase",
        )
        graph.add_constraint(c_refund_window)
        graph.add_node(
            CapabilityNode(
                node_id=c_refund_window.constraint_id,
                node_type=CapabilityNodeType.CONSTRAINT,
                label=c_refund_window.name,
                attributes={
                    "constraint_id": c_refund_window.constraint_id,
                    "name": c_refund_window.name,
                    "type": c_refund_window.constraint_type.value,
                    "parameters": c_refund_window.parameters,
                    "description": c_refund_window.description,
                },
            )
        )

        # 3e. Allowed Substitutions
        if policy.allowed_substitutions:
            c_substitutions = CapabilityConstraint(
                constraint_id=f"const:{merchant_id}:allowed_substitutions",
                name="Allowed SKU Substitutions",
                constraint_type=ConstraintType.ALLOWED_SKUS,
                parameters={"substitutions_map": policy.allowed_substitutions},
                description="Only pre-authorized alternative SKUs can be proposed",
            )
            graph.add_constraint(c_substitutions)
            graph.add_node(
                CapabilityNode(
                    node_id=c_substitutions.constraint_id,
                    node_type=CapabilityNodeType.CONSTRAINT,
                    label=c_substitutions.name,
                    attributes={
                        "constraint_id": c_substitutions.constraint_id,
                        "name": c_substitutions.name,
                        "type": c_substitutions.constraint_type.value,
                        "parameters": c_substitutions.parameters,
                        "description": c_substitutions.description,
                    },
                )
            )

        # 4. Canonical Operations mapping
        capability_operations_map: Dict[CommerceCapabilityType, List[str]] = {
            CommerceCapabilityType.CATALOG: ["SEARCH_CATALOG", "VIEW_ITEM"],
            CommerceCapabilityType.INVENTORY: ["CHECK_INVENTORY", "RESERVE_INVENTORY"],
            CommerceCapabilityType.PRICING: ["QUOTE_PRICE", "APPLY_DISCOUNT"],
            CommerceCapabilityType.SHIPPING: ["STANDARD_SHIPPING", "EXPRESS_SHIPPING"],
            CommerceCapabilityType.TAX: ["CALCULATE_TAX"],
            CommerceCapabilityType.ALTERNATIVE_OFFER: ["SUBSTITUTE_SKU"],
            CommerceCapabilityType.REFUND: ["PROCESS_REFUND"],
            CommerceCapabilityType.FULFILLMENT: ["FULFILL_ORDER"],
        }

        # 5. Evidence Nodes (if specified)
        if evidence_refs:
            for ev_id in evidence_refs:
                ev_node_id = f"ev:{ev_id}"
                if ev_node_id not in graph.nodes:
                    graph.add_node(
                        CapabilityNode(
                            node_id=ev_node_id,
                            node_type=CapabilityNodeType.EVIDENCE,
                            label=f"Evidence {ev_id}",
                            attributes={"evidence_id": ev_id},
                        )
                    )

        # 6. Capabilities, Edges, and Operations
        for cap_type, cap_obj in declaration.capabilities.items():
            cap_node_id = f"cap:{merchant_id}:{cap_type.value}"
            graph.add_node(
                CapabilityNode(
                    node_id=cap_node_id,
                    node_type=CapabilityNodeType.CAPABILITY,
                    label=f"Capability: {cap_type.value}",
                    attributes={
                        "merchant_id": merchant_id,
                        "capability_type": cap_type.value,
                        "is_available": cap_obj.is_available,
                        "version": cap_obj.version,
                        "scope": cap_obj.scope,
                    },
                )
            )

            # Edge: MERCHANT -> OFFERS_CAPABILITY -> CAPABILITY
            graph.add_edge(
                CapabilityEdge(
                    edge_id=f"edge:{merch_node_id}->offers->{cap_node_id}",
                    from_node_id=merch_node_id,
                    to_node_id=cap_node_id,
                    edge_type=CapabilityEdgeType.OFFERS_CAPABILITY,
                )
            )

            # Edge: CAPABILITY -> GOVERNED_BY -> POLICY
            graph.add_edge(
                CapabilityEdge(
                    edge_id=f"edge:{cap_node_id}->governed_by->{pol_node_id}",
                    from_node_id=cap_node_id,
                    to_node_id=pol_node_id,
                    edge_type=CapabilityEdgeType.GOVERNED_BY,
                )
            )

            # Link evidence if available
            if evidence_refs:
                for ev_id in evidence_refs:
                    graph.add_edge(
                        CapabilityEdge(
                            edge_id=f"edge:{cap_node_id}->supported_by->ev:{ev_id}",
                            from_node_id=cap_node_id,
                            to_node_id=f"ev:{ev_id}",
                            edge_type=CapabilityEdgeType.SUPPORTED_BY,
                        )
                    )

            # Link relevant constraints
            if cap_type in [CommerceCapabilityType.PRICING, CommerceCapabilityType.CATALOG]:
                graph.add_edge(
                    CapabilityEdge(
                        edge_id=f"edge:{cap_node_id}->constrained_by->{c_max_order.constraint_id}",
                        from_node_id=cap_node_id,
                        to_node_id=c_max_order.constraint_id,
                        edge_type=CapabilityEdgeType.CONSTRAINED_BY,
                    )
                )
            if cap_type == CommerceCapabilityType.PRICING:
                graph.add_edge(
                    CapabilityEdge(
                        edge_id=f"edge:{cap_node_id}->constrained_by->{c_max_discount.constraint_id}",
                        from_node_id=cap_node_id,
                        to_node_id=c_max_discount.constraint_id,
                        edge_type=CapabilityEdgeType.CONSTRAINED_BY,
                    )
                )
            if cap_type == CommerceCapabilityType.SHIPPING:
                graph.add_edge(
                    CapabilityEdge(
                        edge_id=f"edge:{cap_node_id}->constrained_by->{c_delivery.constraint_id}",
                        from_node_id=cap_node_id,
                        to_node_id=c_delivery.constraint_id,
                        edge_type=CapabilityEdgeType.CONSTRAINED_BY,
                    )
                )
            if cap_type == CommerceCapabilityType.REFUND:
                graph.add_edge(
                    CapabilityEdge(
                        edge_id=f"edge:{cap_node_id}->constrained_by->{c_refund_window.constraint_id}",
                        from_node_id=cap_node_id,
                        to_node_id=c_refund_window.constraint_id,
                        edge_type=CapabilityEdgeType.CONSTRAINED_BY,
                    )
                )
            if cap_type == CommerceCapabilityType.ALTERNATIVE_OFFER and policy.allowed_substitutions:
                sub_id = f"const:{merchant_id}:allowed_substitutions"
                graph.add_edge(
                    CapabilityEdge(
                        edge_id=f"edge:{cap_node_id}->constrained_by->{sub_id}",
                        from_node_id=cap_node_id,
                        to_node_id=sub_id,
                        edge_type=CapabilityEdgeType.CONSTRAINED_BY,
                    )
                )

            # Register operations
            ops = capability_operations_map.get(cap_type, [])
            for op_name in ops:
                op_node_id = f"op:{op_name}"
                if op_node_id not in graph.nodes:
                    graph.add_node(
                        CapabilityNode(
                            node_id=op_node_id,
                            node_type=CapabilityNodeType.OPERATION,
                            label=f"Operation: {op_name}",
                            attributes={"operation": op_name},
                        )
                    )

                # Edge: CAPABILITY -> ENABLES -> OPERATION
                graph.add_edge(
                    CapabilityEdge(
                        edge_id=f"edge:{cap_node_id}->enables->{op_node_id}",
                        from_node_id=cap_node_id,
                        to_node_id=op_node_id,
                        edge_type=CapabilityEdgeType.ENABLES,
                    )
                )

                # Edge: OPERATION -> REQUIRES -> CAPABILITY
                graph.add_edge(
                    CapabilityEdge(
                        edge_id=f"edge:{op_node_id}->requires->{cap_node_id}",
                        from_node_id=op_node_id,
                        to_node_id=cap_node_id,
                        edge_type=CapabilityEdgeType.REQUIRES,
                    )
                )

        graph.validate()
        return graph
