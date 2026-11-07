"""Core tools providing bounded desktop UI interaction and observation to agents."""

from typing import Any, Optional
from pydantic import BaseModel, Field

from backend.app.desktop.capture import CaptureBroker
from backend.app.desktop.emergency import EmergencyStopManager
from backend.app.desktop.executor import DesktopActionExecutor
from backend.app.desktop.guard import ShieldedWindowException
from backend.app.desktop.models import (
    DesktopActionRequest,
    DesktopActionType,
    TargetWindowBinding,
)
from backend.app.desktop.session import TargetSessionManager
from backend.app.desktop.tree import AccessibilityTreeInspector
from backend.app.models.agent import RiskLevel
from backend.app.tools.base import BaseTool
from backend.app.tools.registry import ToolRegistry


class ListWindowsArgs(BaseModel):
    query: Optional[str] = Field(default=None, description="Optional keyword to filter windows by title or process name")


class DesktopListWindowsTool(BaseTool):
    """List open top-level windows on the desktop (excluding shielded security windows)."""

    def __init__(self, session_manager: TargetSessionManager) -> None:
        self.session_manager = session_manager
        self.name = "desktop_list_windows"
        self.description = "List currently open desktop application windows with their titles, HWNDs, and process names."
        self.risk_level = RiskLevel.SAFE
        self.args_schema = ListWindowsArgs

    async def execute(self, query: Optional[str] = None, **kwargs: Any) -> dict[str, Any]:
        windows = self.session_manager.list_windows(include_shielded=False)
        if query and query.strip():
            q = query.strip().lower()
            windows = [w for w in windows if q in w.window_title.lower() or q in w.process_name.lower()]

        return {
            "count": len(windows),
            "windows": [
                {
                    "hwnd": w.hwnd,
                    "pid": w.pid,
                    "process_name": w.process_name,
                    "window_title": w.window_title,
                    "bounds": {"x": w.bounds.x, "y": w.bounds.y, "width": w.bounds.width, "height": w.bounds.height},
                }
                for w in windows
            ],
        }


class InspectTreeArgs(BaseModel):
    hwnd: Optional[int] = Field(default=None, description="Target window HWND (uses active bound window if omitted)")
    max_depth: int = Field(default=4, ge=1, le=8, description="Maximum depth of tree hierarchy to traverse")


class DesktopInspectTreeTool(BaseTool):
    """Inspect accessibility UI Automation tree of a target application window."""

    def __init__(self, session_manager: TargetSessionManager, tree_inspector: AccessibilityTreeInspector) -> None:
        self.session_manager = session_manager
        self.tree_inspector = tree_inspector
        self.name = "desktop_inspect_tree"
        self.description = "Inspect the accessibility UI Automation tree of an application window to discover clickable controls and text fields."
        self.risk_level = RiskLevel.SAFE
        self.args_schema = InspectTreeArgs

    async def execute(self, hwnd: Optional[int] = None, max_depth: int = 4, **kwargs: Any) -> dict[str, Any]:
        target_hwnd = hwnd
        if not target_hwnd:
            active = self.session_manager.get_active_binding()
            if not active:
                return {"error": "No active window binding. Specify an hwnd or list windows first."}
            target_hwnd = active.hwnd

        tree = self.tree_inspector.inspect_and_sanitize(target_hwnd, max_depth=max_depth)
        return {
            "hwnd": target_hwnd,
            "root_element": tree.model_dump(),
        }


class CaptureWindowArgs(BaseModel):
    hwnd: Optional[int] = Field(default=None, description="Target window HWND (uses active bound window if omitted)")


class DesktopCaptureWindowTool(BaseTool):
    """Capture a bounded, privacy-redacted screenshot of a target application window."""

    def __init__(self, session_manager: TargetSessionManager, capture_broker: CaptureBroker) -> None:
        self.session_manager = session_manager
        self.capture_broker = capture_broker
        self.name = "desktop_capture_window"
        self.description = "Capture a window-bounded, redacted screenshot of an application window for visual observation."
        self.risk_level = RiskLevel.SAFE
        self.args_schema = CaptureWindowArgs

    async def execute(self, hwnd: Optional[int] = None, **kwargs: Any) -> dict[str, Any]:
        target_binding: Optional[TargetWindowBinding] = None
        if hwnd:
            try:
                target_binding = self.session_manager.bind_window(hwnd)
            except ShieldedWindowException as e:
                return {"error": str(e)}
        else:
            target_binding = self.session_manager.get_active_binding()

        if not target_binding:
            return {"error": "No target window bound. Specify an hwnd to capture."}

        task_id = kwargs.get("task_id", "default_task")
        evidence = self.capture_broker.capture_and_redact(target_binding, task_id=task_id)
        return {
            "image_id": evidence.image_id,
            "hwnd": evidence.hwnd,
            "width": evidence.width,
            "height": evidence.height,
            "is_redacted": evidence.is_redacted,
            "sha256_hash": evidence.sha256_hash,
            "file_path": evidence.file_path,
        }


