"""Autonomous Desktop Loop Controller with Budgeting, Window Guardrails, and Fail-Closed Emergency Stop."""

from datetime import datetime, timezone
import logging
import time
from typing import Optional

from backend.app.desktop.models import (
    AutonomousSessionConfig,
    AutonomousSessionState,
    AutonomousStepResult,
    DesktopActionRequest,
    DesktopActionResult,
    DesktopActionType,
    TargetWindowBinding,
)
from backend.app.desktop.service import DesktopService

logger = logging.getLogger("nexora.desktop.autonomy")


class AutonomousSessionRecord:
    """Internal tracker for an active desktop autonomy session."""

    def __init__(self, config: AutonomousSessionConfig):
        self.config = config
        self.status = "READY"
        self.action_count = 0
        self.start_time = time.time()
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.updated_at = self.created_at
        self.last_action_message: Optional[str] = None
        self.bound_hwnd: Optional[int] = config.allowed_hwnds[0] if config.allowed_hwnds else None

    @property
    def elapsed_seconds(self) -> float:
        return round(time.time() - self.start_time, 2)

    def to_state(self) -> AutonomousSessionState:
        return AutonomousSessionState(
            session_id=self.config.session_id,
            goal=self.config.goal,
            status=self.status,
            action_count=self.action_count,
            max_actions=self.config.max_actions,
            elapsed_seconds=self.elapsed_seconds,
            max_duration_seconds=self.config.max_duration_seconds,
            bound_hwnd=self.bound_hwnd,
            last_action_message=self.last_action_message,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )


