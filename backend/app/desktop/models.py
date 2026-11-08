"""Domain models for Phase 12: Desktop Vision and Interaction Platform."""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class WindowRect(BaseModel):
    """Bounding rectangle for windows and UI elements."""

    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height

    def contains(self, rel_x: int, rel_y: int) -> bool:
        """Check if relative coordinate is within bounds [0, width) and [0, height)."""
        return 0 <= rel_x < self.width and 0 <= rel_y < self.height


class WindowSummary(BaseModel):
    """Summary of an operating system window."""

    hwnd: int
    pid: int
    process_name: str
    window_title: str
    bounds: WindowRect
    is_shielded: bool = False


class TargetWindowBinding(BaseModel):
    """Active authorized binding between an agent and a target application window."""

    hwnd: int
    pid: int
    process_name: str
    window_title: str
    bounds: WindowRect
    is_shielded: bool = False


class UIElementNode(BaseModel):
    """Structured representation of a Windows UI Automation tree node."""

    element_id: str
    automation_id: str = ""
    name: str = ""
    control_type: str = "Unknown"
    bounding_rect: WindowRect
    is_enabled: bool = True
    is_password: bool = False
    value: Optional[str] = None
    supported_patterns: list[str] = Field(default_factory=list)
    children: list["UIElementNode"] = Field(default_factory=list)


class DesktopActionType(str, Enum):
    """Supported typed actions against Windows desktop UI."""

    FOCUS = "focus"
    INSPECT_TREE = "inspect_tree"
    CLICK = "click"
    TYPE_TEXT = "type_text"
    SCROLL = "scroll"
    WAIT = "wait"


class DesktopActionRequest(BaseModel):
    """Structured request to perform an action against a bound window."""

    binding: TargetWindowBinding
    action_type: DesktopActionType
    target_element_id: Optional[str] = None
    relative_coords: Optional[tuple[int, int]] = None  # (rel_x, rel_y) inside window client rect
    text_input: Optional[str] = None
    scroll_amount: Optional[int] = None
    expected_postcondition: Optional[str] = None


class DesktopActionResult(BaseModel):
    """Execution and verification result of a desktop action."""

    action_id: str
    action_type: DesktopActionType
    status: str  # "SUCCESS", "UNCERTAIN", "FAILED", "CANCELLED"
    message: str
    verification_ok: bool
    pre_action_screenshot_id: Optional[str] = None
    post_action_screenshot_id: Optional[str] = None
    timestamp: str


class ScreenshotEvidence(BaseModel):
    """Metadata record for a task-scoped desktop screenshot."""

    image_id: str
    task_id: str
    hwnd: int
    file_path: str
    sha256_hash: str
    width: int
    height: int
    is_redacted: bool = False
    created_at: str
    expires_at: str


class AutonomousSessionConfig(BaseModel):
    """Budget and boundary configuration for autonomous desktop interaction."""

    session_id: str
    goal: str
    allowed_hwnds: list[int] = Field(default_factory=list)
    max_actions: int = Field(default=30, ge=1, le=100)
    max_duration_seconds: float = Field(default=600.0, ge=10.0, le=3600.0)
    require_confirmation: bool = False


class AutonomousSessionState(BaseModel):
    """Runtime tracking of an active or completed autonomous desktop session."""

    session_id: str
    goal: str
    status: str  # "READY", "RUNNING", "PAUSED", "STOPPED", "EXHAUSTED", "EMERGENCY_STOPPED"
    action_count: int = 0
    max_actions: int = 30
    elapsed_seconds: float = 0.0
    max_duration_seconds: float = 600.0
    bound_hwnd: Optional[int] = None
    last_action_message: Optional[str] = None
    created_at: str
    updated_at: str


class AutonomousStepResult(BaseModel):
    """Step execution response from the autonomous desktop loop."""

    session_id: str
    step_number: int
    action_result: Optional[DesktopActionResult] = None
    session_state: AutonomousSessionState
    is_terminal: bool = False
    terminal_reason: Optional[str] = None
