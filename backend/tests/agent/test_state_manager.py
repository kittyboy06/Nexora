import json
import pytest
from backend.app.agent.state_manager import StateManager
from backend.app.core.config import Settings
from backend.app.core.exceptions import InvalidStateTransitionException
from backend.app.models.agent import TaskStatus


@pytest.fixture
def temp_state_manager(tmp_path):
    settings = Settings(TASK_DATA_DIR=str(tmp_path / "tasks"))
    return StateManager(settings)


@pytest.mark.asyncio
async def test_valid_state_transitions(temp_state_manager: StateManager):
    task = await temp_state_manager.create_task("Test goal")
    assert task.status == TaskStatus.SUBMITTED

    task = await temp_state_manager.transition_state(task.task_id, TaskStatus.PARSING)
    assert task.status == TaskStatus.PARSING

    task = await temp_state_manager.transition_state(task.task_id, TaskStatus.PLANNING)
    assert task.status == TaskStatus.PLANNING

    task = await temp_state_manager.transition_state(task.task_id, TaskStatus.EXECUTING)
    assert task.status == TaskStatus.EXECUTING

    task = await temp_state_manager.transition_state(task.task_id, TaskStatus.COMPLETED)
    assert task.status == TaskStatus.COMPLETED


@pytest.mark.asyncio
async def test_invalid_state_transition(temp_state_manager: StateManager):
    task = await temp_state_manager.create_task("Test goal")
    # SUBMITTED cannot transition directly to COMPLETED
    with pytest.raises(InvalidStateTransitionException):
        await temp_state_manager.transition_state(task.task_id, TaskStatus.COMPLETED)


@pytest.mark.asyncio
async def test_atomic_persistence(temp_state_manager: StateManager):
    task = await temp_state_manager.create_task("Persistent goal")
    file_path = temp_state_manager.data_dir / f"{task.task_id}.json"
    assert file_path.exists()

    data = json.loads(file_path.read_text(encoding="utf-8"))
    assert data["task_id"] == task.task_id
    assert data["status"] == "SUBMITTED"


@pytest.mark.asyncio
async def test_startup_recovery_interrupted(temp_state_manager: StateManager):
    # Simulate an active task saved to disk before shutdown
    task = await temp_state_manager.create_task("Interrupted task")
    await temp_state_manager.transition_state(task.task_id, TaskStatus.PARSING)
    await temp_state_manager.transition_state(task.task_id, TaskStatus.PLANNING)
    await temp_state_manager.transition_state(task.task_id, TaskStatus.EXECUTING)

    # New StateManager instance on startup
    fresh_manager = StateManager(temp_state_manager.settings)
    interrupted_count = await fresh_manager.recover_on_startup()
    assert interrupted_count == 1

    recovered_task = await fresh_manager.get_task(task.task_id)
    assert recovered_task.status == TaskStatus.INTERRUPTED
    assert "application restart" in recovered_task.error_message
