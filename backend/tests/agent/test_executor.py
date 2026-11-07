import asyncio
import pytest
from backend.app.agent.executor import Executor
from backend.app.agent.state_manager import StateManager
from backend.app.core.config import Settings
from backend.app.models.agent import (
    PlanStep,
    RetryClassification,
    RiskLevel,
    StepStatus,
    TaskStatus,
    ToolCall,
)
from backend.app.permissions.manager import PermissionManager
from backend.app.tools.base import BaseTool
from backend.tests.fixtures.mock_tools import register_mock_tools
from backend.app.tools.registry import ToolRegistry
from pydantic import BaseModel


class FlakyTool(BaseTool):
    name = "flaky_tool"
    description = "Fails once with TimeoutError then succeeds"
    risk_level = RiskLevel.SAFE
    args_schema = BaseModel

    def __init__(self):
        self.calls = 0

    async def execute(self, **kwargs):
        self.calls += 1
        if self.calls == 1:
            raise TimeoutError("Temporary simulated network timeout")
        return {"status": "recovered"}


class BrokenTool(BaseTool):
    name = "broken_tool"
    description = "Fails with permanent ValueError"
    risk_level = RiskLevel.SAFE
    args_schema = BaseModel

    async def execute(self, **kwargs):
        raise ValueError("Invalid mathematical state")


class UncertainTool(BaseTool):
    name = "uncertain_tool"
    description = "Fails with ambiguous RuntimeError"
    risk_level = RiskLevel.SAFE
    args_schema = BaseModel

    async def execute(self, **kwargs):
        raise RuntimeError("I/O pipe abruptly severed mid-write")


@pytest.fixture
def executor_setup(tmp_path):
    settings = Settings(TASK_DATA_DIR=str(tmp_path / "tasks"), MAX_RETRIES_PER_STEP=2)
    registry = ToolRegistry()
    register_mock_tools(registry)
    permissions = PermissionManager(settings)
    state_manager = StateManager(settings)
    executor = Executor(registry, permissions, state_manager, settings)
    return executor, registry, state_manager


@pytest.mark.asyncio
async def test_execute_step_success(executor_setup):
    executor, registry, state_manager = executor_setup
    task = await state_manager.create_task("Run calc")
    step = PlanStep(
        step_id=1,
        description="Calc 5+5",
        tool_call=ToolCall(tool_name="mock_calculate", arguments={"expression": "5 + 5"}),
        risk_level=RiskLevel.SAFE,
    )
    res, is_paused = await executor.execute_step(task, step)
    assert not is_paused
    assert res.status == StepStatus.SUCCEEDED
    assert res.output["result"] == 10


@pytest.mark.asyncio
async def test_execute_step_transient_retry_recovers(executor_setup):
    executor, registry, state_manager = executor_setup
    flaky = FlakyTool()
    registry.register(flaky)

    task = await state_manager.create_task("Run flaky")
    step = PlanStep(
        step_id=1,
        description="Flaky call",
        tool_call=ToolCall(tool_name="flaky_tool", arguments={}),
        risk_level=RiskLevel.SAFE,
    )
    res, is_paused = await executor.execute_step(task, step)
    assert not is_paused
    assert res.status == StepStatus.SUCCEEDED
    assert res.output["status"] == "recovered"
    assert flaky.calls == 2
    assert step.retries_attempted == 1


@pytest.mark.asyncio
async def test_execute_step_permanent_error_no_retry(executor_setup):
    executor, registry, state_manager = executor_setup
    broken = BrokenTool()
    registry.register(broken)

    task = await state_manager.create_task("Run broken")
    step = PlanStep(
        step_id=1,
        description="Broken call",
        tool_call=ToolCall(tool_name="broken_tool", arguments={}),
        risk_level=RiskLevel.SAFE,
    )
    res, is_paused = await executor.execute_step(task, step)
    assert not is_paused
    assert res.status == StepStatus.FAILED
    assert res.retry_classification == RetryClassification.PERMANENT
    assert step.retries_attempted == 0


@pytest.mark.asyncio
async def test_execute_step_uncertain_error_never_retries(executor_setup):
    executor, registry, state_manager = executor_setup
    uncertain = UncertainTool()
    registry.register(uncertain)

    task = await state_manager.create_task("Run uncertain")
    step = PlanStep(
        step_id=1,
        description="Uncertain call",
        tool_call=ToolCall(tool_name="uncertain_tool", arguments={}),
        risk_level=RiskLevel.SAFE,
    )
    res, is_paused = await executor.execute_step(task, step)
    assert not is_paused
    assert res.status == StepStatus.FAILED
    assert res.retry_classification == RetryClassification.UNCERTAIN


@pytest.mark.asyncio
async def test_execute_step_pauses_for_sensitive_approval(executor_setup):
    executor, registry, state_manager = executor_setup
    task = await state_manager.create_task("Read file")
    task = await state_manager.transition_state(task.task_id, TaskStatus.PARSING)
    task = await state_manager.transition_state(task.task_id, TaskStatus.PLANNING)
    task = await state_manager.transition_state(task.task_id, TaskStatus.EXECUTING)

    step = PlanStep(
        step_id=1,
        description="Read file",
        tool_call=ToolCall(tool_name="mock_file_read", arguments={"filepath": "config.json"}),
        risk_level=RiskLevel.SENSITIVE,
    )
    res, is_paused = await executor.execute_step(task, step)
    assert is_paused is True
    assert res is None

    updated_task = await state_manager.get_task(task.task_id)
    assert updated_task.status == TaskStatus.WAITING_APPROVAL
    assert updated_task.pending_approval is not None
    assert updated_task.pending_approval.tool_name == "mock_file_read"
