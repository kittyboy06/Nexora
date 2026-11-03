import asyncio
import logging
from fastapi import BackgroundTasks

from backend.app.agent.orchestrator import AgentOrchestrator
from backend.app.agent.state_manager import StateManager
from backend.app.core.exceptions import (
    ApprovalInvalidatedException,
    TaskRunnerBusyException,
)
from backend.app.models.agent import AgentTask, TaskStatus
from backend.app.permissions.manager import PermissionManager

logger = logging.getLogger("nexora.task_manager")


class TaskManager:
    """Manages active task lifecycle and concurrency bounds (max 1 active task)."""

    def __init__(
        self,
        state_manager: StateManager,
        orchestrator: AgentOrchestrator,
        permissions: PermissionManager,
    ):
        self.state_manager = state_manager
        self.orchestrator = orchestrator
        self.permissions = permissions
        self._task_lock = asyncio.Lock()
        self._active_task_id: str | None = None

    @property
    def is_busy(self) -> bool:
        """Whether a task is currently executing."""
        return self._task_lock.locked()

    async def _execute_with_lock(self, task_id: str, pre_authorized_step_id: int | None = None) -> None:
        """Background wrapper acquiring the single-task execution lock."""
        async with self._task_lock:
            self._active_task_id = task_id
            logger.info("Acquired task execution lock for %s", task_id)
            try:
                await self.orchestrator.run_task(task_id, pre_authorized_step_id=pre_authorized_step_id)
            except Exception as exc:
                logger.exception("Unexpected exception in background orchestrator for %s: %s", task_id, exc)
                try:
                    await self.state_manager.transition_state(
                        task_id,
                        TaskStatus.FAILED,
                        error_message=f"Unhandled engine error: {exc}",
                    )
                except Exception:
                    pass
            finally:
                self._active_task_id = None
                logger.info("Released task execution lock for %s", task_id)

    async def create_and_start_task(self, prompt: str, background_tasks: BackgroundTasks) -> AgentTask:
        """Create a new task and dispatch background execution if capacity is available."""
        if self._task_lock.locked():
            logger.warning("Rejecting task creation: TaskManager is currently running task %s", self._active_task_id)
            raise TaskRunnerBusyException(
                message=f"Agent capacity busy (task {self._active_task_id} is running). Try again once it completes."
            )

        task = await self.state_manager.create_task(prompt)
        background_tasks.add_task(self._execute_with_lock, task.task_id)
        return task

    async def submit_approval(
        self,
        task_id: str,
        approval_id: str,
        approved: bool,
        background_tasks: BackgroundTasks,
    ) -> AgentTask:
        """Process human approval decision and resume execution if approved."""
        task = await self.state_manager.get_task(task_id)
        if task.status != TaskStatus.WAITING_APPROVAL or not task.pending_approval:
            raise ApprovalInvalidatedException("Task is not currently waiting for approval.")

        # Find the pending step
        step_id = task.pending_approval.step_id
        step = next((s for s in task.plan.steps if s.step_id == step_id), None) if task.plan else None
        if not step:
            raise ApprovalInvalidatedException(f"Step {step_id} associated with approval not found in plan.")

        # Check approval expiration
        if await self.state_manager.check_approval_expired(task_id):
            raise ApprovalInvalidatedException("Approval window of 10 minutes has expired.")

        # Verify decision and argument integrity
        self.permissions.verify_decision(task, step, approval_id, approved)

        if not approved:
            await self.state_manager.clear_pending_approval(task_id)
            await self.state_manager.transition_state(task_id, TaskStatus.REJECTED, error_message="User rejected tool execution.")
            task = await self.state_manager.transition_state(task_id, TaskStatus.FAILED, error_message="Step rejected by user.")
            return task

        # Decision is approved
        await self.state_manager.clear_pending_approval(task_id)
        task = await self.state_manager.transition_state(task_id, TaskStatus.APPROVED)

        # Dispatch resumption via background task
        background_tasks.add_task(self._execute_with_lock, task_id, step_id)
        return task

    async def cancel_task(self, task_id: str) -> AgentTask:
        """Cancel a task if it is active."""
        return await self.state_manager.transition_state(task_id, TaskStatus.CANCELLED, error_message="Cancelled by user.")
