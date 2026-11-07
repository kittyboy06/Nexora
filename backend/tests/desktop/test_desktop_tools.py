"""Unit tests for Desktop Tools and Emergency Stop Manager (Milestone 5)."""

from pathlib import Path
import pytest

from backend.app.desktop.capture import CaptureBroker
from backend.app.desktop.emergency import EmergencyStopManager
from backend.app.desktop.executor import DesktopActionExecutor
from backend.app.desktop.guard import WindowFocusGuard
from backend.app.desktop.mock_adapter import MockDesktopAdapter
from backend.app.desktop.session import TargetSessionManager
from backend.app.desktop.tools import (
    DesktopCaptureWindowTool,
    DesktopEmergencyStopTool,
    DesktopExecuteActionTool,
    DesktopInspectTreeTool,
    DesktopListWindowsTool,
    register_desktop_tools,
)
from backend.app.desktop.tree import AccessibilityTreeInspector
from backend.app.desktop.verifier import PostconditionVerifier
from backend.app.models.agent import RiskLevel
from backend.app.tools.registry import ToolRegistry


@pytest.fixture
def tools_env(tmp_path: Path):
    adapter = MockDesktopAdapter()
    guard = WindowFocusGuard(adapter)
    session = TargetSessionManager(adapter, guard)
    capture = CaptureBroker(adapter, storage_dir=tmp_path / "quarantine")
    tree = AccessibilityTreeInspector(adapter)
    verifier = PostconditionVerifier(tree)
    emergency = EmergencyStopManager()
    executor = DesktopActionExecutor(
        adapter=adapter,
        guard=guard,
        capture_broker=capture,
        tree_inspector=tree,
        verifier=verifier,
        emergency_manager=emergency,
        settle_delay_sec=0.0,
    )
    registry = ToolRegistry()
    register_desktop_tools(registry, session, tree, capture, executor, emergency)

    return adapter, session, emergency, executor, registry


@pytest.mark.asyncio
async def test_tool_registration_and_risk_levels(tools_env):
    """Verify all 5 desktop tools are registered with expected risk classifications."""
    _, _, _, _, registry = tools_env

    list_tool = registry.get("desktop_list_windows")
    assert list_tool is not None
    assert list_tool.risk_level == RiskLevel.SAFE

    tree_tool = registry.get("desktop_inspect_tree")
    assert tree_tool is not None
    assert tree_tool.risk_level == RiskLevel.SAFE

    cap_tool = registry.get("desktop_capture_window")
    assert cap_tool is not None
    assert cap_tool.risk_level == RiskLevel.SAFE

    act_tool = registry.get("desktop_execute_action")
    assert act_tool is not None
    assert act_tool.risk_level == RiskLevel.SENSITIVE  # Requires operator confirmation

    estop_tool = registry.get("desktop_emergency_stop")
    assert estop_tool is not None
    assert estop_tool.risk_level == RiskLevel.SAFE


@pytest.mark.asyncio
async def test_desktop_tools_execution_flow(tools_env):
    """Verify full tool execution sequence: list -> bind -> inspect -> capture -> act."""
    _, session, _, _, registry = tools_env

    # 1. List windows
    list_tool = registry.get("desktop_list_windows")
    res = await list_tool.execute(query="notepad")
    assert res["count"] == 1
    assert res["windows"][0]["hwnd"] == 1001

    # 2. Bind Notepad
    session.bind_window(1001)

    # 3. Inspect tree
    tree_tool = registry.get("desktop_inspect_tree")
    tree_res = await tree_tool.execute()
    assert tree_res["hwnd"] == 1001
    assert tree_res["root_element"]["automation_id"] == "NotepadWindow"

    # 4. Capture window
    cap_tool = registry.get("desktop_capture_window")
    cap_res = await cap_tool.execute()
    assert cap_res["image_id"].startswith("snap_")
    assert cap_res["width"] == 800

    # 5. Execute action
    act_tool = registry.get("desktop_execute_action")
    act_res = await act_tool.execute(
        action_type="type_text",
        target_element_id="elem_notepad_editor",
        text_input="Tools integration verified",
        expected_postcondition="text_contains:Tools integration verified",
    )
    assert act_res["status"] == "SUCCESS"
    assert act_res["verification_ok"] is True


@pytest.mark.asyncio
async def test_emergency_stop_halts_action(tools_env):
    """Verify triggering emergency stop blocks execution immediately."""
    _, session, emergency, _, registry = tools_env

    session.bind_window(1001)

    # Trigger emergency stop tool
    estop_tool = registry.get("desktop_emergency_stop")
    stop_res = await estop_tool.execute(reason="Manual test killswitch")
    assert stop_res["status"] == "STOPPED"
    assert emergency.is_stopped is True

    # Attempt to execute an action
    act_tool = registry.get("desktop_execute_action")
    blocked_res = await act_tool.execute(
        action_type="click",
        target_element_id="elem_notepad_menubar",
    )
    assert blocked_res["status"] == "CANCELLED"
    assert "Emergency stop is active" in blocked_res["message"]

    # Reset emergency stop
    assert emergency.reset(authorized=True) is True
    assert emergency.is_stopped is False
