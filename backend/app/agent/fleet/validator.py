"""Deterministic DAG Validator and Topological Sorter for Agent Fleet Plans."""

from collections import defaultdict, deque
from typing import Any
from backend.app.agent.fleet.models import FleetPlan


class DAGValidationError(Exception):
    """Base error raised when a FleetPlan DAG fails structural or policy validation."""
    pass


class DAGCycleDetectedError(DAGValidationError):
    """Raised when circular dependencies are detected in the fleet graph."""
    pass


class DAGValidator:
    """Validates structural acyclicity, referential integrity, and capability bounds of a FleetPlan."""

    @staticmethod
    def validate(
        plan: FleetPlan,
        tool_registry: Any | None = None,
        specialist_catalog: dict[str, Any] | None = None,
    ) -> list[str]:
        """Validate the fleet plan and return a deterministic topological execution order.

        Args:
            plan: The FleetPlan to validate.
            tool_registry: Optional ToolRegistry to verify registered capabilities.
            specialist_catalog: Optional specialist catalog to verify profile bounds.

        Returns:
            list[str]: Deterministic topological order of node_ids.

        Raises:
            DAGValidationError: If node count, references, or capability checks fail.
            DAGCycleDetectedError: If a cycle is detected.
        """
        nodes = plan.nodes
        total_nodes = len(nodes)

        # 1. Bounds check: must have at least 1 node and not exceed max_nodes (cap 5)
        if total_nodes == 0:
            raise DAGValidationError("Fleet plan must contain at least 1 node.")
        if total_nodes > plan.max_nodes:
            raise DAGValidationError(
                f"Fleet plan exceeds maximum allowed nodes ({total_nodes} > {plan.max_nodes})."
            )

        # 2. Key-ID consistency & self-dependency check
        for key, node in nodes.items():
            if key != node.node_id:
                raise DAGValidationError(
                    f"Node dictionary key '{key}' does not match node_id '{node.node_id}'."
                )
            if node.node_id in node.dependencies:
                raise DAGCycleDetectedError(
                    f"Self-dependency detected on node '{node.node_id}'."
                )

        # 3. Referential integrity: all dependencies must exist in the plan
        for node in nodes.values():
            for dep in node.dependencies:
                if dep not in nodes:
                    raise DAGValidationError(
                        f"Node '{node.node_id}' depends on nonexistent node '{dep}'."
                    )

        # 4. Capability enclosure checks
        for node in nodes.values():
            # Check against specialist catalog if provided
            if specialist_catalog and node.role in specialist_catalog:
                profile = specialist_catalog[node.role]
                allowed_caps = getattr(profile, "capability_allowlist", None)
                if allowed_caps is None and isinstance(profile, dict):
                    allowed_caps = profile.get("capability_allowlist", [])
                
                if allowed_caps is not None:
                    for cap in node.capability_allowlist:
                        if cap not in allowed_caps:
                            raise DAGValidationError(
                                f"Node '{node.node_id}' requested capability '{cap}' not permitted for role '{node.role}'."
                            )

            # Check against ToolRegistry if provided
            if tool_registry:
                for cap in node.capability_allowlist:
                    # Support get(name), has_tool(name), or get_tool_names()
                    has_capability = False
                    if hasattr(tool_registry, "get"):
                        has_capability = tool_registry.get(cap) is not None
                    elif hasattr(tool_registry, "has_tool"):
                        has_capability = tool_registry.has_tool(cap)
                    elif hasattr(tool_registry, "get_tool_names"):
                        has_capability = cap in tool_registry.get_tool_names()

                    if not has_capability:
                        raise DAGValidationError(
                            f"Node '{node.node_id}' requested unregistered capability '{cap}'."
                        )

        # 5. Kahn's Algorithm for Topological Sort & Cycle Detection
        in_degree = {nid: 0 for nid in nodes}
        adjacency = defaultdict(list)

        for nid, node in nodes.items():
            for dep in node.dependencies:
                # dep -> nid (dep must complete before nid)
                adjacency[dep].append(nid)
                in_degree[nid] += 1

        # Queue nodes with in-degree 0 (sorted by node_id for deterministic order)
        ready_queue = deque(sorted([nid for nid, deg in in_degree.items() if deg == 0]))
        topological_order: list[str] = []

        while ready_queue:
            current = ready_queue.popleft()
            topological_order.append(current)

            # Collect unblocked neighbors
            next_unblocked = []
            for neighbor in adjacency[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    next_unblocked.append(neighbor)

            # Sort unblocked nodes deterministically before adding to queue
            for unblocked in sorted(next_unblocked):
                ready_queue.append(unblocked)

        if len(topological_order) != total_nodes:
            raise DAGCycleDetectedError(
                f"Circular dependency detected in fleet plan. Sorted {len(topological_order)} of {total_nodes} nodes."
            )

        return topological_order
