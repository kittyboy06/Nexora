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
        self._running_task: asyncio.Task | None = None

    @property
    def is_busy(self) -> bool:
        """Whether a task is currently executing."""
        return self._task_lock.locked()

    async def _execute_with_lock(self, task_id: str, pre_authorized_step_id: int | None = None) -> None:
        """Background wrapper acquiring the single-task execution lock."""
        async with self._task_lock:
            self._active_task_id = task_id
            self._running_task = asyncio.current_task()
            logger.info("Acquired task execution lock for %s", task_id)
            try:
                await self.orchestrator.run_task(task_id, pre_authorized_step_id=pre_authorized_step_id)
            except asyncio.CancelledError:
                logger.info("Task %s background execution was cancelled.", task_id)
                try:
                    current = await self.state_manager.get_task(task_id)
                    if current.status not in (TaskStatus.CANCELLED, TaskStatus.FAILED, TaskStatus.COMPLETED):
                        await self.state_manager.transition_state(
                            task_id,
                            TaskStatus.CANCELLED,
                            error_message="Cancelled by user.",
                        )
                except Exception:
                    pass
                raise
            except Exception as exc:
                logger.exception("Unexpected exception in background orchestrator for %s: %s", task_id, exc)
                try:
                    current = await self.state_manager.get_task(task_id)
                    if current.status not in (TaskStatus.CANCELLED, TaskStatus.FAILED, TaskStatus.COMPLETED):
                        await self.state_manager.transition_state(
                            task_id,
                            TaskStatus.FAILED,
                            error_message=f"Unhandled engine error: {exc}",
                        )
                except Exception:
                    pass
            finally:
                self._active_task_id = None
                self._running_task = None
                logger.info("Released task execution lock for %s", task_id)

    async def create_and_start_task(
        self, prompt: str, background_tasks: BackgroundTasks, model_profile_id: str | None = None
    ) -> AgentTask:
        """Create a new task and dispatch background execution if capacity is available."""
        # If lock is held, verify if the currently active task has already terminated or been cancelled
        if self._task_lock.locked():
            if self._active_task_id:
                try:
                    active = await self.state_manager.get_task(self._active_task_id)
                    if active.status in (TaskStatus.CANCELLED, TaskStatus.COMPLETED, TaskStatus.FAILED):
                        logger.warning(
                            "Lock held for %s but task status is terminal (%s). Forcing background cleanup...",
                            self._active_task_id, active.status
                        )
                        if self._running_task and not self._running_task.done():
                            self._running_task.cancel()
                        # Yield to let lock release
                        for _ in range(10):
                            if not self._task_lock.locked():
                                break
                            await asyncio.sleep(0.05)
                        # Fail-safe: if lock is STILL held for a terminal task, break the dead lock
                        if self._task_lock.locked():
                            logger.warning(
                                "Lock deadlocked for terminal task %s (%s). Force-resetting task lock.",
                                self._active_task_id, active.status
                            )
                            self._task_lock = asyncio.Lock()
                            self._active_task_id = None
                            self._running_task = None
                except Exception as exc:
                    logger.warning("Error checking active task terminal status: %s", exc)
            else:
                # Orphaned lock with no active task ID
                logger.warning("Lock held with no active task ID. Force-resetting task lock.")
                self._task_lock = asyncio.Lock()
                self._active_task_id = None
                self._running_task = None

        if self._task_lock.locked():
            logger.warning("Rejecting task creation: TaskManager is currently running task %s", self._active_task_id)
            raise TaskRunnerBusyException(
                message=f"Agent capacity busy (task {self._active_task_id} is running). Try again once it completes."
            )

        task = await self.state_manager.create_task(prompt, model_profile_id=model_profile_id)
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
        try:
            task = await self.state_manager.transition_state(task_id, TaskStatus.CANCELLED, error_message="Cancelled by user.")
        except Exception:
            task = await self.state_manager.get_task(task_id)

        # Immediately cancel the background task if active
        if self._active_task_id == task_id and self._running_task and not self._running_task.done():
            logger.info("Immediately cancelling running background asyncio task for %s", task_id)
            self._running_task.cancel()
            # Wait briefly for cancellation to propagate and release the lock
            for _ in range(10):
                if not self._task_lock.locked():
                    break
                await asyncio.sleep(0.05)

        # Fail-safe: if the lock is STILL held by this cancelled task or orphaned, reset it immediately
        if self._task_lock.locked() and (self._active_task_id == task_id or self._active_task_id is None):
            logger.warning("Force-resetting task lock after cancellation of %s", task_id)
            self._task_lock = asyncio.Lock()
            self._active_task_id = None
            self._running_task = None

        return task
