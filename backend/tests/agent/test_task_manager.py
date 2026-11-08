import asyncio
import pytest
from fastapi import BackgroundTasks
from backend.app.agent.orchestrator import AgentOrchestrator
from backend.app.agent.state_manager import StateManager
from backend.app.agent.task_manager import TaskManager
from backend.app.core.config import Settings
from backend.app.core.exceptions import TaskRunnerBusyException
from backend.app.models.agent import TaskStatus
from backend.app.permissions.manager import PermissionManager
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def manager_setup(tmp_path):
    settings = Settings(TASK_DATA_DIR=str(tmp_path / "tasks"))
    state_manager = StateManager(settings)
    permissions = PermissionManager(settings)
    orchestrator = MagicMock(spec=AgentOrchestrator)
    # Simulate slow task execution
    async def slow_run(task_id, **kwargs):
        await asyncio.sleep(0.5)
    orchestrator.run_task = AsyncMock(side_effect=slow_run)

    task_manager = TaskManager(state_manager, orchestrator, permissions)
    return task_manager, state_manager


@pytest.mark.asyncio
async def test_task_manager_concurrency_busy_exception(manager_setup):
    task_manager, state_manager = manager_setup
    bg = BackgroundTasks()

    # Start first task
    task1 = await task_manager.create_and_start_task("Goal 1", bg)
    assert task1.task_id is not None

    # Manually execute background task to simulate running worker
    runner_task = asyncio.create_task(bg())
    await asyncio.sleep(0.05)  # Let lock acquire

    # Second task submission must fail with TaskRunnerBusyException
    with pytest.raises(TaskRunnerBusyException) as exc:
        await task_manager.create_and_start_task("Goal 2", BackgroundTasks())
    assert "Agent capacity busy" in str(exc.value)

    await runner_task


@pytest.mark.asyncio
async def test_task_manager_cancellation_releases_lock(manager_setup):
    task_manager, state_manager = manager_setup
    bg = BackgroundTasks()

    # Start first task
    task1 = await task_manager.create_and_start_task("Goal 1", bg)
    runner_task = asyncio.create_task(bg())
    await asyncio.sleep(0.05)  # Let lock acquire
    assert task_manager.is_busy

    # Cancel task
    cancelled = await task_manager.cancel_task(task1.task_id)
    assert cancelled.status == TaskStatus.CANCELLED

    # Wait for cancellation to settle
    try:
        await asyncio.wait_for(runner_task, timeout=0.5)
    except (asyncio.CancelledError, Exception):
        pass

    assert not task_manager.is_busy

    # Subsequent task creation must succeed immediately
    bg2 = BackgroundTasks()
    task2 = await task_manager.create_and_start_task("Goal 2", bg2)
    assert task2.task_id is not None
    runner2 = asyncio.create_task(bg2())
    await runner2


@pytest.mark.asyncio
async def test_task_manager_recovers_if_lock_held_for_terminal_task(manager_setup):
    task_manager, state_manager = manager_setup
    bg = BackgroundTasks()

    task1 = await task_manager.create_and_start_task("Goal 1", bg)
    runner_task = asyncio.create_task(bg())
    await asyncio.sleep(0.05)
    assert task_manager.is_busy

    # Force task to CANCELLED in state manager while lock is still held
    await state_manager.transition_state(task1.task_id, TaskStatus.CANCELLED)

    # Next task creation should detect terminal state, clean up and succeed
    bg2 = BackgroundTasks()
    task2 = await task_manager.create_and_start_task("Goal 2", bg2)
    assert task2.task_id is not None
    assert task2.task_id != task1.task_id

    # Clean up runner_task
    try:
        await asyncio.wait_for(runner_task, timeout=0.6)
    except (asyncio.CancelledError, Exception):
        pass
