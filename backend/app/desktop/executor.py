"""Desktop Action Executor coordinating focus guards, synthetic input, and verification."""

from datetime import datetime, timezone
import logging
import time
import uuid

from backend.app.desktop.adapter import DesktopAdapter
from backend.app.desktop.capture import CaptureBroker
from backend.app.desktop.emergency import EmergencyStopActiveException, EmergencyStopManager
from backend.app.desktop.guard import DesktopSecurityException, WindowFocusGuard
from backend.app.desktop.models import (
    DesktopActionRequest,
    DesktopActionResult,
    DesktopActionType,
)
from backend.app.desktop.tree import AccessibilityTreeInspector
from backend.app.desktop.verifier import PostconditionVerifier

logger = logging.getLogger("nexora.desktop.executor")


class DesktopActionExecutor:
    """Executes atomic, verified desktop actions against positively bound windows."""

    def __init__(
        self,
        adapter: DesktopAdapter,
        guard: WindowFocusGuard,
        capture_broker: CaptureBroker,
        tree_inspector: AccessibilityTreeInspector,
        verifier: PostconditionVerifier,
        emergency_manager: Optional[EmergencyStopManager] = None,
        settle_delay_sec: float = 0.05,
    ) -> None:
        self.adapter = adapter
        self.guard = guard
        self.capture_broker = capture_broker
        self.tree_inspector = tree_inspector
        self.verifier = verifier
        self.emergency_manager = emergency_manager
        self.settle_delay_sec = settle_delay_sec

    def execute_action(
        self,
        request: DesktopActionRequest,
        task_id: str = "default_task",
    ) -> DesktopActionResult:
        """Execute a single typed desktop action with pre/post verification."""
        action_id = f"act_{uuid.uuid4().hex[:10]}"
        now_iso = datetime.now(timezone.utc).isoformat()

        # 0. Emergency Stop Check
        if self.emergency_manager and self.emergency_manager.is_stopped:
            logger.warning("Action %s aborted: Emergency stop is active", action_id)
            return DesktopActionResult(
                action_id=action_id,
                action_type=request.action_type,
                status="CANCELLED",
                message=f"Action blocked: Emergency stop is active ({self.emergency_manager.stop_reason})",
                verification_ok=False,
                timestamp=now_iso,
            )

        # 1. Pre-action Focus Guard Check
        try:
            self.guard.verify_focus(request.binding)
        except DesktopSecurityException as exc:
            logger.warning("Pre-action guard rejected action %s: %s", action_id, exc)
            return DesktopActionResult(
                action_id=action_id,
                action_type=request.action_type,
                status="UNCERTAIN",
                message=f"Focus guard rejected action: {exc}",
                verification_ok=False,
                timestamp=now_iso,
            )

        # 2. Pre-action Snapshot
        pre_ev = self.capture_broker.capture_and_redact(request.binding, task_id)

        # 3. Dispatch Typed Action
        dispatch_error: str | None = None
        try:
            if request.action_type == DesktopActionType.FOCUS:
                ok = self.adapter.set_foreground_window(request.binding.hwnd)
                if not ok:
                    dispatch_error = f"Failed to set foreground window HWND {request.binding.hwnd}"

            elif request.action_type == DesktopActionType.INSPECT_TREE:
                # Read-only action
                pass

            elif request.action_type == DesktopActionType.CLICK:
                if request.target_element_id:
                    ok = self.adapter.click_element(request.binding.hwnd, request.target_element_id)
                    if not ok:
                        dispatch_error = f"Element {request.target_element_id} was not clickable."
                elif request.relative_coords:
                    rx, ry = request.relative_coords
                    if not request.binding.bounds.contains(rx, ry):
                        dispatch_error = (
                            f"Bounds violation: Coordinates ({rx}, {ry}) fall outside window bounds "
                            f"(width={request.binding.bounds.width}, height={request.binding.bounds.height})."
                        )
                    else:
                        ok = self.adapter.click_coords(request.binding.hwnd, rx, ry)
                        if not ok:
                            dispatch_error = f"Failed to click coordinates ({rx}, {ry})"
                else:
                    dispatch_error = "Click action requires either target_element_id or relative_coords."

            elif request.action_type == DesktopActionType.TYPE_TEXT:
                if request.text_input is None:
                    dispatch_error = "Type action requires text_input."
                else:
                    ok = self.adapter.type_text(
                        request.binding.hwnd,
                        request.text_input,
                        element_id=request.target_element_id,
                    )
                    if not ok:
                        dispatch_error = "Failed sending text input to target window."

            elif request.action_type == DesktopActionType.SCROLL:
                amount = request.scroll_amount if request.scroll_amount is not None else -1
                ok = self.adapter.scroll(request.binding.hwnd, amount)
                if not ok:
                    dispatch_error = "Failed sending scroll event."

            elif request.action_type == DesktopActionType.WAIT:
                pass

        except Exception as e:
            logger.exception("Error executing action %s: %s", action_id, e)
            dispatch_error = f"Execution exception: {e}"

        if dispatch_error:
            return DesktopActionResult(
                action_id=action_id,
                action_type=request.action_type,
                status="UNCERTAIN",
                message=dispatch_error,
                verification_ok=False,
                pre_action_screenshot_id=pre_ev.image_id,
                timestamp=now_iso,
            )

        # 4. Settle Delay
        if self.settle_delay_sec > 0:
            time.sleep(self.settle_delay_sec)

        # 5. Post-action Focus Check
        try:
            self.guard.verify_focus(request.binding)
        except DesktopSecurityException as exc:
            logger.warning("Post-action focus lost for %s: %s", action_id, exc)
            return DesktopActionResult(
                action_id=action_id,
                action_type=request.action_type,
                status="UNCERTAIN",
                message=f"Post-action focus check failed: {exc}",
                verification_ok=False,
                pre_action_screenshot_id=pre_ev.image_id,
                timestamp=now_iso,
            )

        # 6. Post-action Snapshot and Tree Query
        post_ev = self.capture_broker.capture_and_redact(request.binding, task_id)
        post_tree = self.tree_inspector.inspect_and_sanitize(request.binding.hwnd)

        # 7. Postcondition Verification
        verified, ver_msg = self.verifier.verify_action(
            request.expected_postcondition,
            pre_ev,
            post_ev,
            post_tree,
        )

        final_status = "SUCCESS" if verified else "UNCERTAIN"
        return DesktopActionResult(
            action_id=action_id,
            action_type=request.action_type,
            status=final_status,
            message=ver_msg,
            verification_ok=verified,
            pre_action_screenshot_id=pre_ev.image_id,
            post_action_screenshot_id=post_ev.image_id,
            timestamp=now_iso,
        )
