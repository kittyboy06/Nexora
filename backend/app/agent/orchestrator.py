import asyncio
import logging
import time

from backend.app.agent.executor import Executor
from backend.app.agent.planner import Planner
from backend.app.agent.result_evaluator import ResultEvaluator
from backend.app.agent.fleet.coordinator import FleetCoordinator
from backend.app.agent.fleet.models import FleetPlan, FleetResult
from backend.app.agent.state_manager import StateManager
from backend.app.core.config import Settings
from backend.app.models.agent import RetryClassification, StepStatus, TaskStatus

logger = logging.getLogger("nexora.orchestrator")


class AgentOrchestrator:
    """Coordinates the high-level hybrid agent execution loop."""

    def __init__(
        self,
        state_manager: StateManager,
        planner: Planner,
        executor: Executor,
        evaluator: ResultEvaluator,
        settings: Settings,
        fleet_coordinator: FleetCoordinator | None = None,
    ):
        self.state_manager = state_manager
        self.planner = planner
        self.executor = executor
        self.evaluator = evaluator
        self.settings = settings
        self.fleet_coordinator = fleet_coordinator

    async def run_task(self, task_id: str, pre_authorized_step_id: int | None = None) -> None:
        """Execute or resume an agent task through the complete lifecycle."""
        start_time = time.perf_counter()
        task = await self.state_manager.get_task(task_id)

        # 1. Parsing & Planning (if not already planned)
        if task.status == TaskStatus.SUBMITTED:
            try:
                await self.state_manager.transition_state(task_id, TaskStatus.PARSING)
                # Parse intent
                await asyncio.sleep(0.01)

                await self.state_manager.transition_state(task_id, TaskStatus.PLANNING)
                selection = await self.planner.route_task(task.prompt, profile_override=task.model_profile_id)
                task = await self.state_manager.record_routing(task_id, selection)
                plan = await self.planner.generate_plan_for_route(task.prompt, selection)
                task = await self.state_manager.update_plan(task_id, plan)
                task = await self.state_manager.transition_state(task_id, TaskStatus.EXECUTING)
            except Exception as exc:
                logger.error("Planning failed for task %s: %s", task_id, exc)
                error_msg = getattr(exc, "message", str(exc))
                await self.state_manager.transition_state(task_id, TaskStatus.FAILED, error_message=error_msg)
                return

        elif task.status == TaskStatus.APPROVED:
            # Resuming execution after user approval
            task = await self.state_manager.transition_state(task_id, TaskStatus.EXECUTING)


        # Check if task is running as a Fleet Plan
        if task.fleet_plan and self.fleet_coordinator:
            logger.info("Executing task %s via FleetCoordinator (%d nodes)", task_id, len(task.fleet_plan.nodes))
            if task.status != TaskStatus.EXECUTING:
                task = await self.state_manager.transition_state(task_id, TaskStatus.EXECUTING)
            fleet_result = await self.fleet_coordinator.execute_fleet(task.fleet_plan)
            for art in fleet_result.artifacts:
                await self.state_manager.record_artifact(task_id, art)
            if fleet_result.is_verified:
                await self.state_manager.transition_state(task_id, TaskStatus.COMPLETED)
            else:
                await self.state_manager.transition_state(
                    task_id, TaskStatus.FAILED, error_message=fleet_result.error or fleet_result.summary
                )
            return

        if not task.plan:
            await self.state_manager.transition_state(task_id, TaskStatus.FAILED, error_message="Task has no plan.")
            return

        # 2. Execution Loop
        for step in task.plan.steps:
            # Check execution timeout
            elapsed = time.perf_counter() - start_time
            if elapsed > self.settings.MAX_EXECUTION_DURATION_SECONDS:
                logger.error("Task %s exceeded maximum execution duration (%.1fs)", task_id, elapsed)
                await self.state_manager.transition_state(
                    task_id,
                    TaskStatus.FAILED,
                    error_message=f"Execution duration exceeded limit of {self.settings.MAX_EXECUTION_DURATION_SECONDS}s",
                )
                return

            # Check task cancellation
            current_task = await self.state_manager.get_task(task_id)
            if current_task.status == TaskStatus.CANCELLED:
                logger.info("Task %s was cancelled by user.", task_id)
                return

            # Check iterations limit
            if current_task.iterations_used >= self.settings.MAX_EXECUTION_ITERATIONS:
                logger.error("Task %s exceeded max execution iterations (%d)", task_id, self.settings.MAX_EXECUTION_ITERATIONS)
                await self.state_manager.transition_state(
                    task_id,
                    TaskStatus.FAILED,
                    error_message=f"Exceeded maximum execution iterations limit ({self.settings.MAX_EXECUTION_ITERATIONS})",
                )
                return

            # Skip already completed steps
            if step.status == StepStatus.SUCCEEDED:
                continue

            # Verify dependencies
            deps_met = True
            for dep_id in step.dependencies:
                dep_step = next((s for s in task.plan.steps if s.step_id == dep_id), None)
                if not dep_step or dep_step.status != StepStatus.SUCCEEDED:
                    deps_met = False
                    break

            if not deps_met:
                err = f"Step {step.step_id} cannot run because dependencies were not satisfied."
                logger.error(err)
                await self.state_manager.transition_state(task_id, TaskStatus.FAILED, error_message=err)
                return

            # Determine pre-authorization
            is_pre_authorized = pre_authorized_step_id is not None and step.step_id == pre_authorized_step_id

            # Execute step
            res, is_paused = await self.executor.execute_step(task, step, pre_authorized=is_pre_authorized)
            if is_paused:
                # Execution paused waiting for human approval
                logger.info("Task %s paused at step %d for approval.", task_id, step.step_id)
                return

            # Clear one-time pre-authorization
            pre_authorized_step_id = None

            # Handle step failure
            if res and res.status == StepStatus.FAILED:
                if res.retry_classification == RetryClassification.UNCERTAIN:
                    err = f"Step {step.step_id} failed with UNCERTAIN outcome: {res.error}. Halted safely without retry."
                    logger.error(err)
                    await self.state_manager.transition_state(task_id, TaskStatus.FAILED, error_message=err)
                    return

                # Ask LLM ResultEvaluator for recovery proposal
                logger.info("Consulting ResultEvaluator for step %d failure...", step.step_id)
                decision = await self.evaluator.evaluate_failure(task, step, res)
                if decision.can_recover and decision.revised_tool_call:
                    logger.info("Attempting recovery for step %d: %s", step.step_id, decision.explanation)
                    step.tool_call = decision.revised_tool_call
                    # Re-run revised step
                    res_recovery, is_paused_rev = await self.executor.execute_step(task, step)
                    if is_paused_rev:
                        return
                    if res_recovery and res_recovery.status == StepStatus.FAILED:
                        err = f"Recovery attempt failed for step {step.step_id}: {res_recovery.error}"
                        await self.state_manager.transition_state(task_id, TaskStatus.FAILED, error_message=err)
                        return
                else:
                    err = f"Step {step.step_id} failed and cannot be recovered: {res.error} ({decision.explanation})"
                    logger.error(err)
                    await self.state_manager.transition_state(task_id, TaskStatus.FAILED, error_message=err)
                    return

        # 3. All Steps Succeeded
        await self.state_manager.transition_state(task_id, TaskStatus.COMPLETED)
        logger.info("Task %s completed successfully (%d steps).", task_id, len(task.plan.steps))


    async def run_fleet_task(self, task_id: str, fleet_plan: FleetPlan) -> FleetResult:
        """Explicitly run a task using FleetCoordinator."""
        await self.state_manager.update_fleet_plan(task_id, fleet_plan)
        if not self.fleet_coordinator:
            raise RuntimeError("FleetCoordinator is not configured on AgentOrchestrator.")

        task = await self.state_manager.get_task(task_id)
        if task.status != TaskStatus.EXECUTING:
            await self.state_manager.transition_state(task_id, TaskStatus.EXECUTING)

        result = await self.fleet_coordinator.execute_fleet(fleet_plan)
        for art in result.artifacts:
            await self.state_manager.record_artifact(task_id, art)

        if result.is_verified:
            await self.state_manager.transition_state(task_id, TaskStatus.COMPLETED)
        else:
            await self.state_manager.transition_state(
                task_id, TaskStatus.FAILED, error_message=result.error or result.summary
            )
        return result
