import asyncio
import logging
import time
from typing import Any

from backend.app.agent.state_manager import StateManager
from backend.app.core.config import Settings
from backend.app.models.agent import (
    AgentTask,
    PlanStep,
    RetryClassification,
    StepResult,
    StepStatus,
    TaskStatus,
)
from backend.app.permissions.manager import PermissionManager
from backend.app.tools.registry import ToolRegistry

logger = logging.getLogger("nexora.executor")


class Executor:
    """Step execution runner enforcing immediate permission checks and tri-state retries."""

    def __init__(
        self,
        registry: ToolRegistry,
        permissions: PermissionManager,
        state_manager: StateManager,
        settings: Settings,
    ):
        self.registry = registry
        self.permissions = permissions
        self.state_manager = state_manager
        self.settings = settings

    def classify_error(self, exc: Exception) -> RetryClassification:
        """Categorize execution failures to prevent unsafe replays."""
        if isinstance(exc, (TimeoutError, asyncio.TimeoutError, ConnectionError)):
            return RetryClassification.TRANSIENT
        if isinstance(exc, (ValueError, TypeError, KeyError, AttributeError)):
            return RetryClassification.PERMANENT
        # Any unexpected or ambiguous error is treated as UNCERTAIN
        return RetryClassification.UNCERTAIN

    async def execute_step(
        self,
        task: AgentTask,
        step: PlanStep,
        pre_authorized: bool = False,
    ) -> tuple[StepResult | None, bool]:
        """
        Execute a single plan step.
        Returns: (StepResult | None, is_paused_for_approval: bool)
        """
        # 1. Immediate Pre-Execution Permission Gate
        if not pre_authorized:
            authorized, approval = self.permissions.evaluate_permission(step, task)
            if not authorized and approval:
                await self.state_manager.set_pending_approval(task.task_id, approval)
                await self.state_manager.transition_state(task.task_id, TaskStatus.WAITING_APPROVAL)
                logger.info("Task %s paused waiting for human approval on step %d", task.task_id, step.step_id)
                return None, True

        tool = self.registry.get(step.tool_call.tool_name)
        if not tool:
            res = StepResult(
                step_id=step.step_id,
                tool_name=step.tool_call.tool_name,
                status=StepStatus.FAILED,
                error=f"Tool '{step.tool_call.tool_name}' not registered",
                duration_ms=0.0,
                retry_classification=RetryClassification.PERMANENT,
            )
            step.status = StepStatus.FAILED
            await self.state_manager.append_step_result(task.task_id, res)
            return res, False

        step.status = StepStatus.RUNNING
        logger.info("Executing step %d: %s with args %s", step.step_id, tool.name, step.tool_call.arguments)

        # 2. Execution with Tri-State Retry Loop
        attempt = 0
        while attempt <= self.settings.MAX_RETRIES_PER_STEP:
            start_time = time.perf_counter()
            try:
                await self.state_manager.increment_iterations(task.task_id)
                output = await tool.execute(**step.tool_call.arguments)
                duration_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

                res = StepResult(
                    step_id=step.step_id,
                    tool_name=tool.name,
                    status=StepStatus.SUCCEEDED,
                    output=output,
                    duration_ms=duration_ms,
                )
                step.status = StepStatus.SUCCEEDED
                await self.state_manager.append_step_result(task.task_id, res)
                logger.info("Step %d (%s) SUCCEEDED in %.2fms", step.step_id, tool.name, duration_ms)
                return res, False

            except Exception as exc:
                duration_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
                classification = self.classify_error(exc)
                logger.warning(
                    "Step %d execution error (%s): %s (attempt %d/%d)",
                    step.step_id,
                    classification.value,
                    exc,
                    attempt,
                    self.settings.MAX_RETRIES_PER_STEP,
                )

                if classification == RetryClassification.TRANSIENT and attempt < self.settings.MAX_RETRIES_PER_STEP:
                    attempt += 1
                    step.retries_attempted = attempt
                    await asyncio.sleep(0.1)  # Brief backoff
                    continue

                # For PERMANENT, UNCERTAIN, or exhausted TRANSIENT retries:
                res = StepResult(
                    step_id=step.step_id,
                    tool_name=tool.name,
                    status=StepStatus.FAILED,
                    error=str(exc),
                    duration_ms=duration_ms,
                    retry_classification=classification,
                )
                step.status = StepStatus.FAILED
                await self.state_manager.append_step_result(task.task_id, res)
                return res, False

        return None, False
