"""Window Focus Guard and Shielded Process Filter for Desktop Automation."""

import logging
from typing import Set

from backend.app.desktop.adapter import DesktopAdapter
from backend.app.desktop.models import TargetWindowBinding, WindowSummary

logger = logging.getLogger("nexora.desktop.guard")

# Blacklist of sensitive processes that must never be observed or controlled
SHIELDED_PROCESSES: Set[str] = {
    "1password.exe",
    "bitwarden.exe",
    "keepass.exe",
    "keepassxc.exe",
    "credentialuibroker.exe",
    "sechealthui.exe",
    "lockapp.exe",
    "consent.exe",
    "taskmgr.exe",
}

# Substrings in window titles that indicate credentials or system security
SHIELDED_TITLE_PATTERNS = [
    "windows security",
    "credential manager",
    "user account control",
    "master password",
    "unlock vault",
    "bitlocker",
]


class DesktopSecurityException(Exception):
    """Base class for desktop security guard violations."""
    pass


class FocusLostException(DesktopSecurityException):
    """Raised when the target window is not currently in the foreground."""
    pass


class WindowTitleChangedException(DesktopSecurityException):
    """Raised when the target window title shifted unexpectedly."""
    pass


class ShieldedWindowException(DesktopSecurityException):
    """Raised when an attempt is made to bind or interact with a protected window."""
    pass


class WindowFocusGuard:
    """Enforces target window authorization, foreground focus integrity, and privacy shielding."""

    def __init__(self, adapter: DesktopAdapter) -> None:
        self.adapter = adapter

    def is_shielded(self, process_name: str, window_title: str) -> bool:
        """Check if process name or title matches shielded security criteria."""
        proc = process_name.lower().strip()
        if proc in SHIELDED_PROCESSES:
            return True

        title_lower = window_title.lower()
        if any(pat in title_lower for pat in SHIELDED_TITLE_PATTERNS):
            return True

        return False

    def check_can_bind(self, summary: WindowSummary) -> None:
        """Validate whether a window is safe to bind."""
        if self.is_shielded(summary.process_name, summary.window_title):
            logger.warning(
                "Attempted to bind shielded window HWND %s (%s, %s)",
                summary.hwnd,
                summary.process_name,
                summary.window_title,
            )
            raise ShieldedWindowException(
                f"Window '{summary.window_title}' ({summary.process_name}) is shielded from automation."
            )

    def verify_focus(self, binding: TargetWindowBinding) -> None:
        """Fail-closed pre-action focus and title check."""
        # 1. Shielded check
        if self.is_shielded(binding.process_name, binding.window_title):
            raise ShieldedWindowException(
                f"Target window '{binding.window_title}' is marked as shielded and cannot receive input."
            )

        # 2. Foreground check
        current_fg_hwnd = self.adapter.get_foreground_window()
        if current_fg_hwnd != binding.hwnd:
            current_title = self.adapter.get_window_text(current_fg_hwnd)
            logger.warning(
                "Focus guard failed: Expected HWND %s (%s), but foreground is HWND %s ('%s')",
                binding.hwnd,
                binding.window_title,
                current_fg_hwnd,
                current_title,
            )
            raise FocusLostException(
                f"Focus lost: Target window HWND {binding.hwnd} ('{binding.window_title}') is not in foreground. "
                f"Active foreground is HWND {current_fg_hwnd} ('{current_title}')."
            )

        # 3. Window title check
        live_title = self.adapter.get_window_text(binding.hwnd)
        if binding.window_title.lower() not in live_title.lower() and live_title.lower() not in binding.window_title.lower():
            logger.warning(
                "Window title shifted: Expected '%s', live title is '%s'",
                binding.window_title,
                live_title,
            )
            raise WindowTitleChangedException(
                f"Window title shifted from '{binding.window_title}' to '{live_title}'."
            )