class AutonomousSessionController:
    """Orchestrates bounded multi-step autonomous desktop interaction."""

    def __init__(self, desktop_service: DesktopService):
        self.desktop_service = desktop_service
        self._sessions: dict[str, AutonomousSessionRecord] = {}

    def start_session(self, config: AutonomousSessionConfig) -> AutonomousSessionState:
        """Initialize and start an autonomous desktop session bounded by budgets and allowed HWNDs."""
        # Validate HWNDs
        if config.allowed_hwnds:
            for hwnd in config.allowed_hwnds:
                # Ensure window exists and is not shielded
                rect = self.desktop_service.adapter.get_window_rect(hwnd)
                if rect.width <= 0 or rect.height <= 0:
                    raise ValueError(f"Window HWND {hwnd} has invalid geometry or does not exist.")

        session = AutonomousSessionRecord(config)
        session.status = "RUNNING"
        self._sessions[config.session_id] = session
        logger.info(
            "Started autonomous desktop session '%s' (max_actions: %s, max_sec: %s)",
            config.session_id,
            config.max_actions,
            config.max_duration_seconds,
        )
        return session.to_state()

    def get_session(self, session_id: str) -> Optional[AutonomousSessionState]:
        """Retrieve state of an active or completed session."""
        session = self._sessions.get(session_id)
        return session.to_state() if session else None

    def pause_session(self, session_id: str) -> Optional[AutonomousSessionState]:
        """Pause session execution."""
        session = self._sessions.get(session_id)
        if not session:
            return None
        session.status = "PAUSED"
        session.updated_at = datetime.now(timezone.utc).isoformat()
        return session.to_state()

    def resume_session(self, session_id: str) -> Optional[AutonomousSessionState]:
        """Resume paused session."""
        session = self._sessions.get(session_id)
        if not session:
            return None
        session.status = "RUNNING"
        session.updated_at = datetime.now(timezone.utc).isoformat()
        return session.to_state()

    def stop_session(self, session_id: str, reason: str = "Stopped by operator") -> Optional[AutonomousSessionState]:
        """Stop session permanently."""
        session = self._sessions.get(session_id)
        if not session:
            return None
        session.status = "STOPPED"
        session.last_action_message = reason
        session.updated_at = datetime.now(timezone.utc).isoformat()
        return session.to_state()

    async def execute_step(
        self,
        session_id: str,
        action: Optional[DesktopActionRequest] = None,
    ) -> AutonomousStepResult:
        """Execute a single verified step within the bounded session envelope."""
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session '{session_id}' not found.")

        # 1. Emergency Stop Check (Highest priority fail-closed)
        if self.desktop_service.emergency_manager.is_stopped:
            session.status = "EMERGENCY_STOPPED"
            session.last_action_message = "Emergency stop is active; execution halted."
            session.updated_at = datetime.now(timezone.utc).isoformat()
            return AutonomousStepResult(
                session_id=session_id,
                step_number=session.action_count,
                action_result=None,
                session_state=session.to_state(),
                is_terminal=True,
                terminal_reason="EMERGENCY_STOPPED",
            )

        # 2. Check Session State
        if session.status in ("STOPPED", "EXHAUSTED", "EMERGENCY_STOPPED"):
            return AutonomousStepResult(
                session_id=session_id,
                step_number=session.action_count,
                action_result=None,
                session_state=session.to_state(),
                is_terminal=True,
                terminal_reason=f"Session is already {session.status}",
            )

        # 3. Action Budget Check
        if session.action_count >= session.config.max_actions:
            session.status = "EXHAUSTED"
            session.last_action_message = f"Action budget limit reached ({session.config.max_actions})."
            session.updated_at = datetime.now(timezone.utc).isoformat()
            return AutonomousStepResult(
                session_id=session_id,
                step_number=session.action_count,
                action_result=None,
                session_state=session.to_state(),
                is_terminal=True,
                terminal_reason="BUDGET_ACTIONS_EXHAUSTED",
            )

        # 4. Duration Budget Check
        if session.elapsed_seconds >= session.config.max_duration_seconds:
            session.status = "EXHAUSTED"
            session.last_action_message = f"Duration budget limit reached ({session.config.max_duration_seconds}s)."
            session.updated_at = datetime.now(timezone.utc).isoformat()
            return AutonomousStepResult(
                session_id=session_id,
                step_number=session.action_count,
                action_result=None,
                session_state=session.to_state(),
                is_terminal=True,
                terminal_reason="BUDGET_DURATION_EXHAUSTED",
            )

        # 5. Window Focus Verification Guard
        if session.config.allowed_hwnds:
            fg_hwnd = self.desktop_service.adapter.get_foreground_window()
            if fg_hwnd not in session.config.allowed_hwnds:
                # Attempt refocus once
                target_hwnd = session.bound_hwnd or session.config.allowed_hwnds[0]
                self.desktop_service.adapter.set_foreground_window(target_hwnd)
                fg_hwnd = self.desktop_service.adapter.get_foreground_window()

                if fg_hwnd not in session.config.allowed_hwnds:
                    session.status = "PAUSED"
                    session.last_action_message = (
                        f"Focus guard triggered: foreground window HWND {fg_hwnd} is outside allowed targets. Session paused."
                    )
                    session.updated_at = datetime.now(timezone.utc).isoformat()
                    return AutonomousStepResult(
                        session_id=session_id,
                        step_number=session.action_count,
                        action_result=None,
                        session_state=session.to_state(),
                        is_terminal=False,
                        terminal_reason="FOCUS_LOST",
                    )

        # 6. Execute Action (or default inspection step if no specific action provided)
        target_hwnd = session.bound_hwnd or (session.config.allowed_hwnds[0] if session.config.allowed_hwnds else None)
        if target_hwnd is None:
            active_binding = self.desktop_service.get_active_binding()
            target_hwnd = active_binding.hwnd if active_binding else 0

        if action is None:
            # Default step: capture inspection
            tree = self.desktop_service.inspect_tree(hwnd=target_hwnd)
            action_result = DesktopActionResult(
                action_id=f"step_{session.action_count + 1}",
                action_type=DesktopActionType.INSPECT_TREE,
                status="SUCCESS",
                message=f"Tree inspected ({tree.name or 'Window'}), {len(tree.children)} controls found.",
                verification_ok=True,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
        else:
            action_result = self.desktop_service.execute_action(action, task_id=session_id)

        session.action_count += 1
        session.last_action_message = action_result.message
        session.updated_at = datetime.now(timezone.utc).isoformat()

        # Check if action reached final budget on this step
        is_terminal = False
        terminal_reason = None
        if session.action_count >= session.config.max_actions:
            session.status = "EXHAUSTED"
            is_terminal = True
            terminal_reason = "BUDGET_ACTIONS_EXHAUSTED"

        return AutonomousStepResult(
            session_id=session_id,
            step_number=session.action_count,
            action_result=action_result,
            session_state=session.to_state(),
            is_terminal=is_terminal,
            terminal_reason=terminal_reason,
        )
