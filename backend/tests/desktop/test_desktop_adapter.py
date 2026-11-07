"""Unit tests for Desktop Adapters and Domain Models (Milestone 1)."""

import pytest
from backend.tests.fixtures.desktop_mock_adapter import DUMMY_PNG_BYTES, MockDesktopAdapter
from backend.app.desktop.models import (
    DesktopActionRequest,
    DesktopActionResult,
    DesktopActionType,
    TargetWindowBinding,
    UIElementNode,
    WindowRect,
    WindowSummary,
)
from backend.app.desktop.win32_adapter import Win32DesktopAdapter


def test_window_rect_bounds():
    """Verify WindowRect arithmetic and relative containment."""
    rect = WindowRect(x=100, y=200, width=800, height=600)
    assert rect.right == 900
    assert rect.bottom == 800

    # Inside
    assert rect.contains(0, 0) is True
    assert rect.contains(400, 300) is True
    assert rect.contains(799, 599) is True

    # Outside
    assert rect.contains(-1, 0) is False
    assert rect.contains(0, -1) is False
    assert rect.contains(800, 300) is False
    assert rect.contains(400, 600) is False


def test_mock_desktop_adapter_discovery_and_focus():
    """Verify MockDesktopAdapter window listing and focus management."""
    adapter = MockDesktopAdapter()

    windows = adapter.list_windows()
    assert len(windows) >= 3
    hwnds = {w.hwnd for w in windows}
    assert 1001 in hwnds  # Notepad
    assert 1002 in hwnds  # Calculator
    assert 9001 in hwnds  # 1Password

    # Foreground tracking
    assert adapter.get_foreground_window() == 1001
    assert "Notepad" in adapter.get_window_text(1001)

    # Set focus to Calculator
    assert adapter.set_foreground_window(1002) is True
    assert adapter.get_foreground_window() == 1002
    assert adapter.set_foreground_window(99999) is False


def test_mock_desktop_adapter_tree_and_redaction():
    """Verify UI Automation tree inspection and password detection."""
    adapter = MockDesktopAdapter()

    # Notepad Tree
    notepad_tree = adapter.inspect_tree(1001)
    assert notepad_tree.control_type == "Window"
    assert len(notepad_tree.children) == 2
    editor_node = next(c for c in notepad_tree.children if c.control_type == "Edit")
    assert editor_node.automation_id == "TextEditor"
    assert editor_node.is_password is False

    # 1Password Tree with password field
    pwd_tree = adapter.inspect_tree(9001)
    pwd_node = pwd_tree.children[0]
    assert pwd_node.is_password is True
    assert pwd_node.value == "super_secret_master_key"


def test_mock_desktop_adapter_capture_and_actions():
    """Verify capture, coordinate bounds checking, and text typing."""
    adapter = MockDesktopAdapter()

    # Capture
    raw_bytes, width, height = adapter.capture_window(1001)
    assert raw_bytes == DUMMY_PNG_BYTES
    assert width == 800
    assert height == 600

    # Click coords within window bounds
    assert adapter.click_coords(1001, 100, 100) is True
    assert adapter.click_coords(1001, 900, 700) is False  # Out of bounds

    # Type text into Notepad
    assert adapter.type_text(1001, "Hello World", element_id="elem_notepad_editor") is True
    notepad_tree = adapter.inspect_tree(1001)
    editor_node = next(c for c in notepad_tree.children if c.control_type == "Edit")
    assert editor_node.value == "Hello World"

    # Click element
    assert adapter.click_element(1001, "elem_notepad_menubar") is True

    # Scroll
    assert adapter.scroll(1001, 3) is True
    assert len(adapter.input_log) == 4


def test_win32_desktop_adapter_instantiation():
    """Verify Win32DesktopAdapter initializes safely on the platform."""
    adapter = Win32DesktopAdapter()
    assert adapter is not None
    # Basic method calls should not crash
    fg = adapter.get_foreground_window()
    assert isinstance(fg, int)
    rect = adapter.get_window_rect(fg)
    assert isinstance(rect, WindowRect)
