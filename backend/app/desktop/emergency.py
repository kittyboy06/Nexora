"""Global Emergency Stop Manager for Windows Desktop Interactions."""

import logging
import threading
from typing import Optional

logger = logging.getLogger("nexora.desktop.emergency")


class EmergencyStopActiveException(Exception):
    """Raised when an action is attempted while the emergency stop is actively engaged."""
    pass


class EmergencyStopManager:
    """Thread-safe global emergency stop controller."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._is_stopped = False
        self._stop_reason: Optional[str] = None
        self._stopped_at: Optional[str] = None

    @property
    def is_stopped(self) -> bool:
        with self._lock:
            return self._is_stopped

    @property
    def stop_reason(self) -> Optional[str]:
        with self._lock:
            return self._stop_reason

    def trigger_emergency_stop(self, reason: str = "Operator manual emergency stop") -> bool:
        """Engage the emergency stop, halting all active and pending desktop automation."""
        with self._lock:
            self._is_stopped = True
            self._stop_reason = reason
            from datetime import datetime, timezone
            self._stopped_at = datetime.now(timezone.utc).isoformat()
            logger.critical("EMERGENCY STOP ENGAGED: %s", reason)
            return True

    def trigger_stop(self, reason: str = "Operator manual emergency stop") -> bool:
        """Convenience alias for trigger_emergency_stop."""
        return self.trigger_emergency_stop(reason)

    def reset(self, authorized: bool = True) -> bool:
        """Reset the emergency stop state once safe."""
        if not authorized:
            return False
        with self._lock:
            self._is_stopped = False
            self._stop_reason = None
            self._stopped_at = None
            logger.info("Emergency stop reset by authorized operator.")
            return True

    def check_stopped(self) -> None:
        """Check if emergency stop is active, raising an exception if so."""
        with self._lock:
            if self._is_stopped:
                raise EmergencyStopActiveException(
                    f"Desktop automation is locked by Emergency Stop: {self._stop_reason}"
                )
