"""Target Window Session Manager for Desktop Automation."""

import logging
from typing import Optional

from backend.app.desktop.adapter import DesktopAdapter
from backend.app.desktop.guard import ShieldedWindowException, WindowFocusGuard
from backend.app.desktop.models import TargetWindowBinding, WindowSummary

logger = logging.getLogger("nexora.desktop.session")


class TargetSessionManager:
    """Manages active target window bindings and enforces discovery policy."""

    def __init__(self, adapter: DesktopAdapter, guard: WindowFocusGuard) -> None:
        self.adapter = adapter
        self.guard = guard
        self._active_binding: Optional[TargetWindowBinding] = None

    def list_windows(self, include_shielded: bool = False) -> list[WindowSummary]:
        """List active windows with shielded status tagged."""
        raw_windows = self.adapter.list_windows()
        result: list[WindowSummary] = []
        for w in raw_windows:
            shielded = self.guard.is_shielded(w.process_name, w.window_title)
            w.is_shielded = shielded
            if shielded and not include_shielded:
                continue
            result.append(w)
        return result

    def bind_window(self, hwnd: int, bring_to_front: bool = True) -> TargetWindowBinding:
        """Bind target window after safety and shielded validation."""
        windows = self.adapter.list_windows()
        target = next((w for w in windows if w.hwnd == hwnd), None)
        if not target:
            raise ValueError(f"Window with HWND {hwnd} was not found on desktop.")

        # Enforce shielding policy
        self.guard.check_can_bind(target)

        if bring_to_front:
            self.adapter.set_foreground_window(hwnd)

        live_rect = self.adapter.get_window_rect(hwnd)
        live_title = self.adapter.get_window_text(hwnd) or target.window_title

        binding = TargetWindowBinding(
            hwnd=target.hwnd,
            pid=target.pid,
            process_name=target.process_name,
            window_title=live_title,
            bounds=live_rect,
            is_shielded=False,
        )
        self._active_binding = binding
        logger.info("Bound active target window HWND %s (%s, %s)", hwnd, binding.process_name, binding.window_title)
        return binding

    def get_active_binding(self) -> Optional[TargetWindowBinding]:
        """Return the current active target window binding, if any."""
        return self._active_binding

    def release_binding(self) -> None:
        """Release current target window binding."""
        if self._active_binding:
            logger.info("Released active target window HWND %s", self._active_binding.hwnd)
            self._active_binding = None
