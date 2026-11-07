"""Mock Desktop Adapter for headless testing and CI environments."""

import io
from typing import Optional

from backend.app.desktop.adapter import DesktopAdapter
from backend.app.desktop.models import UIElementNode, WindowRect, WindowSummary

# Minimal 1x1 transparent PNG bytes for headless simulation without Pillow dependency
DUMMY_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc`\x00\x00\x00"
    b"\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82"
)


class MockDesktopAdapter(DesktopAdapter):
    """Simulated desktop environment providing deterministic OS and UI responses."""

    def __init__(self) -> None:
        self.windows: dict[int, WindowSummary] = {
            1001: WindowSummary(
                hwnd=1001,
                pid=5001,
                process_name="notepad.exe",
                window_title="Untitled - Notepad",
                bounds=WindowRect(x=100, y=100, width=800, height=600),
            ),
            1002: WindowSummary(
                hwnd=1002,
                pid=5002,
                process_name="calc.exe",
                window_title="Calculator",
                bounds=WindowRect(x=200, y=200, width=400, height=500),
            ),
            9001: WindowSummary(
                hwnd=9001,
                pid=9001,
                process_name="1password.exe",
                window_title="1Password - Unlock Vault",
                bounds=WindowRect(x=300, y=300, width=450, height=350),
                is_shielded=True,
            ),
        }
        self.foreground_hwnd: int = 1001
        self.trees: dict[int, UIElementNode] = {}
        self.input_log: list[dict] = []
        self._init_default_trees()

    def _init_default_trees(self) -> None:
        """Seed realistic UI Automation trees for default mock windows."""
        # Notepad Tree
        text_editor = UIElementNode(
            element_id="elem_notepad_editor",
            automation_id="TextEditor",
            name="Text Editor",
            control_type="Edit",
            bounding_rect=WindowRect(x=110, y=140, width=780, height=520),
            is_enabled=True,
            is_password=False,
            value="",
            supported_patterns=["Value", "Text"],
        )
        menu_bar = UIElementNode(
            element_id="elem_notepad_menubar",
            automation_id="MenuBar",
            name="Application Menu",
            control_type="MenuBar",
            bounding_rect=WindowRect(x=100, y=100, width=800, height=30),
            is_enabled=True,
            supported_patterns=[],
        )
        self.trees[1001] = UIElementNode(
            element_id="elem_notepad_root",
            automation_id="NotepadWindow",
            name="Untitled - Notepad",
            control_type="Window",
            bounding_rect=WindowRect(x=100, y=100, width=800, height=600),
            is_enabled=True,
            children=[menu_bar, text_editor],
        )

        # 1Password Tree with password field
        pwd_box = UIElementNode(
            element_id="elem_1pwd_master",
            automation_id="MasterPasswordBox",
            name="Master Password",
            control_type="Edit",
            bounding_rect=WindowRect(x=350, y=400, width=350, height=40),
            is_enabled=True,
            is_password=True,
            value="super_secret_master_key",
            supported_patterns=["Value"],
        )
        self.trees[9001] = UIElementNode(
            element_id="elem_1pwd_root",
            automation_id="VaultWindow",
            name="1Password - Unlock Vault",
            control_type="Window",
            bounding_rect=WindowRect(x=300, y=300, width=450, height=350),
            is_enabled=True,
            children=[pwd_box],
        )

    def list_windows(self) -> list[WindowSummary]:
        return list(self.windows.values())

    def get_foreground_window(self) -> int:
        return self.foreground_hwnd

    def get_window_text(self, hwnd: int) -> str:
        win = self.windows.get(hwnd)
        return win.window_title if win else ""

    def get_window_rect(self, hwnd: int) -> WindowRect:
        win = self.windows.get(hwnd)
        return win.bounds if win else WindowRect()

    def set_foreground_window(self, hwnd: int) -> bool:
        if hwnd in self.windows:
            self.foreground_hwnd = hwnd
            return True
        return False

    def inspect_tree(self, hwnd: int, max_depth: int = 4) -> UIElementNode:
        if hwnd in self.trees:
            return self.trees[hwnd]
        win = self.windows.get(hwnd)
        title = win.window_title if win else f"Window {hwnd}"
        bounds = win.bounds if win else WindowRect()
        return UIElementNode(
            element_id=f"elem_root_{hwnd}",
            automation_id=f"AutoId_{hwnd}",
            name=title,
            control_type="Window",
            bounding_rect=bounds,
            is_enabled=True,
        )

    def capture_window(self, hwnd: int) -> tuple[bytes, int, int]:
        win = self.windows.get(hwnd)
        width = win.bounds.width if win else 800
        height = win.bounds.height if win else 600
        return DUMMY_PNG_BYTES, width, height

    def click_element(self, hwnd: int, element_id: str) -> bool:
        self.input_log.append({"action": "click_element", "hwnd": hwnd, "element_id": element_id})
        # Simulate click side-effect
        root = self.trees.get(hwnd)
        if root:
            node = self._find_node_by_id(root, element_id)
            if node:
                return True
        return True

    def click_coords(self, hwnd: int, rel_x: int, rel_y: int) -> bool:
        win = self.windows.get(hwnd)
        if not win or not win.bounds.contains(rel_x, rel_y):
            return False
        self.input_log.append({"action": "click_coords", "hwnd": hwnd, "x": rel_x, "y": rel_y})
        return True

    def type_text(self, hwnd: int, text: str, element_id: Optional[str] = None) -> bool:
        self.input_log.append({"action": "type_text", "hwnd": hwnd, "text": text, "element_id": element_id})
        # If targeting Notepad editor, append text to value
        root = self.trees.get(hwnd)
        if root and element_id:
            node = self._find_node_by_id(root, element_id)
            if node:
                node.value = (node.value or "") + text
        return True

    def scroll(self, hwnd: int, amount: int) -> bool:
        self.input_log.append({"action": "scroll", "hwnd": hwnd, "amount": amount})
        return True

    def _find_node_by_id(self, node: UIElementNode, element_id: str) -> Optional[UIElementNode]:
        if node.element_id == element_id:
            return node
        for child in node.children:
            res = self._find_node_by_id(child, element_id)
            if res:
                return res
        return None
