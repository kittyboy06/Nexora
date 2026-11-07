"""Tests for SchedulerService: lifecycle management, async ticker loop, and CRUD facade."""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
import pytest

from backend.app.models.agent import AgentTask, TaskStatus
from backend.app.scheduler.clock import SimulatedClock
from backend.app.scheduler.database import SchedulerDatabase
from backend.app.scheduler.models import (
    ConcurrencyPolicy,
    MissedRunPolicy,
    RunStatus,
    ScheduleCreate,
    ScheduleStatus,
    ScheduleUpdate,
    TriggerType,
)
from backend.app.scheduler.service import SchedulerService
from backend.app.scheduler.store import ScheduleStore


class MockTaskManager:
    def __init__(self):
        self.is_busy = False
        self.state_manager = MagicMock()
        self._execute_with_lock = AsyncMock()


@pytest.fixture
def test_clock() -> SimulatedClock:
    return SimulatedClock(datetime(2026, 11, 7, 8, 0, 0, tzinfo=timezone.utc))


@pytest.fixture
def scheduler_service(tmp_path: Path, test_clock: SimulatedClock) -> SchedulerService:
    db = SchedulerDatabase(tmp_path / "service_test.db")
    store = ScheduleStore(db)
    task_manager = MockTaskManager()

    mock_task = AgentTask(
        task_id="task-srv-1",
        prompt="Test prompt",
        status=TaskStatus.COMPLETED,
    )
    task_manager.state_manager.create_task = AsyncMock(return_value=mock_task)
    task_manager.state_manager.get_task = AsyncMock(return_value=mock_task)

    return SchedulerService(
        store=store,
        task_manager=task_manager,
        clock=test_clock,
        tick_interval_seconds=0.02,
    )


def test_crud_facade(scheduler_service: SchedulerService, test_clock: SimulatedClock):
    # 1. Create
    payload = ScheduleCreate(
        name="Morning Alert",
        prompt_template="Send morning summary",
        trigger_type=TriggerType.CRON,
        trigger_expression="0 9 * * *",
        timezone="America/New_York",
        missed_run_policy=MissedRunPolicy.RUN_ONCE_CATCHUP,
        concurrency_policy=ConcurrencyPolicy.SKIP_BUSY,
    )
    created = scheduler_service.create_schedule(payload)
    assert created.name == "Morning Alert"
    assert created.status == ScheduleStatus.ACTIVE
    assert created.next_run_at is not None

    # 2. Get & List
    fetched = scheduler_service.get_schedule(created.id)
    assert fetched is not None
    assert fetched.id == created.id

    schedules = scheduler_service.list_schedules()
    assert len(schedules) == 1

    # 3. Update
    updated = scheduler_service.update_schedule(
        created.id,
        ScheduleUpdate(name="Renamed Alert", trigger_expression="0 10 * * *"),
    )
    assert updated.name == "Renamed Alert"
    assert updated.trigger_expression == "0 10 * * *"

    # 4. Pause & Resume
    paused = scheduler_service.pause_schedule(created.id)
    assert paused.status == ScheduleStatus.PAUSED

    resumed = scheduler_service.resume_schedule(created.id)
    assert resumed.status == ScheduleStatus.ACTIVE

    # 5. Delete
    deleted = scheduler_service.delete_schedule(created.id)
    assert deleted is True
    assert scheduler_service.get_schedule(created.id) is None


@pytest.mark.asyncio
async def test_tick_once_dispatches_due(
    scheduler_service: SchedulerService, test_clock: SimulatedClock
):
    now = test_clock.now_utc()
    payload = ScheduleCreate(
        name="Interval Tick Test",
        prompt_template="Check heartbeats",
        trigger_type=TriggerType.INTERVAL,
        trigger_expression="30m",
        timezone="UTC",
    )
    sched = scheduler_service.create_schedule(payload)
    assert sched.next_run_at == now + timedelta(minutes=30)

    # 1. When not due, tick_once does nothing
    dispatched = await scheduler_service.tick_once()
    assert dispatched == 0

    # 2. Advance time past due
    test_clock.advance(timedelta(minutes=31))
    dispatched = await scheduler_service.tick_once()
    assert dispatched == 1

    # Check run was recorded
    runs = scheduler_service.list_runs(schedule_id=sched.id)
    assert len(runs) == 1


@pytest.mark.asyncio
async def test_service_start_stop_lifecycle(
    scheduler_service: SchedulerService, test_clock: SimulatedClock
):
    # Create due schedule
    payload = ScheduleCreate(
        name="Auto Ticker Test",
        prompt_template="Run auto tick",
        trigger_type=TriggerType.INTERVAL,
        trigger_expression="10s",
        timezone="UTC",
    )
    sched = scheduler_service.create_schedule(payload)

    # Start service
    await scheduler_service.start()
    assert scheduler_service._running is True
    assert scheduler_service._ticker_task is not None

    # Advance clock and wait for loop
    test_clock.advance(timedelta(seconds=15))
    await asyncio.sleep(0.06)

    # Stop service
    await scheduler_service.stop()
    assert scheduler_service._running is False
    assert scheduler_service._ticker_task is None

    # Verify run was executed
    runs = scheduler_service.list_runs(schedule_id=sched.id)
    assert len(runs) >= 1
