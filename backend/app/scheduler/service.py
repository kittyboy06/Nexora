"""SchedulerService orchestrating the async ticker, CRUD operations, and execution dispatch."""

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from backend.app.agent.task_manager import TaskManager
from backend.app.core.config import get_settings
from backend.app.scheduler.clock import Clock, SystemClock
from backend.app.scheduler.database import SchedulerDatabase
from backend.app.scheduler.dispatcher import TaskDispatcher
from backend.app.scheduler.models import (
    RunStatus,
    Schedule,
    ScheduleCreate,
    ScheduleRun,
    ScheduleStatus,
    ScheduleUpdate,
    compute_template_hash,
)
from backend.app.scheduler.reconciler import StartupReconciler
from backend.app.scheduler.recurrence import RecurrenceEngine
from backend.app.scheduler.store import ScheduleStore

logger = logging.getLogger("nexora.scheduler.service")


class SchedulerService:
    """Core service managing background schedules, lifecycle ticker, and run history."""

    def __init__(
        self,
        store: ScheduleStore,
        task_manager: TaskManager,
        clock: Optional[Clock] = None,
        tick_interval_seconds: float = 1.0,
    ):
        self.store = store
        self.task_manager = task_manager
        self.clock = clock or SystemClock()
        self.tick_interval_seconds = tick_interval_seconds
        self.dispatcher = TaskDispatcher(self.store, self.task_manager, self.clock)
        self.reconciler = StartupReconciler(self.store, self.dispatcher, self.clock)
        self._running = False
        self._ticker_task: Optional[asyncio.Task] = None

    @classmethod
    def create_default(cls, task_manager: TaskManager) -> "SchedulerService":
        """Instantiate default production SchedulerService with persistent SQLite WAL database."""
        settings = get_settings()
        db_path = settings.get_scheduler_data_dir() / "nexora_scheduler.db"
        db = SchedulerDatabase(db_path)
        store = ScheduleStore(db)
        return cls(store=store, task_manager=task_manager, clock=SystemClock())

    # --- Lifecycle Management ---

    async def start(self) -> None:
        """Start scheduler service, reconcile downtime state, and launch async ticker loop."""
        if self._running:
            logger.warning("SchedulerService is already running.")
            return

        self._running = True
        logger.info("Starting SchedulerService; executing startup reconciliation...")
        try:
            await self.reconciler.reconcile_startup()
        except Exception as exc:
            logger.exception("Error during startup reconciliation: %s", exc)

        self._ticker_task = asyncio.create_task(self._ticker_loop())
        logger.info("SchedulerService background ticker loop started (interval: %.1fs).", self.tick_interval_seconds)

    async def stop(self) -> None:
        """Gracefully stop scheduler ticker loop."""
        if not self._running:
            return

        self._running = False
        if self._ticker_task and not self._ticker_task.done():
            self._ticker_task.cancel()
            try:
                await self._ticker_task
            except asyncio.CancelledError:
                pass
        self._ticker_task = None
        logger.info("SchedulerService stopped cleanly.")

    async def tick_once(self) -> int:
        """
        Execute a single scheduler tick:
        Scans all ACTIVE schedules where next_run_at <= now and dispatches due executions.
        Returns the number of schedules dispatched.
        """
        now = self.clock.now_utc()
        due_schedules = self.store.get_due_schedules(now)
        dispatched_count = 0

        for schedule in due_schedules:
            if not self._running and self._ticker_task is not None:
                break
            try:
                run = await self.dispatcher.dispatch_due_schedule(
                    schedule=schedule,
                    scheduled_for=schedule.next_run_at,
                )
                if run and run.status == RunStatus.DISPATCHED:
                    dispatched_count += 1
            except Exception as exc:
                logger.exception("Error dispatching schedule '%s' (%s): %s", schedule.name, schedule.id, exc)

        return dispatched_count

    async def _ticker_loop(self) -> None:
        """Background loop ticking at configured interval."""
        while self._running:
            try:
                await self.tick_once()
            except Exception as exc:
                logger.exception("Unexpected exception in scheduler ticker loop: %s", exc)

            try:
                await asyncio.sleep(self.tick_interval_seconds)
            except asyncio.CancelledError:
                break

    # --- Schedule Management CRUD Facade ---

    def create_schedule(self, payload: ScheduleCreate) -> Schedule:
        """Validate and create a new schedule."""
        # 1. Validate expression & timezone
        RecurrenceEngine.validate_expression(
            trigger_type=payload.trigger_type,
            trigger_expression=payload.trigger_expression,
            timezone_str=payload.timezone,
        )

        now = self.clock.now_utc()
        schedule_id = str(uuid.uuid4())
        template_hash = compute_template_hash(payload.prompt_template, payload.model_profile_id)

        # 2. Calculate initial next_run_at
        next_run_at = RecurrenceEngine.calculate_next_run(
            trigger_type=payload.trigger_type,
            trigger_expression=payload.trigger_expression,
            timezone_str=payload.timezone,
            reference_utc=now,
        )

        schedule = Schedule(
            id=schedule_id,
            name=payload.name,
            prompt_template=payload.prompt_template,
            model_profile_id=payload.model_profile_id,
            trigger_type=payload.trigger_type,
            trigger_expression=payload.trigger_expression,
            timezone=payload.timezone,
            status=ScheduleStatus.ACTIVE,
            missed_run_policy=payload.missed_run_policy,
            concurrency_policy=payload.concurrency_policy,
            max_instances=payload.max_instances,
            retry_grace_seconds=payload.retry_grace_seconds,
            next_run_at=next_run_at,
            last_run_at=None,
            template_hash=template_hash,
            created_at=now,
            updated_at=now,
        )

        return self.store.create_schedule(schedule)

    def get_schedule(self, schedule_id: str) -> Optional[Schedule]:
        """Fetch schedule by ID."""
        return self.store.get_schedule(schedule_id)

    def list_schedules(self, status: Optional[ScheduleStatus] = None) -> List[Schedule]:
        """List schedules, optionally filtered by status."""
        return self.store.list_schedules(status=status)

    def update_schedule(self, schedule_id: str, payload: ScheduleUpdate) -> Schedule:
        """Update fields of an existing schedule."""
        existing = self.store.get_schedule(schedule_id)
        if not existing:
            raise ValueError(f"Schedule '{schedule_id}' not found.")

        now = self.clock.now_utc()
        target_name = payload.name if payload.name is not None else existing.name
        target_prompt = payload.prompt_template if payload.prompt_template is not None else existing.prompt_template
        target_profile = payload.model_profile_id if payload.model_profile_id is not None else existing.model_profile_id
        target_type = payload.trigger_type if payload.trigger_type is not None else existing.trigger_type
        target_expr = payload.trigger_expression if payload.trigger_expression is not None else existing.trigger_expression
        target_tz = payload.timezone if payload.timezone is not None else existing.timezone
        target_missed = payload.missed_run_policy if payload.missed_run_policy is not None else existing.missed_run_policy
        target_concurrency = payload.concurrency_policy if payload.concurrency_policy is not None else existing.concurrency_policy
        target_grace = payload.retry_grace_seconds if payload.retry_grace_seconds is not None else existing.retry_grace_seconds

        # Validate if expression or timezone changed
        RecurrenceEngine.validate_expression(
            trigger_type=target_type,
            trigger_expression=target_expr,
            timezone_str=target_tz,
        )

        # Recalculate hash
        new_hash = compute_template_hash(target_prompt, target_profile)

        # If prompt or recurrence changed, recalculate next_run_at
        next_run = existing.next_run_at
        if (target_type != existing.trigger_type or
            target_expr != existing.trigger_expression or
            target_tz != existing.timezone):
            next_run = RecurrenceEngine.calculate_next_run(
                trigger_type=target_type,
                trigger_expression=target_expr,
                timezone_str=target_tz,
                reference_utc=now,
            )

        existing.name = target_name
        existing.prompt_template = target_prompt
        existing.model_profile_id = target_profile
        existing.trigger_type = target_type
        existing.trigger_expression = target_expr
        existing.timezone = target_tz
        existing.missed_run_policy = target_missed
        existing.concurrency_policy = target_concurrency
        existing.retry_grace_seconds = target_grace
        existing.template_hash = new_hash
        existing.next_run_at = next_run
        existing.updated_at = now

        return self.store.update_schedule(existing)

    def pause_schedule(self, schedule_id: str) -> Schedule:
        """Pause an active schedule."""
        schedule = self.store.get_schedule(schedule_id)
        if not schedule:
            raise ValueError(f"Schedule '{schedule_id}' not found.")

        schedule.status = ScheduleStatus.PAUSED
        schedule.updated_at = self.clock.now_utc()
        return self.store.update_schedule(schedule)

    def resume_schedule(self, schedule_id: str) -> Schedule:
        """Resume a paused or invalidated schedule, recalculating next run and updating hash."""
        schedule = self.store.get_schedule(schedule_id)
        if not schedule:
            raise ValueError(f"Schedule '{schedule_id}' not found.")

        now = self.clock.now_utc()
        schedule.status = ScheduleStatus.ACTIVE
        schedule.template_hash = compute_template_hash(schedule.prompt_template, schedule.model_profile_id)
        schedule.next_run_at = RecurrenceEngine.calculate_next_run(
            trigger_type=schedule.trigger_type,
            trigger_expression=schedule.trigger_expression,
            timezone_str=schedule.timezone,
            reference_utc=now,
        )
        schedule.updated_at = now
        return self.store.update_schedule(schedule)

    def delete_schedule(self, schedule_id: str) -> bool:
        """Delete a schedule and all associated runs."""
        return self.store.delete_schedule(schedule_id)

    async def trigger_manual_run(self, schedule_id: str) -> ScheduleRun:
        """Dispatch manual out-of-band execution of an existing schedule."""
        return await self.dispatcher.trigger_manual_run(schedule_id)

    def list_runs(
        self,
        schedule_id: Optional[str] = None,
        status: Optional[RunStatus] = None,
        limit: int = 50,
    ) -> List[ScheduleRun]:
        """List execution history records."""
        return self.store.list_runs(schedule_id=schedule_id, status=status, limit=limit)
