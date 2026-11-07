"""Unit tests for Window Focus Guard, Shielding and Target Session Management (Milestone 2)."""

import pytest
from backend.app.desktop.guard import (
    FocusLostException,
    ShieldedWindowException,
    WindowFocusGuard,
    WindowTitleChangedException,
)
from backend.app.desktop.mock_adapter import MockDesktopAdapter
from backend.app.desktop.session import TargetSessionManager


def test_shielded_process_detection():
    """Verify blacklist detection for credential managers and security prompts."""
    adapter = MockDesktopAdapter()
    guard = WindowFocusGuard(adapter)

    # Protected processes
    assert guard.is_shielded("1password.exe", "1Password") is True
    assert guard.is_shielded("Bitwarden.exe", "Vault") is True
    assert guard.is_shielded("KeePass.exe", "KeePass") is True
    assert guard.is_shielded("CredentialUIBroker.exe", "Windows Security") is True

    # Protected titles
    assert guard.is_shielded("chrome.exe", "Master Password Prompt") is True
    assert guard.is_shielded("app.exe", "User Account Control") is True

    # Safe processes
    assert guard.is_shielded("notepad.exe", "Untitled - Notepad") is False
    assert guard.is_shielded("calc.exe", "Calculator") is False
    assert guard.is_shielded("code.exe", "workspace - VS Code") is False


def test_session_manager_bind_and_shield_rejection():
    """Verify TargetSessionManager blocks binding shielded windows."""
    adapter = MockDesktopAdapter()
    guard = WindowFocusGuard(adapter)
    manager = TargetSessionManager(adapter, guard)

    # Listing excludes shielded by default
    safe_windows = manager.list_windows(include_shielded=False)
    assert not any(w.process_name == "1password.exe" for w in safe_windows)

    all_windows = manager.list_windows(include_shielded=True)
    assert any(w.process_name == "1password.exe" for w in all_windows)

    # Attempting to bind shielded window (HWND 9001) raises ShieldedWindowException
    with pytest.raises(ShieldedWindowException) as exc:
        manager.bind_window(9001)
    assert "shielded from automation" in str(exc.value)

    # Binding safe window (Notepad HWND 1001) succeeds
    binding = manager.bind_window(1001)
    assert binding.hwnd == 1001
    assert binding.process_name == "notepad.exe"
    assert manager.get_active_binding() == binding

    # Release binding
    manager.release_binding()
    assert manager.get_active_binding() is None


def test_focus_guard_verification():
    """Verify fail-closed focus verification logic."""
    adapter = MockDesktopAdapter()
    guard = WindowFocusGuard(adapter)
    manager = TargetSessionManager(adapter, guard)

    binding = manager.bind_window(1001)  # Notepad

    # 1. Foreground focus matches -> Passes
    adapter.set_foreground_window(1001)
    guard.verify_focus(binding)  # Should not raise

    # 2. Foreground focus shifted to Calculator (HWND 1002) -> Raises FocusLostException
    adapter.set_foreground_window(1002)
    with pytest.raises(FocusLostException) as exc:
        guard.verify_focus(binding)
    assert "Focus lost" in str(exc.value)

    # 3. Window title shifted unexpectedly -> Raises WindowTitleChangedException
    adapter.set_foreground_window(1001)
    adapter.windows[1001].window_title = "Totally Different App Name"
    with pytest.raises(WindowTitleChangedException) as exc:
        guard.verify_focus(binding)
    assert "Window title shifted" in str(exc.value)
