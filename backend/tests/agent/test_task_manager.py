import asyncio
import pytest
from fastapi import BackgroundTasks
from backend.app.agent.orchestrator import AgentOrchestrator
from backend.app.agent.state_manager import StateManager
from backend.app.agent.task_manager import TaskManager
from backend.app.core.config import Settings
from backend.app.core.exceptions import TaskRunnerBusyException
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
        await asyncio.sleep(0.3)
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
