"""Tests for StartupReconciler: recovery of crashed in-flight runs and downtime catchup/skip policies."""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
import pytest

from backend.app.models.agent import AgentTask, TaskStatus
from backend.app.scheduler.clock import SimulatedClock
from backend.app.scheduler.database import SchedulerDatabase
from backend.app.scheduler.dispatcher import TaskDispatcher
from backend.app.scheduler.models import (
    ConcurrencyPolicy,
    MissedRunPolicy,
    RunStatus,
    Schedule,
    ScheduleStatus,
    TriggerType,
    compute_template_hash,
)
from backend.app.scheduler.reconciler import StartupReconciler
from backend.app.scheduler.store import ScheduleStore


class MockTaskManager:
    def __init__(self):
        self.is_busy = False
        self.state_manager = MagicMock()
        self._execute_with_lock = AsyncMock()


@pytest.fixture
def scheduler_store(tmp_path: Path) -> ScheduleStore:
    db = SchedulerDatabase(tmp_path / "reconciler_test.db")
    return ScheduleStore(db)


@pytest.fixture
def test_clock() -> SimulatedClock:
    return SimulatedClock(datetime(2026, 11, 7, 12, 0, 0, tzinfo=timezone.utc))


@pytest.mark.asyncio
async def test_reconcile_recovers_interrupted_runs(
    scheduler_store: ScheduleStore, test_clock: SimulatedClock
):
    task_manager = MockTaskManager()
    dispatcher = TaskDispatcher(scheduler_store, task_manager, test_clock)
    reconciler = StartupReconciler(scheduler_store, dispatcher, test_clock)

    now = test_clock.now_utc()
    sched_id = str(uuid.uuid4())
    schedule = Schedule(
        id=sched_id,
        name="Crashed Task Test",
        prompt_template="Some prompt",
        model_profile_id=None,
        trigger_type=TriggerType.INTERVAL,
        trigger_expression="1h",
        timezone="UTC",
        status=ScheduleStatus.ACTIVE,
        missed_run_policy=MissedRunPolicy.SKIP_NOTIFY,
        concurrency_policy=ConcurrencyPolicy.SKIP_BUSY,
        max_instances=1,
        retry_grace_seconds=300,
        next_run_at=now + timedelta(hours=1),
        last_run_at=None,
        template_hash=compute_template_hash("Some prompt", None),
        created_at=now,
        updated_at=now,
    )
    scheduler_store.create_schedule(schedule)

    # Insert an orphaned run that was DISPATCHED before the crash
    crashed_scheduled = now - timedelta(hours=2)
    orphaned_run = scheduler_store.acquire_run_lease(
        schedule_id=sched_id,
        scheduled_for=crashed_scheduled,
        clock_now=crashed_scheduled,
        initial_status=RunStatus.DISPATCHED,
    )
    assert orphaned_run.status == RunStatus.DISPATCHED

    # Run startup reconciliation
    stats = await reconciler.reconcile_startup()
    assert stats["interrupted_runs_recovered"] == 1

    # Verify run is now INTERRUPTED and not re-executed
    recovered = scheduler_store.get_run(orphaned_run.run_id)
    assert recovered.status == RunStatus.INTERRUPTED
    assert "Server restarted" in recovered.error_message
    task_manager._execute_with_lock.assert_not_called()


@pytest.mark.asyncio
async def test_reconcile_missed_run_catchup(
    scheduler_store: ScheduleStore, test_clock: SimulatedClock
):
    task_manager = MockTaskManager()
    dispatcher = TaskDispatcher(scheduler_store, task_manager, test_clock)
    reconciler = StartupReconciler(scheduler_store, dispatcher, test_clock)

    now = test_clock.now_utc()
    template = "Generate Daily Digest"
    thash = compute_template_hash(template, None)

    # Schedule was due 2 hours ago during downtime
    missed_due = now - timedelta(hours=2)
    schedule = Schedule(
        id=str(uuid.uuid4()),
        name="Daily Digest",
        prompt_template=template,
        model_profile_id=None,
        trigger_type=TriggerType.INTERVAL,
        trigger_expression="1h",
        timezone="UTC",
        status=ScheduleStatus.ACTIVE,
        missed_run_policy=MissedRunPolicy.RUN_ONCE_CATCHUP,  # Catch up once!
        concurrency_policy=ConcurrencyPolicy.SKIP_BUSY,
        max_instances=1,
        retry_grace_seconds=300,
        next_run_at=missed_due,
        last_run_at=None,
        template_hash=thash,
        created_at=missed_due,
        updated_at=missed_due,
    )
    scheduler_store.create_schedule(schedule)

    mock_task = AgentTask(
        task_id="task-catchup-1",
        prompt=template,
        status=TaskStatus.COMPLETED,
    )
    task_manager.state_manager.create_task = AsyncMock(return_value=mock_task)
    task_manager.state_manager.get_task = AsyncMock(return_value=mock_task)

    stats = await reconciler.reconcile_startup()
    assert stats["catchup_runs_dispatched"] == 1

    # Check task execution was dispatched
    task_manager.state_manager.create_task.assert_called_once()

    # Recurrence should be advanced into the future relative to now
    updated_sched = scheduler_store.get_schedule(schedule.id)
    assert updated_sched.next_run_at > now


@pytest.mark.asyncio
async def test_reconcile_missed_run_skip_notify(
    scheduler_store: ScheduleStore, test_clock: SimulatedClock
):
    task_manager = MockTaskManager()
    dispatcher = TaskDispatcher(scheduler_store, task_manager, test_clock)
    reconciler = StartupReconciler(scheduler_store, dispatcher, test_clock)

    now = test_clock.now_utc()
    template = "Mutating Backup Routine"
    thash = compute_template_hash(template, None)

    missed_due = now - timedelta(hours=3)
    schedule = Schedule(
        id=str(uuid.uuid4()),
        name="Mutating Backup",
        prompt_template=template,
        model_profile_id=None,
        trigger_type=TriggerType.INTERVAL,
        trigger_expression="2h",
        timezone="UTC",
        status=ScheduleStatus.ACTIVE,
        missed_run_policy=MissedRunPolicy.SKIP_NOTIFY,  # Skip mutating runs
        concurrency_policy=ConcurrencyPolicy.SKIP_BUSY,
        max_instances=1,
        retry_grace_seconds=300,
        next_run_at=missed_due,
        last_run_at=None,
        template_hash=thash,
        created_at=missed_due,
        updated_at=missed_due,
    )
    scheduler_store.create_schedule(schedule)

    stats = await reconciler.reconcile_startup()
    assert stats["missed_runs_skipped"] == 1

    # TaskManager should NOT have been called
    task_manager.state_manager.create_task.assert_not_called()

    # Check that a SKIPPED run was recorded in store
    runs = scheduler_store.list_runs(schedule_id=schedule.id)
    assert len(runs) == 1
    assert runs[0].status == RunStatus.SKIPPED
    assert "skipped per safety policy" in runs[0].error_message

    # Recurrence advanced into future
    updated_sched = scheduler_store.get_schedule(schedule.id)
    assert updated_sched.next_run_at > now
