"""Desktop Service orchestrating adapters, guards, capture broker, executor, and emergency stop."""

import logging
from pathlib import Path
from typing import Optional

from backend.app.desktop.adapter import DesktopAdapter
from backend.app.desktop.capture import CaptureBroker
from backend.app.desktop.emergency import EmergencyStopManager
from backend.app.desktop.executor import DesktopActionExecutor
from backend.app.desktop.guard import WindowFocusGuard
from backend.app.desktop.models import (
    DesktopActionRequest,
    DesktopActionResult,
    ScreenshotEvidence,
    TargetWindowBinding,
    UIElementNode,
    WindowSummary,
)
from backend.app.desktop.session import TargetSessionManager
from backend.app.desktop.tree import AccessibilityTreeInspector
from backend.app.desktop.verifier import PostconditionVerifier
from backend.app.desktop.win32_adapter import Win32DesktopAdapter

logger = logging.getLogger("nexora.desktop.service")


class DesktopService:
    """Central domain service coordinating all desktop vision and interaction capabilities."""

    def __init__(
        self,
        quarantine_dir: Path,
        adapter: Optional[DesktopAdapter] = None,
        settle_delay_sec: float = 0.05,
    ) -> None:
        self.adapter = adapter or Win32DesktopAdapter()
        self.guard = WindowFocusGuard(self.adapter)
        self.session_manager = TargetSessionManager(self.adapter, self.guard)
        self.capture_broker = CaptureBroker(self.adapter, storage_dir=quarantine_dir)
        self.tree_inspector = AccessibilityTreeInspector(self.adapter)
        self.verifier = PostconditionVerifier(self.tree_inspector)
        self.emergency_manager = EmergencyStopManager()
        self.executor = DesktopActionExecutor(
            adapter=self.adapter,
            guard=self.guard,
            capture_broker=self.capture_broker,
            tree_inspector=self.tree_inspector,
            verifier=self.verifier,
            emergency_manager=self.emergency_manager,
            settle_delay_sec=settle_delay_sec,
        )

    def list_windows(self, query: Optional[str] = None, include_shielded: bool = False) -> list[WindowSummary]:
        """List open top-level application windows."""
        windows = self.session_manager.list_windows(include_shielded=include_shielded)
        if query and query.strip():
            q = query.strip().lower()
            windows = [w for w in windows if q in w.window_title.lower() or q in w.process_name.lower()]
        return windows

    def bind_window(self, hwnd: int) -> TargetWindowBinding:
        """Bind active target window."""
        return self.session_manager.bind_window(hwnd)

    def get_active_binding(self) -> Optional[TargetWindowBinding]:
        """Get currently bound target window."""
        return self.session_manager.get_active_binding()

    def release_binding(self) -> None:
        """Release active target window binding."""
        self.session_manager.release_binding()

    def inspect_tree(self, hwnd: Optional[int] = None, max_depth: int = 4) -> UIElementNode:
        """Inspect and sanitize accessibility tree for specified or bound window."""
        target_hwnd = hwnd
        if not target_hwnd:
            active = self.session_manager.get_active_binding()
            if not active:
                raise ValueError("No active window binding. Specify an HWND or bind a window first.")
            target_hwnd = active.hwnd
        return self.tree_inspector.inspect_and_sanitize(target_hwnd, max_depth=max_depth)

    def capture_window(self, hwnd: Optional[int] = None, task_id: str = "default_task") -> ScreenshotEvidence:
        """Capture bounded, redacted screenshot of specified or bound window."""
        if hwnd:
            binding = self.session_manager.bind_window(hwnd)
        else:
            binding = self.session_manager.get_active_binding()
            if not binding:
                raise ValueError("No active window binding. Specify an HWND or bind a window first.")

        return self.capture_broker.capture_and_redact(binding, task_id=task_id)

    def execute_action(self, request: DesktopActionRequest, task_id: str = "default_task") -> DesktopActionResult:
        """Execute a typed, bounded desktop action with verification."""
        return self.executor.execute_action(request, task_id=task_id)

    def trigger_emergency_stop(self, reason: str = "Operator manual emergency stop") -> bool:
        """Immediately trigger emergency stop."""
        return self.emergency_manager.trigger_emergency_stop(reason=reason)

    def reset_emergency_stop(self, authorized: bool = True) -> bool:
        """Reset emergency stop."""
        return self.emergency_manager.reset(authorized=authorized)

    def is_emergency_stop_active(self) -> bool:
        """Check if emergency stop is currently engaged."""
        return self.emergency_manager.is_stopped

    def list_evidence(self, task_id: Optional[str] = None) -> list[ScreenshotEvidence]:
        """List captured screenshot evidence records."""
        return self.capture_broker.list_evidence(task_id=task_id)

    def get_evidence(self, image_id: str) -> Optional[ScreenshotEvidence]:
        """Retrieve screenshot evidence by image ID."""
        return self.capture_broker.get_evidence(image_id)
