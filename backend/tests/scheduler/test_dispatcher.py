"""Tests for TaskDispatcher: capacity guards, drift invalidation, approval timeouts, and manual triggers."""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
import pytest

from backend.app.core.exceptions import TaskRunnerBusyException
from backend.app.models.agent import ActionApproval, AgentTask, TaskStatus
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
from backend.app.scheduler.store import ScheduleStore


class MockTaskManager:
    def __init__(self):
        self.is_busy = False
        self.state_manager = MagicMock()
        self._execute_with_lock = AsyncMock()


@pytest.fixture
def scheduler_store(tmp_path: Path) -> ScheduleStore:
    db = SchedulerDatabase(tmp_path / "dispatcher_test.db")
    return ScheduleStore(db)


@pytest.fixture
def test_clock() -> SimulatedClock:
    return SimulatedClock(datetime(2026, 11, 7, 10, 0, 0, tzinfo=timezone.utc))


@pytest.mark.asyncio
async def test_dispatch_due_schedule_success(
    scheduler_store: ScheduleStore, test_clock: SimulatedClock
):
    task_manager = MockTaskManager()
    dispatcher = TaskDispatcher(scheduler_store, task_manager, test_clock)

    now = test_clock.now_utc()
    template = "Daily Summary"
    thash = compute_template_hash(template, None)

    schedule = Schedule(
        id=str(uuid.uuid4()),
        name="Summary Schedule",
        prompt_template=template,
        model_profile_id=None,
        trigger_type=TriggerType.INTERVAL,
        trigger_expression="1h",
        timezone="UTC",
        status=ScheduleStatus.ACTIVE,
        missed_run_policy=MissedRunPolicy.SKIP_NOTIFY,
        concurrency_policy=ConcurrencyPolicy.SKIP_BUSY,
        max_instances=1,
        retry_grace_seconds=300,
        next_run_at=now,
        last_run_at=None,
        template_hash=thash,
        created_at=now,
        updated_at=now,
    )
    scheduler_store.create_schedule(schedule)

    mock_task = AgentTask(
        task_id="task-123",
        prompt=template,
        status=TaskStatus.COMPLETED,
    )
    task_manager.state_manager.create_task = AsyncMock(return_value=mock_task)
    task_manager.state_manager.get_task = AsyncMock(return_value=mock_task)

    # Dispatch
    run = await dispatcher.dispatch_due_schedule(schedule, now)
    assert run is not None
    assert run.status == RunStatus.DISPATCHED
    assert run.task_id == "task-123"

    # Give async monitor task a moment to finish
    await asyncio.sleep(0.05)

    # Verify run updated to COMPLETED
    updated_run = scheduler_store.get_run(run.run_id)
    assert updated_run.status == RunStatus.COMPLETED

    # Verify schedule recurrence advanced by 1h
    updated_sched = scheduler_store.get_schedule(schedule.id)
    assert updated_sched.next_run_at == now + timedelta(hours=1)


@pytest.mark.asyncio
async def test_dispatch_template_drift_invalidation(
    scheduler_store: ScheduleStore, test_clock: SimulatedClock
):
    task_manager = MockTaskManager()
    dispatcher = TaskDispatcher(scheduler_store, task_manager, test_clock)

    now = test_clock.now_utc()
    # Template has been tampered with or modified without recalculating hash
    schedule = Schedule(
        id=str(uuid.uuid4()),
        name="Drifted Schedule",
        prompt_template="Delete all database tables",  # modified
        model_profile_id=None,
        trigger_type=TriggerType.INTERVAL,
        trigger_expression="1h",
        timezone="UTC",
        status=ScheduleStatus.ACTIVE,
        missed_run_policy=MissedRunPolicy.SKIP_NOTIFY,
        concurrency_policy=ConcurrencyPolicy.SKIP_BUSY,
        max_instances=1,
        retry_grace_seconds=300,
        next_run_at=now,
        last_run_at=None,
        template_hash="old_legit_hash_value",  # mismatch!
        created_at=now,
        updated_at=now,
    )
    scheduler_store.create_schedule(schedule)

    run = await dispatcher.dispatch_due_schedule(schedule, now)
    assert run is not None
    assert run.status == RunStatus.SKIPPED
    assert "drift detected" in run.error_message

    # Verify schedule was paused with PAUSED_INVALIDATED
    updated_sched = scheduler_store.get_schedule(schedule.id)
    assert updated_sched.status == ScheduleStatus.PAUSED_INVALIDATED


