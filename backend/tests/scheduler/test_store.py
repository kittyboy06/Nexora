"""Tests for SQLite WAL persistence, ScheduleStore, and atomic run leases."""

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest

from backend.app.scheduler.database import SchedulerDatabase
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


@pytest.fixture
def scheduler_store(tmp_path: Path) -> ScheduleStore:
    db_file = tmp_path / "test_scheduler.db"
    db = SchedulerDatabase(db_file)
    return ScheduleStore(db)


def test_schedule_crud(scheduler_store: ScheduleStore):
    now = datetime(2026, 11, 7, 10, 0, 0, tzinfo=timezone.utc)
    sched_id = str(uuid.uuid4())
    template = "Generate morning system digest"
    thash = compute_template_hash(template, None)

    schedule = Schedule(
        id=sched_id,
        name="Morning Digest",
        prompt_template=template,
        model_profile_id=None,
        trigger_type=TriggerType.CRON,
        trigger_expression="0 9 * * *",
        timezone="America/New_York",
        status=ScheduleStatus.ACTIVE,
        missed_run_policy=MissedRunPolicy.RUN_ONCE_CATCHUP,
        concurrency_policy=ConcurrencyPolicy.SKIP_BUSY,
        max_instances=1,
        retry_grace_seconds=300,
        next_run_at=now + timedelta(hours=1),
        last_run_at=None,
        template_hash=thash,
        created_at=now,
        updated_at=now,
    )

    # 1. Create
    created = scheduler_store.create_schedule(schedule)
    assert created.id == sched_id

    # 2. Read
    fetched = scheduler_store.get_schedule(sched_id)
    assert fetched is not None
    assert fetched.name == "Morning Digest"
    assert fetched.status == ScheduleStatus.ACTIVE
    assert fetched.trigger_type == TriggerType.CRON
    assert fetched.next_run_at == now + timedelta(hours=1)

    # 3. List
    schedules = scheduler_store.list_schedules()
    assert len(schedules) == 1
    assert schedules[0].id == sched_id

    # List with filter
    active_scheds = scheduler_store.list_schedules(status=ScheduleStatus.ACTIVE)
    assert len(active_scheds) == 1
    paused_scheds = scheduler_store.list_schedules(status=ScheduleStatus.PAUSED)
    assert len(paused_scheds) == 0

    # 4. Update
    fetched.name = "Morning Digest Renamed"
    fetched.status = ScheduleStatus.PAUSED
    updated = scheduler_store.update_schedule(fetched)
    assert updated.name == "Morning Digest Renamed"
    assert updated.status == ScheduleStatus.PAUSED

    refetched = scheduler_store.get_schedule(sched_id)
    assert refetched.name == "Morning Digest Renamed"
    assert refetched.status == ScheduleStatus.PAUSED

    # 5. Delete
    deleted = scheduler_store.delete_schedule(sched_id)
    assert deleted is True
    assert scheduler_store.get_schedule(sched_id) is None


