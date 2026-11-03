import logging
from typing import Any
from pydantic import ValidationError
from backend.app.core.config import Settings
from backend.app.core.exceptions import PlanValidationException
from backend.app.models.agent import PlanStep, TaskPlan
from backend.app.tools.registry import ToolRegistry

logger = logging.getLogger("nexora.plan_validator")


class PlanValidator:
    """Pure Python rule engine validating TaskPlans before execution."""

    def __init__(self, registry: ToolRegistry, settings: Settings):
        self.registry = registry
        self.settings = settings

    def _check_cycles(self, steps: list[PlanStep]) -> None:
        """Check for cycles in step dependency graph using DFS."""
        adj: dict[int, list[int]] = {s.step_id: s.dependencies for s in steps}
        visited: dict[int, int] = {}  # 0: unvisited, 1: visiting, 2: visited

        for step_id in adj:
            visited[step_id] = 0

        def dfs(node: int, path: list[int]) -> None:
            visited[node] = 1
            for neighbor in adj.get(node, []):
                if neighbor not in visited:
                    continue  # Invalid reference handled separately
                if visited[neighbor] == 1:
                    cycle = path + [neighbor]
                    raise PlanValidationException(
                        f"Cyclic dependency detected: {' -> '.join(map(str, cycle))}",
                        details={"cycle": cycle},
                    )
                if visited[neighbor] == 0:
                    dfs(neighbor, path + [neighbor])
            visited[node] = 2

        for step_id in adj:
            if visited[step_id] == 0:
                dfs(step_id, [step_id])

    def validate(self, plan: TaskPlan) -> TaskPlan:
        """Thoroughly validate plan structure, tool names, arguments, and dependencies."""
        errors: list[str] = []

        # 1. Step count check
        if not (1 <= len(plan.steps) <= self.settings.MAX_PLAN_STEPS):
            errors.append(f"Plan step count ({len(plan.steps)}) exceeds allowed limit [1, {self.settings.MAX_PLAN_STEPS}].")

        # 2. Unique Step IDs check
        step_ids = [s.step_id for s in plan.steps]
        if len(step_ids) != len(set(step_ids)):
            errors.append(f"Duplicate step IDs found: {step_ids}")

        step_id_set = set(step_ids)

        # 3. Tool and Argument Validation
        for step in plan.steps:
            tool_name = step.tool_call.tool_name
            tool = self.registry.get(tool_name)
            if not tool:
                errors.append(f"Step {step.step_id}: Tool '{tool_name}' is not registered in ToolRegistry.")
                continue

            # Ensure step risk level reflects registered tool risk level
            step.risk_level = tool.risk_level

            # Validate arguments against Pydantic schema
            try:
                tool.validate_args(step.tool_call.arguments)
            except ValidationError as ve:
                errors.append(f"Step {step.step_id}: Invalid arguments for '{tool_name}': {ve.errors()}")

            # 4. Dependency integrity check (dependencies must point to valid prior steps)
            for dep_id in step.dependencies:
                if dep_id not in step_id_set:
                    errors.append(f"Step {step.step_id}: Dependency step {dep_id} does not exist in plan.")
                elif dep_id >= step.step_id:
                    errors.append(f"Step {step.step_id}: Dependency step {dep_id} must precede step {step.step_id}.")

        if errors:
            logger.warning("Plan validation failed with %d error(s): %s", len(errors), errors)
            raise PlanValidationException(
                message=f"Plan validation failed: {'; '.join(errors)}",
                details={"errors": errors},
            )

        # 5. Dependency acyclic check
        self._check_cycles(plan.steps)

        logger.info("Plan %s passed validation (%d steps).", plan.plan_id, len(plan.steps))
        return plan