@pytest.mark.asyncio
async def test_dispatch_concurrency_skip_busy(
    scheduler_store: ScheduleStore, test_clock: SimulatedClock
):
    task_manager = MockTaskManager()
    task_manager.is_busy = True  # Agent capacity is currently busy
    dispatcher = TaskDispatcher(scheduler_store, task_manager, test_clock)

    now = test_clock.now_utc()
    template = "Routine check"
    schedule = Schedule(
        id=str(uuid.uuid4()),
        name="Routine check",
        prompt_template=template,
        model_profile_id=None,
        trigger_type=TriggerType.INTERVAL,
        trigger_expression="30m",
        timezone="UTC",
        status=ScheduleStatus.ACTIVE,
        missed_run_policy=MissedRunPolicy.SKIP_NOTIFY,
        concurrency_policy=ConcurrencyPolicy.SKIP_BUSY,
        max_instances=1,
        retry_grace_seconds=300,
        next_run_at=now,
        last_run_at=None,
        template_hash=compute_template_hash(template, None),
        created_at=now,
        updated_at=now,
    )
    scheduler_store.create_schedule(schedule)

    run = await dispatcher.dispatch_due_schedule(schedule, now)
    assert run is not None
    assert run.status == RunStatus.BLOCKED_BUSY

    # Verify schedule next_run_at advanced to next period
    updated_sched = scheduler_store.get_schedule(schedule.id)
    assert updated_sched.next_run_at == now + timedelta(minutes=30)


@pytest.mark.asyncio
async def test_dispatch_concurrency_retry_grace(
    scheduler_store: ScheduleStore, test_clock: SimulatedClock
):
    task_manager = MockTaskManager()
    task_manager.is_busy = True  # Saturated
    dispatcher = TaskDispatcher(scheduler_store, task_manager, test_clock)

    scheduled_for = test_clock.now_utc()
    template = "Important sync"
    schedule = Schedule(
        id=str(uuid.uuid4()),
        name="Important sync",
        prompt_template=template,
        model_profile_id=None,
        trigger_type=TriggerType.INTERVAL,
        trigger_expression="1h",
        timezone="UTC",
        status=ScheduleStatus.ACTIVE,
        missed_run_policy=MissedRunPolicy.SKIP_NOTIFY,
        concurrency_policy=ConcurrencyPolicy.RETRY_GRACE,
        max_instances=1,
        retry_grace_seconds=300,  # 5 min
        next_run_at=scheduled_for,
        last_run_at=None,
        template_hash=compute_template_hash(template, None),
        created_at=scheduled_for,
        updated_at=scheduled_for,
    )
    scheduler_store.create_schedule(schedule)

    # 1. First tick (now == scheduled_for, within 300s grace): returns None (will retry)
    run1 = await dispatcher.dispatch_due_schedule(schedule, scheduled_for)
    assert run1 is None
    # Schedule next_run_at is NOT advanced yet
    assert scheduler_store.get_schedule(schedule.id).next_run_at == scheduled_for

    # 2. Advance time past grace window (6 minutes later)
    test_clock.advance(timedelta(minutes=6))
    run2 = await dispatcher.dispatch_due_schedule(schedule, scheduled_for)
    assert run2 is not None
    assert run2.status == RunStatus.BLOCKED_BUSY
    assert "grace window" in run2.error_message

    # Schedule is now advanced
    assert scheduler_store.get_schedule(schedule.id).next_run_at > scheduled_for


