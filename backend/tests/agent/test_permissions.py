from datetime import datetime, timedelta, timezone
import pytest
from backend.app.core.config import Settings
from backend.app.core.exceptions import ApprovalInvalidatedException
from backend.app.models.agent import (
    ActionApproval,
    AgentTask,
    PlanStep,
    RiskLevel,
    ToolCall,
)
from backend.app.permissions.manager import PermissionManager


@pytest.fixture
def manager():
    return PermissionManager(Settings(APPROVAL_EXPIRATION_SECONDS=600.0))


def test_safe_tool_auto_authorizes(manager: PermissionManager):
    task = AgentTask(task_id="task_1", prompt="Search test")
    step = PlanStep(
        step_id=1,
        description="Search",
        tool_call=ToolCall(tool_name="mock_search", arguments={"query": "test"}),
        risk_level=RiskLevel.SAFE,
    )
    authorized, approval = manager.evaluate_permission(step, task)
    assert authorized is True
    assert approval is None


def test_sensitive_tool_requires_approval(manager: PermissionManager):
    task = AgentTask(task_id="task_1", prompt="Read file")
    step = PlanStep(
        step_id=1,
        description="Read file",
        tool_call=ToolCall(tool_name="mock_file_read", arguments={"filepath": "test.txt"}),
        risk_level=RiskLevel.SENSITIVE,
    )
    authorized, approval = manager.evaluate_permission(step, task)
    assert authorized is False
    assert approval is not None
    assert approval.task_id == "task_1"
    assert approval.step_id == 1
    assert approval.tool_name == "mock_file_read"
    assert approval.argument_hash is not None


def test_verify_decision_valid(manager: PermissionManager):
    task = AgentTask(task_id="task_1", prompt="Read file")
    step = PlanStep(
        step_id=1,
        description="Read file",
        tool_call=ToolCall(tool_name="mock_file_read", arguments={"filepath": "test.txt"}),
        risk_level=RiskLevel.SENSITIVE,
    )
    _, approval = manager.evaluate_permission(step, task)
    task.pending_approval = approval

    # Should not raise
    manager.verify_decision(task, step, approval.approval_id, approved=True)


def test_verify_decision_arguments_modified_invalidates(manager: PermissionManager):
    task = AgentTask(task_id="task_1", prompt="Read file")
    step = PlanStep(
        step_id=1,
        description="Read file",
        tool_call=ToolCall(tool_name="mock_file_read", arguments={"filepath": "test.txt"}),
        risk_level=RiskLevel.SENSITIVE,
    )
    _, approval = manager.evaluate_permission(step, task)
    task.pending_approval = approval

    # Tamper with step arguments
    step.tool_call.arguments["filepath"] = "different_secret.txt"

    with pytest.raises(ApprovalInvalidatedException) as exc:
        manager.verify_decision(task, step, approval.approval_id, approved=True)
    assert "modified after approval" in str(exc.value)


def test_verify_decision_expired(manager: PermissionManager):
    task = AgentTask(task_id="task_1", prompt="Read file")
    step = PlanStep(
        step_id=1,
        description="Read file",
        tool_call=ToolCall(tool_name="mock_file_read", arguments={"filepath": "test.txt"}),
        risk_level=RiskLevel.SENSITIVE,
    )
    _, approval = manager.evaluate_permission(step, task)
    # Force expiration in past
    approval.expires_at = datetime.now(timezone.utc) - timedelta(seconds=10)
    task.pending_approval = approval

    with pytest.raises(ApprovalInvalidatedException) as exc:
        manager.verify_decision(task, step, approval.approval_id, approved=True)
    assert "expired" in str(exc.value)
