"""Abstract adapter interface for Windows desktop observation and interaction."""

from abc import ABC, abstractmethod
from typing import Optional

from backend.app.desktop.models import UIElementNode, WindowRect, WindowSummary


class DesktopAdapter(ABC):
    """Contract for native or simulated Windows desktop automation and observation."""

    @abstractmethod
    def list_windows(self) -> list[WindowSummary]:
        """List active visible top-level windows."""
        pass

    @abstractmethod
    def get_foreground_window(self) -> int:
        """Return the HWND of the currently active foreground window."""
        pass

    @abstractmethod
    def get_window_text(self, hwnd: int) -> str:
        """Return the window title bar text for the given HWND."""
        pass

    @abstractmethod
    def get_window_rect(self, hwnd: int) -> WindowRect:
        """Return the client rectangle bounds for the given HWND."""
        pass

    @abstractmethod
    def set_foreground_window(self, hwnd: int) -> bool:
        """Attempt to bring the specified HWND into foreground focus."""
        pass

    @abstractmethod
    def inspect_tree(self, hwnd: int, max_depth: int = 4) -> UIElementNode:
        """Traverse the UI Automation tree of the specified window."""
        pass

    @abstractmethod
    def capture_window(self, hwnd: int) -> tuple[bytes, int, int]:
        """Capture the window client rect as image bytes (PNG/JPEG format, width, height)."""
        pass

    @abstractmethod
    def click_element(self, hwnd: int, element_id: str) -> bool:
        """Invoke or click the specified UI Automation element."""
        pass

    @abstractmethod
    def click_coords(self, hwnd: int, rel_x: int, rel_y: int) -> bool:
        """Synthesize a left mouse click at relative coordinates within the window."""
        pass

    @abstractmethod
    def type_text(self, hwnd: int, text: str, element_id: Optional[str] = None) -> bool:
        """Send keyboard text sequence to the specified element or active window."""
        pass

    @abstractmethod
    def scroll(self, hwnd: int, amount: int) -> bool:
        """Synthesize vertical scroll input in the specified window."""
        pass
