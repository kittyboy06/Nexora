import pytest
from pydantic import ValidationError
from backend.app.models.agent import (
    AgentTask,
    PlanStep,
    RiskLevel,
    StepStatus,
    TaskPlan,
    TaskStatus,
    ToolCall,
)


def test_plan_step_valid():
    step = PlanStep(
        step_id=1,
        description="Search info",
        tool_call=ToolCall(tool_name="mock_search", arguments={"query": "test"}),
    )
    assert step.step_id == 1
    assert step.risk_level == RiskLevel.SAFE
    assert step.status == StepStatus.PENDING
    assert step.retries_attempted == 0


def test_plan_step_invalid_id():
    with pytest.raises(ValidationError):
        PlanStep(
            step_id=11,  # Exceeds max 10
            description="Bad step",
            tool_call=ToolCall(tool_name="mock_search", arguments={}),
        )


def test_task_plan_max_steps():
    steps = [
        PlanStep(
            step_id=1,  # same step_id to bypass PlanStep.step_id <= 10
            description=f"Step {i}",
            tool_call=ToolCall(tool_name="mock_search", arguments={"query": "test"}),
        )
        for i in range(11)  # 11 steps
    ]
    with pytest.raises(ValidationError) as exc:
        TaskPlan(plan_id="plan_1", goal="Too many steps", steps=steps)
    assert "at most 10 items" in str(exc.value) or "too_long" in str(exc.value)


def test_agent_task_defaults():
    task = AgentTask(task_id="task_123", prompt="Calculate 2 + 2")
    assert task.status == TaskStatus.SUBMITTED
    assert task.plan is None
    assert task.iterations_used == 0
    assert task.execution_trace == []
