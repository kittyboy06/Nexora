"""Sequential Fleet Coordinator executing DAG nodes under InferenceGuard with fail-fast safety."""

import asyncio
import logging
from collections import defaultdict, deque
from typing import Any, Awaitable, Callable
from backend.app.agent.fleet.catalog import SpecialistCatalog
from backend.app.agent.fleet.models import (
    Artifact,
    FleetNode,
    FleetNodeState,
    FleetPlan,
    FleetResult,
)
from backend.app.agent.fleet.runtime import AgentRuntime, AgentRuntimeFactory
from backend.app.agent.fleet.validator import DAGValidator
from backend.app.core.guard import InferenceGuard
from backend.app.tools.registry import ToolRegistry

logger = logging.getLogger("nexora.fleet.coordinator")


class FleetCoordinator:
    """Coordinates the deterministic, sequential execution of a validated FleetPlan DAG."""

    def __init__(
        self,
        catalog: SpecialistCatalog | None = None,
        tool_registry: ToolRegistry | None = None,
        guard: InferenceGuard | None = None,
        node_runner: Callable[[AgentRuntime, FleetNode], Awaitable[Any]] | None = None,
    ) -> None:
        self.catalog = catalog or SpecialistCatalog()
        self.tool_registry = tool_registry or ToolRegistry()
        self.guard = guard
        self.node_runner = node_runner

    async def execute_fleet(self, plan: FleetPlan) -> FleetResult:
        """Execute a fleet plan sequentially following topological order.

        Args:
            plan: The validated FleetPlan to execute.

        Returns:
            FleetResult: Final aggregated results and artifacts.
        """
        # 1. Structural and policy validation
        topological_order = DAGValidator.validate(
            plan=plan,
            tool_registry=self.tool_registry,
            specialist_catalog=self.catalog._profiles,
        )

        logger.info(
            "Starting execution of Fleet '%s' (parent_task=%s, nodes=%d, order=%s)",
            plan.fleet_id,
            plan.parent_task_id,
            len(topological_order),
            " -> ".join(topological_order),
        )

        artifacts: dict[str, Artifact] = {}
        node_artifact_map: dict[str, str] = {}  # node_id -> artifact_id

        # Build adjacency for downstream blocking: parent -> [children]
        dependents_map = defaultdict(list)
        for nid, node in plan.nodes.items():
            for dep in node.dependencies:
                dependents_map[dep].append(nid)

        # 2. Sequential execution loop
        for node_id in topological_order:
            node = plan.nodes[node_id]

            # If node was already marked BLOCKED or CANCELLED, skip execution
            if node.state in (FleetNodeState.BLOCKED, FleetNodeState.CANCELLED):
                logger.info("Skipping node '%s' in state %s", node_id, node.state.value)
                continue

            # Verify all dependencies are COMPLETED
            unmet_deps = [dep for dep in node.dependencies if plan.nodes[dep].state != FleetNodeState.COMPLETED]
            if unmet_deps:
                node.state = FleetNodeState.BLOCKED
                node.error = f"Dependencies unmet: {unmet_deps}"
                self._block_downstream(node_id, plan, dependents_map)
                continue

            node.state = FleetNodeState.RUNNING
            logger.info("Executing node '%s' (role=%s, objective=%s)", node_id, node.role, node.objective)

            # Gather resolved input artifacts
            input_artifacts: list[Artifact] = []
            for dep_id in node.dependencies:
                art_id = node_artifact_map.get(dep_id)
                if art_id and art_id in artifacts:
                    input_artifacts.append(artifacts[art_id])

            for explicit_art_id in node.input_artifact_refs:
                if explicit_art_id in artifacts and artifacts[explicit_art_id] not in input_artifacts:
                    input_artifacts.append(artifacts[explicit_art_id])

            # Instantiate isolated runtime
            runtime = AgentRuntimeFactory.create_runtime(
                node=node,
                catalog=self.catalog,
                input_artifacts=input_artifacts,
                tool_registry=self.tool_registry,
            )

            # Execute node within hardware lock
            try:
                if self.guard:
                    async with self.guard.acquire():
                        output = await self._run_node_internal(runtime, node)
                else:
                    output = await self._run_node_internal(runtime, node)

                # Successful completion: create and record immutable artifact
                artifact = Artifact.create(
                    node_id=node.node_id,
                    producer_role=node.role,
                    content=output if output is not None else {"status": "success"},
                )
                artifacts[artifact.artifact_id] = artifact
                node_artifact_map[node_id] = artifact.artifact_id
                node.result_artifact_id = artifact.artifact_id
                node.state = FleetNodeState.COMPLETED
                logger.info("Node '%s' completed successfully. Artifact: %s", node_id, artifact.artifact_id)

            except Exception as exc:
                logger.exception("Node '%s' failed during execution: %s", node_id, exc)
                node.state = FleetNodeState.FAILED
                node.error = str(exc)

                # Fail-fast: block all downstream dependents and halt execution
                self._block_downstream(node_id, plan, dependents_map)
                break

        # 3. Aggregate FleetResult
        all_completed = all(n.state == FleetNodeState.COMPLETED for n in plan.nodes.values())
        any_failed = any(n.state == FleetNodeState.FAILED for n in plan.nodes.values())

        if all_completed:
            summary = f"All {len(plan.nodes)} specialist nodes completed successfully."
        elif any_failed:
            failed_nodes = [n.node_id for n in plan.nodes.values() if n.state == FleetNodeState.FAILED]
            blocked_nodes = [n.node_id for n in plan.nodes.values() if n.state == FleetNodeState.BLOCKED]
            summary = (
                f"Fleet execution halted due to failure in node(s): {failed_nodes}. "
                f"Downstream node(s) blocked: {blocked_nodes}."
            )
        else:
            summary = "Fleet execution finished with partial outcomes."

        return FleetResult(
            fleet_id=plan.fleet_id,
            parent_task_id=plan.parent_task_id,
            node_outcomes={nid: node.state for nid, node in plan.nodes.items()},
            artifacts=list(artifacts.values()),
            summary=summary,
            is_verified=all_completed,
            error=plan.nodes[failed_nodes[0]].error if any_failed else None,
        )

    def _block_downstream(
        self,
        failed_node_id: str,
        plan: FleetPlan,
        dependents_map: dict[str, list[str]],
    ) -> None:
        """Recursively mark all direct and indirect downstream dependents as BLOCKED."""
        queue = deque(dependents_map.get(failed_node_id, []))
        visited = set()

        while queue:
            child_id = queue.popleft()
            if child_id in visited:
                continue
            visited.add(child_id)

            child_node = plan.nodes.get(child_id)
            if child_node and child_node.state in (FleetNodeState.QUEUED, FleetNodeState.READY):
                child_node.state = FleetNodeState.BLOCKED
                child_node.error = f"Blocked due to upstream failure in '{failed_node_id}'."
                logger.warning("Marking downstream node '%s' as BLOCKED.", child_id)

            for grandchild in dependents_map.get(child_id, []):
                if grandchild not in visited:
                    queue.append(grandchild)

    async def _run_node_internal(self, runtime: AgentRuntime, node: FleetNode) -> Any:
        """Internal dispatch invoking the provided node_runner or simulated completion."""
        if self.node_runner:
            return await self.node_runner(runtime, node)
        
        # Default fallback returns structured acknowledgment
        return {
            "node_id": node.node_id,
            "role": node.role,
            "objective": node.objective,
            "status": "completed",
        }
