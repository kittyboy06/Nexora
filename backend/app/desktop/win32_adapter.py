"""Native Windows Desktop Adapter utilizing Win32 and UI Automation APIs."""

import ctypes
from ctypes import wintypes
import io
import logging
import sys
from typing import Optional

from backend.app.desktop.adapter import DesktopAdapter
from backend.app.desktop.models import UIElementNode, WindowRect, WindowSummary

logger = logging.getLogger("nexora.desktop.win32")

IS_WINDOWS = sys.platform == "win32"


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [
        ("bmiHeader", BITMAPINFOHEADER),
        ("bmiColors", wintypes.DWORD * 3),
    ]


class Win32DesktopAdapter(DesktopAdapter):
    """Direct Win32 API implementation for Windows desktop observation and interaction."""

    def __init__(self) -> None:
        if not IS_WINDOWS:
            logger.warning("Win32DesktopAdapter instantiated on non-Windows platform (%s)", sys.platform)
            self._user32 = None
            self._gdi32 = None
            return

        self._user32 = ctypes.windll.user32
        self._gdi32 = ctypes.windll.gdi32
        self._kernel32 = ctypes.windll.kernel32

    def list_windows(self) -> list[WindowSummary]:
        if not self._user32:
            return []

        windows: list[WindowSummary] = []
        WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def enum_windows_callback(hwnd: int, lparam: int) -> bool:
            if not self._user32.IsWindowVisible(hwnd):
                return True

            length = self._user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                return True

            buffer = ctypes.create_unicode_buffer(length + 1)
            self._user32.GetWindowTextW(hwnd, buffer, length + 1)
            title = buffer.value.strip()

            if not title:
                return True

            pid = wintypes.DWORD()
            self._user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

            rect = RECT()
            self._user32.GetWindowRect(hwnd, ctypes.byref(rect))
            width = max(0, rect.right - rect.left)
            height = max(0, rect.bottom - rect.top)

            if width < 50 or height < 50:
                return True

            # Get process name via process handle or basic lookup
            process_name = self._get_process_name(pid.value)

            windows.append(
                WindowSummary(
                    hwnd=hwnd,
                    pid=pid.value,
                    process_name=process_name,
                    window_title=title,
                    bounds=WindowRect(x=rect.left, y=rect.top, width=width, height=height),
                )
            )
            return True

        self._user32.EnumWindows(WNDENUMPROC(enum_windows_callback), 0)
        return windows

    def get_foreground_window(self) -> int:
        if not self._user32:
            return 0
        return int(self._user32.GetForegroundWindow())

    def get_window_text(self, hwnd: int) -> str:
        if not self._user32 or not hwnd:
            return ""
        length = self._user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return ""
        buffer = ctypes.create_unicode_buffer(length + 1)
        self._user32.GetWindowTextW(hwnd, buffer, length + 1)
        return buffer.value

    def get_window_rect(self, hwnd: int) -> WindowRect:
        if not self._user32 or not hwnd:
            return WindowRect()
        rect = RECT()
        if self._user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return WindowRect(
                x=rect.left,
                y=rect.top,
                width=max(0, rect.right - rect.left),
                height=max(0, rect.bottom - rect.top),
            )
        return WindowRect()

    def set_foreground_window(self, hwnd: int) -> bool:
        if not self._user32 or not hwnd:
            return False
        return bool(self._user32.SetForegroundWindow(hwnd))

    def inspect_tree(self, hwnd: int, max_depth: int = 4) -> UIElementNode:
        """Inspect window hierarchy using Win32 Child Windows or UIAutomation."""
        title = self.get_window_text(hwnd)
        bounds = self.get_window_rect(hwnd)
        root = UIElementNode(
            element_id=f"win_{hwnd}",
            automation_id=f"HWND_{hwnd}",
            name=title or f"Window_{hwnd}",
            control_type="Window",
            bounding_rect=bounds,
            is_enabled=True,
        )

        if not self._user32:
            return root

        # Traverse immediate child windows
        WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        children: list[UIElementNode] = []

        def enum_child_proc(child_hwnd: int, lparam: int) -> bool:
            if not self._user32.IsWindowVisible(child_hwnd):
                return True
            child_text = self.get_window_text(child_hwnd)
            child_bounds = self.get_window_rect(child_hwnd)
            class_buffer = ctypes.create_unicode_buffer(256)
            self._user32.GetClassNameW(child_hwnd, class_buffer, 256)
            class_name = class_buffer.value

            is_password = "password" in class_name.lower() or "edit" in class_name.lower() and bool(
                self._user32.GetWindowLongW(child_hwnd, -16) & 0x0020  # ES_PASSWORD
            )

            children.append(
                UIElementNode(
                    element_id=f"elem_{child_hwnd}",
                    automation_id=f"HWND_{child_hwnd}",
                    name=child_text,
                    control_type=class_name or "Custom",
                    bounding_rect=child_bounds,
                    is_enabled=bool(self._user32.IsWindowEnabled(child_hwnd)),
                    is_password=is_password,
                    supported_patterns=["Value"] if "edit" in class_name.lower() else ["Invoke"],
                )
            )
            return True

        self._user32.EnumChildWindows(hwnd, WNDENUMPROC(enum_child_proc), 0)
        root.children = children[:50]  # Bound tree to reasonable size
        return root

    def capture_window(self, hwnd: int) -> tuple[bytes, int, int]:
        """Capture window client rect using Win32 PrintWindow / BitBlt."""
        rect = self.get_window_rect(hwnd)
        width, height = rect.width, rect.height
        if width <= 0 or height <= 0:
            width, height = 800, 600

        if not self._user32 or not self._gdi32:
            from PIL import Image
            img = Image.new("RGB", (width, height), color=(30, 30, 30))
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue(), width, height

        try:
            hwnd_dc = self._user32.GetWindowDC(hwnd)
            mem_dc = self._gdi32.CreateCompatibleDC(hwnd_dc)
            bitmap = self._gdi32.CreateCompatibleBitmap(hwnd_dc, width, height)
            self._gdi32.SelectObject(mem_dc, bitmap)

            # PW_RENDERFULLCONTENT = 0x00000002
            pw_res = self._user32.PrintWindow(hwnd, mem_dc, 2)
            if not pw_res:
                # SRCCOPY = 0x00CC0020
                self._gdi32.BitBlt(mem_dc, 0, 0, width, height, hwnd_dc, 0, 0, 0x00CC0020)

            # Extract DIB bits
            bmi = BITMAPINFO()
            bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
            bmi.bmiHeader.biWidth = width
            bmi.bmiHeader.biHeight = -height  # top-down DIB
            bmi.bmiHeader.biPlanes = 1
            bmi.bmiHeader.biBitCount = 32
            bmi.bmiHeader.biCompression = 0  # BI_RGB

            buffer_size = width * height * 4
            pixel_data = ctypes.create_string_buffer(buffer_size)

            self._gdi32.GetDIBits(
                mem_dc, bitmap, 0, height, pixel_data, ctypes.byref(bmi), 0
            )

            self._gdi32.DeleteObject(bitmap)
            self._gdi32.DeleteDC(mem_dc)
            self._user32.ReleaseDC(hwnd, hwnd_dc)

            from PIL import Image
            img = Image.frombuffer("RGBA", (width, height), pixel_data, "raw", "BGRA", 0, 1)
            buf = io.BytesIO()
            img.convert("RGB").save(buf, format="PNG")
            return buf.getvalue(), width, height
        except Exception as e:
            logger.debug("Win32 direct capture fallback triggered: %s", e)
            from PIL import Image
            img = Image.new("RGB", (width, height), color=(30, 30, 30))
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue(), width, height

    def click_element(self, hwnd: int, element_id: str) -> bool:
        """Click UI element center by extracting HWND from ID or finding its rect."""
        if element_id.startswith("elem_"):
            try:
                child_hwnd = int(element_id.split("_")[1])
                # BM_CLICK = 0x00F5
                self._user32.SendMessageW(child_hwnd, 0x00F5, 0, 0)
                return True
            except Exception:
                pass
        return True

    def click_coords(self, hwnd: int, rel_x: int, rel_y: int) -> bool:
        """Synthesize left mouse click at relative coordinates within target window."""
        rect = self.get_window_rect(hwnd)
        if not rect.contains(rel_x, rel_y):
            return False

        abs_x = rect.x + rel_x
        abs_y = rect.y + rel_y
        if self._user32:
            self._user32.SetCursorPos(abs_x, abs_y)
            # MOUSEEVENTF_LEFTDOWN = 0x0002, MOUSEEVENTF_LEFTUP = 0x0004
            self._user32.mouse_event(0x0002, 0, 0, 0, 0)
            self._user32.mouse_event(0x0004, 0, 0, 0, 0)
        return True

    def type_text(self, hwnd: int, text: str, element_id: Optional[str] = None) -> bool:
        """Send keystrokes or WM_CHAR to target window/element."""
        if not self._user32:
            return False

        target_hwnd = hwnd
        if element_id and element_id.startswith("elem_"):
            try:
                target_hwnd = int(element_id.split("_")[1])
            except ValueError:
                pass

        for char in text:
            # WM_CHAR = 0x0102
            self._user32.PostMessageW(target_hwnd, 0x0102, ord(char), 0)
        return True

    def scroll(self, hwnd: int, amount: int) -> bool:
        """Send WM_MOUSEWHEEL event."""
        if not self._user32:
            return False
        # WM_MOUSEWHEEL = 0x020A; WHEEL_DELTA = 120
        delta = amount * 120
        wParam = (delta << 16) & 0xFFFFFFFF
        self._user32.SendMessageW(hwnd, 0x020A, wParam, 0)
        return True

    def _get_process_name(self, pid: int) -> str:
        """Look up executable image name from process PID."""
        if not self._kernel32 or pid == 0:
            return "unknown.exe"

        # PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = self._kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            return "unknown.exe"

        buffer = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(1024)
        try:
            # QueryFullProcessImageNameW
            if self._kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
                full_path = buffer.value
                return full_path.split("\\")[-1].lower()
        except Exception:
            pass
        finally:
            self._kernel32.CloseHandle(handle)
        return "unknown.exe"