class ExecuteActionArgs(BaseModel):
    action_type: str = Field(..., description="Action type: 'focus', 'click', 'type_text', 'scroll', or 'wait'")
    target_element_id: Optional[str] = Field(default=None, description="UI Automation element ID to target")
    relative_coords: Optional[list[int]] = Field(default=None, description="Relative coordinates [x, y] inside target window")
    text_input: Optional[str] = Field(default=None, description="Text string to type")
    scroll_amount: Optional[int] = Field(default=None, description="Number of notches to scroll (positive=up, negative=down)")
    expected_postcondition: Optional[str] = Field(default=None, description="Expected postcondition (e.g. 'text_contains:Saved' or 'visual_change')")


class DesktopExecuteActionTool(BaseTool):
    """Execute a typed, bounded UI interaction against the bound window with pre/post verification."""

    def __init__(self, session_manager: TargetSessionManager, executor: DesktopActionExecutor) -> None:
        self.session_manager = session_manager
        self.executor = executor
        self.name = "desktop_execute_action"
        self.description = "Execute a typed desktop action (click element, type text, scroll) against the active window with visual verification."
        self.risk_level = RiskLevel.SENSITIVE
        self.args_schema = ExecuteActionArgs

    async def execute(
        self,
        action_type: str,
        target_element_id: Optional[str] = None,
        relative_coords: Optional[list[int]] = None,
        text_input: Optional[str] = None,
        scroll_amount: Optional[int] = None,
        expected_postcondition: Optional[str] = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        active_binding = self.session_manager.get_active_binding()
        if not active_binding:
            return {"error": "No window is currently bound. Use desktop_list_windows or bind first."}

        try:
            atype = DesktopActionType(action_type.lower())
        except ValueError:
            return {"error": f"Invalid action_type '{action_type}'. Valid values: focus, click, type_text, scroll, wait."}

        coords_tuple = tuple(relative_coords) if relative_coords and len(relative_coords) == 2 else None

        req = DesktopActionRequest(
            binding=active_binding,
            action_type=atype,
            target_element_id=target_element_id,
            relative_coords=coords_tuple,
            text_input=text_input,
            scroll_amount=scroll_amount,
            expected_postcondition=expected_postcondition,
        )

        task_id = kwargs.get("task_id", "default_task")
        result = self.executor.execute_action(req, task_id=task_id)
        return result.model_dump()


class EmergencyStopArgs(BaseModel):
    reason: Optional[str] = Field(default="Operator emergency stop", description="Reason for engaging emergency stop")


class DesktopEmergencyStopTool(BaseTool):
    """Immediately engage the emergency stop, halting all desktop automation."""

    def __init__(self, emergency_manager: EmergencyStopManager) -> None:
        self.emergency_manager = emergency_manager
        self.name = "desktop_emergency_stop"
        self.description = "Immediately engage the emergency stop, halting all active and queued desktop automation."
        self.risk_level = RiskLevel.SAFE
        self.args_schema = EmergencyStopArgs

    async def execute(self, reason: Optional[str] = None, **kwargs: Any) -> dict[str, Any]:
        msg = reason or "Operator emergency stop"
        self.emergency_manager.trigger_emergency_stop(reason=msg)
        return {
            "status": "STOPPED",
            "message": "Emergency stop has been engaged. All desktop actions are blocked.",
            "reason": msg,
        }


def register_desktop_tools(
    tool_registry: ToolRegistry,
    session_manager: TargetSessionManager,
    tree_inspector: AccessibilityTreeInspector,
    capture_broker: CaptureBroker,
    executor: DesktopActionExecutor,
    emergency_manager: EmergencyStopManager,
) -> None:
    """Register desktop vision and interaction tools in NEXORA central registry."""
    tool_registry.register(DesktopListWindowsTool(session_manager))
    tool_registry.register(DesktopInspectTreeTool(session_manager, tree_inspector))
    tool_registry.register(DesktopCaptureWindowTool(session_manager, capture_broker))
    tool_registry.register(DesktopExecuteActionTool(session_manager, executor))
    tool_registry.register(DesktopEmergencyStopTool(emergency_manager))
