"""Unit tests for Desktop Action Executor and Postcondition Verifier (Milestone 4)."""

from pathlib import Path
import pytest

from backend.app.desktop.capture import CaptureBroker
from backend.app.desktop.executor import DesktopActionExecutor
from backend.app.desktop.guard import WindowFocusGuard
from backend.app.desktop.mock_adapter import MockDesktopAdapter
from backend.app.desktop.models import (
    DesktopActionRequest,
    DesktopActionType,
    TargetWindowBinding,
    WindowRect,
)
from backend.app.desktop.tree import AccessibilityTreeInspector
from backend.app.desktop.verifier import PostconditionVerifier


@pytest.fixture
def executor_env(tmp_path: Path):
    adapter = MockDesktopAdapter()
    guard = WindowFocusGuard(adapter)
    capture = CaptureBroker(adapter, storage_dir=tmp_path / "quarantine")
    tree = AccessibilityTreeInspector(adapter)
    verifier = PostconditionVerifier(tree)
    executor = DesktopActionExecutor(
        adapter=adapter,
        guard=guard,
        capture_broker=capture,
        tree_inspector=tree,
        verifier=verifier,
        settle_delay_sec=0.0,
    )
    binding = TargetWindowBinding(
        hwnd=1001,
        pid=5001,
        process_name="notepad.exe",
        window_title="Untitled - Notepad",
        bounds=WindowRect(x=100, y=100, width=800, height=600),
    )
    return adapter, guard, executor, binding


def test_executor_type_text_success_and_verified(executor_env):
    """Verify typing text into target element succeeds and fulfills postcondition."""
    adapter, _, executor, binding = executor_env

    req = DesktopActionRequest(
        binding=binding,
        action_type=DesktopActionType.TYPE_TEXT,
        target_element_id="elem_notepad_editor",
        text_input="NEXORA Automated Note",
        expected_postcondition="text_contains:NEXORA Automated Note",
    )

    result = executor.execute_action(req)
    assert result.status == "SUCCESS"
    assert result.verification_ok is True
    assert result.pre_action_screenshot_id is not None
    assert result.post_action_screenshot_id is not None
    assert "Found expected text" in result.message

    # Confirm text was injected into mock tree
    tree = adapter.inspect_tree(1001)
    editor = next(c for c in tree.children if c.control_type == "Edit")
    assert "NEXORA Automated Note" in editor.value


def test_executor_bounds_violation_returns_uncertain(executor_env):
    """Verify clicking outside window rect fails closed with UNCERTAIN."""
    _, _, executor, binding = executor_env

    # Coordinates (900, 700) exceed window size (800x600)
    req = DesktopActionRequest(
        binding=binding,
        action_type=DesktopActionType.CLICK,
        relative_coords=(900, 700),
    )

    result = executor.execute_action(req)
    assert result.status == "UNCERTAIN"
    assert result.verification_ok is False
    assert "Bounds violation" in result.message


def test_executor_pre_action_focus_lost(executor_env):
    """Verify focus shift before action aborts as UNCERTAIN."""
    adapter, _, executor, binding = executor_env

    # Switch foreground focus to another window
    adapter.set_foreground_window(1002)

    req = DesktopActionRequest(
        binding=binding,
        action_type=DesktopActionType.CLICK,
        target_element_id="elem_notepad_menubar",
    )

    result = executor.execute_action(req)
    assert result.status == "UNCERTAIN"
    assert result.verification_ok is False
    assert "Focus lost" in result.message


def test_executor_postcondition_unfulfilled_returns_uncertain(executor_env):
    """Verify missing expected text returns UNCERTAIN."""
    _, _, executor, binding = executor_env

    req = DesktopActionRequest(
        binding=binding,
        action_type=DesktopActionType.TYPE_TEXT,
        target_element_id="elem_notepad_editor",
        text_input="Just simple text",
        expected_postcondition="text_contains:Some Unfulfilled Keyword",
    )

    result = executor.execute_action(req)
    assert result.status == "UNCERTAIN"
    assert result.verification_ok is False
    assert "Postcondition unfulfilled" in result.message
