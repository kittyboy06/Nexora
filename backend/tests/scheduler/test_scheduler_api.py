"""Integration tests for Scheduler REST API endpoints (/api/scheduler/*)."""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
import httpx
import pytest
import pytest_asyncio

from backend.app.main import create_app
from backend.app.models.agent import AgentTask, TaskStatus
from backend.app.scheduler.clock import SimulatedClock
from backend.app.scheduler.database import SchedulerDatabase
from backend.app.scheduler.models import (
    ConcurrencyPolicy,
    MissedRunPolicy,
    TriggerType,
)
from backend.app.scheduler.service import SchedulerService
from backend.app.scheduler.store import ScheduleStore


class MockTaskManager:
    def __init__(self):
        self.is_busy = False
        self.state_manager = MagicMock()
        self._execute_with_lock = AsyncMock()


@pytest_asyncio.fixture
async def scheduler_client(tmp_path: Path):
    """Create test client with isolated SQLite database and mock task manager."""
    db_path = tmp_path / "api_test_scheduler.db"
    db = SchedulerDatabase(db_path)
    store = ScheduleStore(db)
    task_manager = MockTaskManager()

    mock_task = AgentTask(
        task_id="task-api-test-1",
        prompt="Execute API scheduled task",
        status=TaskStatus.COMPLETED,
    )
    task_manager.state_manager.create_task = AsyncMock(return_value=mock_task)
    task_manager.state_manager.get_task = AsyncMock(return_value=mock_task)

    clock = SimulatedClock(datetime(2026, 11, 7, 10, 0, 0, tzinfo=timezone.utc))

    service = SchedulerService(
        store=store,
        task_manager=task_manager,
        clock=clock,
        tick_interval_seconds=0.01,
    )

    app = create_app()
    app.state.scheduler_service = service

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        yield client, service, clock


@pytest.mark.asyncio
async def test_schedule_crud_and_endpoints(scheduler_client):
    client, service, clock = scheduler_client

    # 1. List initially empty
    resp = await client.get("/api/scheduler/schedules")
    assert resp.status_code == 200
    assert resp.json() == []

    # 2. Create invalid schedule -> 400
    bad_payload = {
        "name": "Invalid Schedule",
        "prompt_template": "Run bad",
        "trigger_type": "CRON",
        "trigger_expression": "invalid-cron",
        "timezone": "UTC",
    }
    bad_resp = await client.post("/api/scheduler/schedules", json=bad_payload)
    assert bad_resp.status_code == 400

    # 3. Create valid schedule -> 201
    good_payload = {
        "name": "Daily Report",
        "prompt_template": "Generate daily report",
        "model_profile_id": "fast",
        "trigger_type": "CRON",
        "trigger_expression": "0 9 * * 1-5",
        "timezone": "America/New_York",
        "missed_run_policy": "RUN_ONCE_CATCHUP",
        "concurrency_policy": "SKIP_BUSY",
        "max_instances": 1,
        "retry_grace_seconds": 300,
    }
    create_resp = await client.post("/api/scheduler/schedules", json=good_payload)
    assert create_resp.status_code == 201
    sched = create_resp.json()
    sched_id = sched["id"]
    assert sched["name"] == "Daily Report"
    assert sched["status"] == "ACTIVE"
    assert sched["template_hash"] is not None

    # 4. Get schedule details -> 200
    get_resp = await client.get(f"/api/scheduler/schedules/{sched_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == sched_id

    # Get non-existent -> 404
    non_existent = await client.get("/api/scheduler/schedules/fake-id-123")
    assert non_existent.status_code == 404

    # 5. Patch schedule -> 200
    patch_payload = {
        "name": "Daily Business Report",
        "trigger_expression": "0 10 * * 1-5",
    }
    patch_resp = await client.patch(f"/api/scheduler/schedules/{sched_id}", json=patch_payload)
    assert patch_resp.status_code == 200
    assert patch_resp.json()["name"] == "Daily Business Report"
    assert patch_resp.json()["trigger_expression"] == "0 10 * * 1-5"

    # 6. Pause schedule -> 200
    pause_resp = await client.post(f"/api/scheduler/schedules/{sched_id}/pause")
    assert pause_resp.status_code == 200
    assert pause_resp.json()["status"] == "PAUSED"

    # 7. Resume schedule -> 200
    resume_resp = await client.post(f"/api/scheduler/schedules/{sched_id}/resume")
    assert resume_resp.status_code == 200
    assert resume_resp.json()["status"] == "ACTIVE"

    # 8. Trigger manual run -> 200
    trigger_resp = await client.post(f"/api/scheduler/schedules/{sched_id}/trigger")
    assert trigger_resp.status_code == 200
    run_data = trigger_resp.json()
    assert run_data["schedule_id"] == sched_id
    assert run_data["task_id"] == "task-api-test-1"

    # 9. List runs -> 200
    runs_resp = await client.get(f"/api/scheduler/runs?schedule_id={sched_id}")
    assert runs_resp.status_code == 200
    runs = runs_resp.json()
    assert len(runs) >= 1

    # 10. Delete schedule -> 200
    del_resp = await client.delete(f"/api/scheduler/schedules/{sched_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["deleted"] is True

    # Confirm deleted
    get_after_del = await client.get(f"/api/scheduler/schedules/{sched_id}")
    assert get_after_del.status_code == 404
