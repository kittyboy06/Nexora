import pytest
from backend.app.agent.plan_validator import PlanValidator
from backend.app.core.config import Settings
from backend.app.core.exceptions import PlanValidationException
from backend.app.models.agent import PlanStep, RiskLevel, TaskPlan, ToolCall
from backend.tests.fixtures.mock_tools import register_mock_tools
from backend.app.tools.registry import ToolRegistry


@pytest.fixture
def validator():
    settings = Settings(MAX_PLAN_STEPS=10)
    registry = ToolRegistry()
    register_mock_tools(registry)
    return PlanValidator(registry=registry, settings=settings)


def test_valid_plan(validator: PlanValidator):
    plan = TaskPlan(
        plan_id="plan_1",
        goal="Search and summarize",
        steps=[
            PlanStep(
                step_id=1,
                description="Search info",
                tool_call=ToolCall(tool_name="mock_search", arguments={"query": "python"}),
                dependencies=[],
            ),
            PlanStep(
                step_id=2,
                description="Summarize results",
                tool_call=ToolCall(tool_name="mock_summarize", arguments={"text": "some text"}),
                dependencies=[1],
            ),
        ],
    )
    validated = validator.validate(plan)
    assert len(validated.steps) == 2


def test_unregistered_tool(validator: PlanValidator):
    plan = TaskPlan(
        plan_id="plan_bad",
        goal="Use bad tool",
        steps=[
            PlanStep(
                step_id=1,
                description="Run shell",
                tool_call=ToolCall(tool_name="unregistered_tool", arguments={}),
                dependencies=[],
            )
        ],
    )
    with pytest.raises(PlanValidationException) as exc:
        validator.validate(plan)
    assert "not registered" in str(exc.value)


def test_invalid_tool_arguments(validator: PlanValidator):
    plan = TaskPlan(
        plan_id="plan_bad_args",
        goal="Invalid args",
        steps=[
            PlanStep(
                step_id=1,
                description="Calculate without expression",
                tool_call=ToolCall(tool_name="mock_calculate", arguments={"wrong_key": 123}),
                dependencies=[],
            )
        ],
    )
    with pytest.raises(PlanValidationException) as exc:
        validator.validate(plan)
    assert "Invalid arguments" in str(exc.value)


def test_invalid_dependencies(validator: PlanValidator):
    plan = TaskPlan(
        plan_id="plan_bad_deps",
        goal="Forward dependency",
        steps=[
            PlanStep(
                step_id=1,
                description="Step 1 depends on future Step 2",
                tool_call=ToolCall(tool_name="mock_search", arguments={"query": "test"}),
                dependencies=[2],  # Forward dependency!
            ),
            PlanStep(
                step_id=2,
                description="Step 2",
                tool_call=ToolCall(tool_name="mock_summarize", arguments={"text": "test"}),
                dependencies=[],
            ),
        ],
    )
    with pytest.raises(PlanValidationException) as exc:
        validator.validate(plan)
    assert "must precede" in str(exc.value)


def test_cyclic_dependencies(validator: PlanValidator):
    # Construct steps where dependencies form a cycle
    step1 = PlanStep(
        step_id=1,
        description="Step 1",
        tool_call=ToolCall(tool_name="mock_search", arguments={"query": "test"}),
        dependencies=[1],  # Self loop
    )
    plan = TaskPlan(plan_id="plan_cycle", goal="Cycle", steps=[step1])
    with pytest.raises(PlanValidationException) as exc:
        validator.validate(plan)
    assert "must precede" in str(exc.value) or "Cyclic" in str(exc.value)