def test_get_due_schedules(scheduler_store: ScheduleStore):
    now = datetime(2026, 11, 7, 12, 0, 0, tzinfo=timezone.utc)

    # Due schedule
    due_sched = Schedule(
        id=str(uuid.uuid4()),
        name="Due Task",
        prompt_template="Run due",
        model_profile_id=None,
        trigger_type=TriggerType.INTERVAL,
        trigger_expression="15m",
        timezone="UTC",
        status=ScheduleStatus.ACTIVE,
        missed_run_policy=MissedRunPolicy.SKIP_NOTIFY,
        concurrency_policy=ConcurrencyPolicy.SKIP_BUSY,
        max_instances=1,
        retry_grace_seconds=300,
        next_run_at=now - timedelta(minutes=5),  # Due 5 minutes ago
        last_run_at=None,
        template_hash="hash1",
        created_at=now,
        updated_at=now,
    )
    scheduler_store.create_schedule(due_sched)

    # Future schedule
    future_sched = Schedule(
        id=str(uuid.uuid4()),
        name="Future Task",
        prompt_template="Run future",
        model_profile_id=None,
        trigger_type=TriggerType.INTERVAL,
        trigger_expression="15m",
        timezone="UTC",
        status=ScheduleStatus.ACTIVE,
        missed_run_policy=MissedRunPolicy.SKIP_NOTIFY,
        concurrency_policy=ConcurrencyPolicy.SKIP_BUSY,
        max_instances=1,
        retry_grace_seconds=300,
        next_run_at=now + timedelta(minutes=10),  # In future
        last_run_at=None,
        template_hash="hash2",
        created_at=now,
        updated_at=now,
    )
    scheduler_store.create_schedule(future_sched)

    # Paused overdue schedule (should be excluded)
    paused_sched = Schedule(
        id=str(uuid.uuid4()),
        name="Paused Task",
        prompt_template="Run paused",
        model_profile_id=None,
        trigger_type=TriggerType.INTERVAL,
        trigger_expression="15m",
        timezone="UTC",
        status=ScheduleStatus.PAUSED,
        missed_run_policy=MissedRunPolicy.SKIP_NOTIFY,
        concurrency_policy=ConcurrencyPolicy.SKIP_BUSY,
        max_instances=1,
        retry_grace_seconds=300,
        next_run_at=now - timedelta(minutes=10),
        last_run_at=None,
        template_hash="hash3",
        created_at=now,
        updated_at=now,
    )
    scheduler_store.create_schedule(paused_sched)

    due_list = scheduler_store.get_due_schedules(now)
    assert len(due_list) == 1
    assert due_list[0].id == due_sched.id


def test_atomic_run_lease_and_idempotency(scheduler_store: ScheduleStore):
    sched_id = str(uuid.uuid4())
    schedule = Schedule(
        id=sched_id,
        name="Atomic Test",
        prompt_template="Test prompt",
        model_profile_id=None,
        trigger_type=TriggerType.CRON,
        trigger_expression="0 9 * * *",
        timezone="UTC",
        status=ScheduleStatus.ACTIVE,
        missed_run_policy=MissedRunPolicy.SKIP_NOTIFY,
        concurrency_policy=ConcurrencyPolicy.SKIP_BUSY,
        max_instances=1,
        retry_grace_seconds=300,
        next_run_at=None,
        last_run_at=None,
        template_hash="hash_atomic",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    scheduler_store.create_schedule(schedule)

    scheduled_for = datetime(2026, 11, 7, 9, 0, 0, tzinfo=timezone.utc)
    clock_now = datetime(2026, 11, 7, 9, 0, 1, tzinfo=timezone.utc)

    # 1. First lease acquisition succeeds
    lease1 = scheduler_store.acquire_run_lease(sched_id, scheduled_for, clock_now)
    assert lease1 is not None
    assert lease1.schedule_id == sched_id
    assert lease1.status == RunStatus.DISPATCHED
    assert lease1.run_key == f"{sched_id}:{scheduled_for.isoformat()}"

    # 2. Second lease acquisition for identical scheduled_for fails (idempotent guard)
    lease2 = scheduler_store.acquire_run_lease(sched_id, scheduled_for, clock_now)
    assert lease2 is None

    # 3. Different scheduled timestamp succeeds
    next_scheduled = scheduled_for + timedelta(days=1)
    lease3 = scheduler_store.acquire_run_lease(sched_id, next_scheduled, clock_now)
    assert lease3 is not None
    assert lease3.run_key == f"{sched_id}:{next_scheduled.isoformat()}"

    # 4. Update run status and task metadata
    task_uuid = "task-xyz-123"
    finished_time = clock_now + timedelta(seconds=45)
    updated_run = scheduler_store.update_run(
        run_id=lease1.run_id,
        status=RunStatus.COMPLETED,
        task_id=task_uuid,
        finished_at=finished_time,
    )
    assert updated_run is not None
    assert updated_run.status == RunStatus.COMPLETED
    assert updated_run.task_id == task_uuid
    assert updated_run.finished_at == finished_time

    # 5. In-flight runs (lease3 is still DISPATCHED, lease1 is COMPLETED)
    in_flight = scheduler_store.get_in_flight_runs()
    assert len(in_flight) == 1
    assert in_flight[0].run_id == lease3.run_id

    # 6. Cascade delete
    scheduler_store.delete_schedule(sched_id)
    assert len(scheduler_store.list_runs(schedule_id=sched_id)) == 0