@pytest.mark.asyncio
async def test_manual_trigger(
    scheduler_store: ScheduleStore, test_clock: SimulatedClock
):
    task_manager = MockTaskManager()
    dispatcher = TaskDispatcher(scheduler_store, task_manager, test_clock)

    now = test_clock.now_utc()
    template = "On-demand task"
    schedule = Schedule(
        id=str(uuid.uuid4()),
        name="On-demand",
        prompt_template=template,
        model_profile_id=None,
        trigger_type=TriggerType.INTERVAL,
        trigger_expression="1d",
        timezone="UTC",
        status=ScheduleStatus.ACTIVE,
        missed_run_policy=MissedRunPolicy.SKIP_NOTIFY,
        concurrency_policy=ConcurrencyPolicy.SKIP_BUSY,
        max_instances=1,
        retry_grace_seconds=300,
        next_run_at=now + timedelta(days=1),
        last_run_at=None,
        template_hash=compute_template_hash(template, None),
        created_at=now,
        updated_at=now,
    )
    scheduler_store.create_schedule(schedule)

    mock_task = AgentTask(
        task_id="task-manual-999",
        prompt=template,
        status=TaskStatus.COMPLETED,
    )
    task_manager.state_manager.create_task = AsyncMock(return_value=mock_task)
    task_manager.state_manager.get_task = AsyncMock(return_value=mock_task)

    # 1. Trigger when idle succeeds
    run = await dispatcher.trigger_manual_run(schedule.id)
    assert run.task_id == "task-manual-999"

    # 2. Trigger when busy raises TaskRunnerBusyException
    task_manager.is_busy = True
    with pytest.raises(TaskRunnerBusyException):
        await dispatcher.trigger_manual_run(schedule.id)


@pytest.mark.asyncio
async def test_dispatch_approval_timeout(
    scheduler_store: ScheduleStore, test_clock: SimulatedClock
):
    task_manager = MockTaskManager()
    dispatcher = TaskDispatcher(scheduler_store, task_manager, test_clock)

    now = test_clock.now_utc()
    template = "Sensitive operation requiring operator approval"
    schedule = Schedule(
        id=str(uuid.uuid4()),
        name="Sensitive Scheduled Task",
        prompt_template=template,
        model_profile_id=None,
        trigger_type=TriggerType.INTERVAL,
        trigger_expression="1d",
        timezone="UTC",
        status=ScheduleStatus.ACTIVE,
        missed_run_policy=MissedRunPolicy.SKIP_NOTIFY,
        concurrency_policy=ConcurrencyPolicy.SKIP_BUSY,
        max_instances=1,
        retry_grace_seconds=300,
        next_run_at=now,
        last_run_at=None,
        template_hash=compute_template_hash(template, None),
        created_at=now,
        updated_at=now,
    )
    scheduler_store.create_schedule(schedule)

    approval = ActionApproval(
        approval_id="appr-1",
        task_id="task-appr-test",
        step_id=1,
        tool_name="terminal_execute",
        argument_hash="abc",
        expires_at=now + timedelta(seconds=600),
        created_at=now,
    )
    mock_task = AgentTask(
        task_id="task-appr-test",
        prompt=template,
        status=TaskStatus.WAITING_APPROVAL,
        pending_approval=approval,
    )

    task_manager.state_manager.create_task = AsyncMock(return_value=mock_task)
    task_manager.state_manager.get_task = AsyncMock(return_value=mock_task)
    task_manager.state_manager.transition_state = AsyncMock()
    task_manager._execute_with_lock = AsyncMock()

    # Advance clock past expiration
    test_clock.advance(timedelta(seconds=601))

    run = await dispatcher.dispatch_due_schedule(schedule, now)
    assert run is not None

    # Wait briefly for background monitor loop to detect timeout
    await asyncio.sleep(0.6)

    updated_run = scheduler_store.get_run(run.run_id)
    assert updated_run.status == RunStatus.EXPIRED_APPROVAL
    task_manager.state_manager.transition_state.assert_called_with(
        "task-appr-test",
        TaskStatus.CANCELLED,
        error_message="Operator approval expired after timeout.",
    )

