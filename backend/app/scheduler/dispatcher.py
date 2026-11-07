"""Task dispatcher bridging schedule triggers into standard AgentTasks with capacity guards."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from backend.app.agent.task_manager import TaskManager
from backend.app.core.config import get_settings
from backend.app.core.exceptions import TaskRunnerBusyException
from backend.app.models.agent import TaskStatus
from backend.app.scheduler.clock import Clock
from backend.app.scheduler.models import (
    ConcurrencyPolicy,
    RunStatus,
    Schedule,
    ScheduleRun,
    ScheduleStatus,
    TriggerType,
    compute_template_hash,
)
from backend.app.scheduler.recurrence import RecurrenceEngine
from backend.app.scheduler.store import ScheduleStore

logger = logging.getLogger("nexora.scheduler.dispatcher")


class TaskDispatcher:
    """Dispatches scheduled executions to TaskManager with capacity & drift guards."""

    def __init__(self, store: ScheduleStore, task_manager: TaskManager, clock: Clock):
        self.store = store
        self.task_manager = task_manager
        self.clock = clock

    async def dispatch_due_schedule(
        self, schedule: Schedule, scheduled_for: datetime
    ) -> Optional[ScheduleRun]:
        """
        Evaluate and dispatch a due schedule tick.
        Guards against template drift, capacity saturation, and double dispatches.
        """
        now = self.clock.now_utc()

        # 1. Tamper / Drift Guard
        current_hash = compute_template_hash(schedule.prompt_template, schedule.model_profile_id)
        if current_hash != schedule.template_hash:
            logger.warning(
                "Template drift detected for schedule '%s' (%s). Pausing schedule.",
                schedule.name,
                schedule.id,
            )
            schedule.status = ScheduleStatus.PAUSED_INVALIDATED
            schedule.updated_at = now
            self.store.update_schedule(schedule)

            # Record skipped run lease for audit trail
            run = self.store.acquire_run_lease(
                schedule_id=schedule.id,
                scheduled_for=scheduled_for,
                clock_now=now,
                initial_status=RunStatus.SKIPPED,
            )
            if run:
                run = self.store.update_run(
                    run_id=run.run_id,
                    status=RunStatus.SKIPPED,
                    finished_at=now,
                    error_message="Template or model profile drift detected. Schedule paused for safety review.",
                )
            return run

        # 2. Capacity Guard (Single-Tenant Limit)
        if self.task_manager.is_busy:
            if schedule.concurrency_policy == ConcurrencyPolicy.SKIP_BUSY:
                logger.info(
                    "Capacity busy. Skipping tick for schedule '%s' per SKIP_BUSY policy.",
                    schedule.name,
                )
                run = self.store.acquire_run_lease(
                    schedule_id=schedule.id,
                    scheduled_for=scheduled_for,
                    clock_now=now,
                    initial_status=RunStatus.BLOCKED_BUSY,
                )
                if run:
                    run = self.store.update_run(
                        run_id=run.run_id,
                        status=RunStatus.BLOCKED_BUSY,
                        finished_at=now,
                        error_message="Execution skipped: agent task runner is busy.",
                    )
                self._advance_schedule(schedule, scheduled_for, now)
                return run

            elif schedule.concurrency_policy == ConcurrencyPolicy.RETRY_GRACE:
                # Check if grace window has expired
                grace_delta = timedelta(seconds=schedule.retry_grace_seconds)
                if now > (scheduled_for + grace_delta):
                    logger.warning(
                        "Grace window (%ss) expired for schedule '%s'. Marking BLOCKED_BUSY.",
                        schedule.retry_grace_seconds,
                        schedule.name,
                    )
                    run = self.store.acquire_run_lease(
                        schedule_id=schedule.id,
                        scheduled_for=scheduled_for,
                        clock_now=now,
                        initial_status=RunStatus.BLOCKED_BUSY,
                    )
                    if run:
                        run = self.store.update_run(
                            run_id=run.run_id,
                            status=RunStatus.BLOCKED_BUSY,
                            finished_at=now,
                            error_message=f"Agent capacity busy: retry grace window ({schedule.retry_grace_seconds}s) expired.",
                        )
                    self._advance_schedule(schedule, scheduled_for, now)
                    return run
                else:
                    logger.info(
                        "Capacity busy for schedule '%s'. Retrying within grace window (%ss remaining).",
                        schedule.name,
                        int(((scheduled_for + grace_delta) - now).total_seconds()),
                    )
                    return None

        # 3. Capacity is Free: Acquire Atomic Run Lease
        run = self.store.acquire_run_lease(
            schedule_id=schedule.id,
            scheduled_for=scheduled_for,
            clock_now=now,
            initial_status=RunStatus.DISPATCHED,
        )
        if run is None:
            # Another worker or tick already claimed this run lease
            return None

        # 4. Create standard AgentTask
        try:
            task = await self.task_manager.state_manager.create_task(
                prompt=schedule.prompt_template,
                model_profile_id=schedule.model_profile_id,
            )
            self.store.update_run(run_id=run.run_id, status=RunStatus.DISPATCHED, task_id=task.task_id)
            run.task_id = task.task_id
        except Exception as exc:
            logger.exception("Failed to create agent task for schedule '%s': %s", schedule.name, exc)
            self.store.update_run(
                run_id=run.run_id,
                status=RunStatus.FAILED,
                finished_at=now,
                error_message=f"Failed to create agent task: {exc}",
            )
            self._advance_schedule(schedule, scheduled_for, now)
            return run

        # 5. Advance Schedule Recurrence
        self._advance_schedule(schedule, scheduled_for, now)

        # 6. Dispatch background task execution & monitoring
        asyncio.create_task(self._monitor_execution(run.run_id, task.task_id))
        return run

    async def trigger_manual_run(self, schedule_id: str) -> ScheduleRun:
        """Trigger an out-of-band immediate manual run of an existing schedule."""
        schedule = self.store.get_schedule(schedule_id)
        if not schedule:
            raise ValueError(f"Schedule '{schedule_id}' not found.")

        if self.task_manager.is_busy:
            raise TaskRunnerBusyException(
                message=f"Agent capacity is currently busy. Cannot trigger '{schedule.name}' right now."
            )

        now = self.clock.now_utc()
        run = self.store.acquire_run_lease(
            schedule_id=schedule.id,
            scheduled_for=now,
            clock_now=now,
            initial_status=RunStatus.DISPATCHED,
        )
        if not run:
            raise RuntimeError("Failed to acquire run lease for manual trigger.")

        task = await self.task_manager.state_manager.create_task(
            prompt=schedule.prompt_template,
            model_profile_id=schedule.model_profile_id,
        )
        self.store.update_run(run_id=run.run_id, status=RunStatus.DISPATCHED, task_id=task.task_id)
        run.task_id = task.task_id

        # Update last run timestamp
        schedule.last_run_at = now
        schedule.updated_at = now
        self.store.update_schedule(schedule)

        asyncio.create_task(self._monitor_execution(run.run_id, task.task_id))
        return run

    def _advance_schedule(self, schedule: Schedule, scheduled_for: datetime, now: datetime) -> None:
        """Advance schedule's last_run_at and next_run_at."""
        schedule.last_run_at = scheduled_for
        schedule.updated_at = now

        if schedule.trigger_type == TriggerType.ONE_SHOT:
            schedule.status = ScheduleStatus.COMPLETED
            schedule.next_run_at = None
        else:
            schedule.next_run_at = RecurrenceEngine.calculate_next_run(
                trigger_type=schedule.trigger_type,
                trigger_expression=schedule.trigger_expression,
                timezone_str=schedule.timezone,
                reference_utc=now,
                last_run_at=scheduled_for,
            )

        self.store.update_schedule(schedule)

    async def _monitor_execution(self, run_id: str, task_id: str) -> None:
        """Monitor running task, handle approval timeout, and update run record."""
        approval_timeout_seconds = getattr(get_settings(), "APPROVAL_EXPIRATION_SECONDS", 600.0)

        # Launch the task execution with lock in background
        exec_task = asyncio.create_task(self.task_manager._execute_with_lock(task_id))

        try:
            # Wait for execution step/turn to finish
            await exec_task

            # Check if task is paused waiting for operator approval
            task = await self.task_manager.state_manager.get_task(task_id)
            if task and task.status == TaskStatus.WAITING_APPROVAL and task.pending_approval:
                while True:
                    await asyncio.sleep(0.05)
                    task = await self.task_manager.state_manager.get_task(task_id)
                    if not task or task.status != TaskStatus.WAITING_APPROVAL:
                        break

                    now_utc = self.clock.now_utc()
                    is_expired = False
                    if task.pending_approval.expires_at and now_utc >= task.pending_approval.expires_at:
                        is_expired = True
                    elif task.pending_approval.created_at:
                        elapsed = (now_utc - task.pending_approval.created_at).total_seconds()
                        if elapsed >= approval_timeout_seconds:
                            is_expired = True

                    if is_expired:
                        logger.warning(
                            "Approval for task %s expired. Cancelling task.",
                            task_id,
                        )
                        await self.task_manager.state_manager.transition_state(
                            task_id,
                            TaskStatus.CANCELLED,
                            error_message="Operator approval expired after timeout.",
                        )
                        self.store.update_run(
                            run_id=run_id,
                            status=RunStatus.EXPIRED_APPROVAL,
                            finished_at=now_utc,
                            error_message="Operator approval expired after timeout.",
                        )
                        return

            # Final state update
            task = await self.task_manager.state_manager.get_task(task_id)
            now = self.clock.now_utc()
            if task:
                if task.status == TaskStatus.COMPLETED:
                    self.store.update_run(run_id=run_id, status=RunStatus.COMPLETED, finished_at=now)
                elif task.status == TaskStatus.CANCELLED:
                    self.store.update_run(
                        run_id=run_id,
                        status=RunStatus.FAILED,
                        finished_at=now,
                        error_message=task.error_message or "Task was cancelled.",
                    )
                elif task.status == TaskStatus.FAILED:
                    self.store.update_run(
                        run_id=run_id,
                        status=RunStatus.FAILED,
                        finished_at=now,
                        error_message=task.error_message or "Task failed.",
                    )
        except asyncio.CancelledError:
            logger.info("Monitoring task for run %s was cancelled.", run_id)
        except Exception as exc:
            logger.exception("Error while monitoring task execution for run %s: %s", run_id, exc)
            self.store.update_run(
                run_id=run_id,
                status=RunStatus.FAILED,
                finished_at=self.clock.now_utc(),
                error_message=str(exc),
            )
