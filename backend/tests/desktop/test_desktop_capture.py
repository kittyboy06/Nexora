"""Unit tests for Capture Broker, Visual Redaction and Evidence Quarantine (Milestone 3)."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest
from PIL import Image

from backend.app.desktop.capture import CaptureBroker
from backend.app.desktop.mock_adapter import MockDesktopAdapter
from backend.app.desktop.models import TargetWindowBinding, UIElementNode, WindowRect


def test_capture_and_redact_safe_window(tmp_path: Path):
    """Verify normal window capture produces unredacted evidence."""
    adapter = MockDesktopAdapter()
    broker = CaptureBroker(adapter, storage_dir=tmp_path / "quarantine")

    binding = TargetWindowBinding(
        hwnd=1001,
        pid=5001,
        process_name="notepad.exe",
        window_title="Untitled - Notepad",
        bounds=WindowRect(x=100, y=100, width=800, height=600),
    )

    evidence = broker.capture_and_redact(binding, task_id="task_101")
    assert evidence.image_id.startswith("snap_")
    assert evidence.is_redacted is False
    assert Path(evidence.file_path).exists()
    assert len(evidence.sha256_hash) == 64

    # Verify Pillow can open the saved file
    with Image.open(evidence.file_path) as img:
        assert img.width == 800
        assert img.height == 600


def test_capture_and_redact_password_box(tmp_path: Path):
    """Verify password elements in tree trigger visual blackout and is_redacted flag."""
    adapter = MockDesktopAdapter()
    broker = CaptureBroker(adapter, storage_dir=tmp_path / "quarantine")

    # Add a custom mock window with a password input box
    adapter.windows[2001] = adapter.windows[1001].model_copy(
        update={"hwnd": 2001, "window_title": "Login Dialog", "bounds": WindowRect(x=50, y=50, width=500, height=400)}
    )
    pwd_node = UIElementNode(
        element_id="elem_pwd_login",
        automation_id="PasswordInput",
        name="User Password",
        control_type="Edit",
        bounding_rect=WindowRect(x=80, y=100, width=300, height=35),
        is_password=True,
    )
    adapter.trees[2001] = UIElementNode(
        element_id="elem_login_root",
        automation_id="LoginWin",
        name="Login Dialog",
        control_type="Window",
        bounding_rect=WindowRect(x=50, y=50, width=500, height=400),
        children=[pwd_node],
    )

    binding = TargetWindowBinding(
        hwnd=2001,
        pid=5001,
        process_name="app.exe",
        window_title="Login Dialog",
        bounds=WindowRect(x=50, y=50, width=500, height=400),
    )

    evidence = broker.capture_and_redact(binding, task_id="task_102")
    assert evidence.is_redacted is True

    # Check evidence listing
    task_ev = broker.list_evidence("task_102")
    assert len(task_ev) == 1
    assert task_ev[0].image_id == evidence.image_id


def test_cleanup_expired_evidence(tmp_path: Path):
    """Verify expired screenshots are purged from disk and catalogue."""
    adapter = MockDesktopAdapter()
    broker = CaptureBroker(adapter, storage_dir=tmp_path / "quarantine")

    binding = TargetWindowBinding(
        hwnd=1001,
        pid=5001,
        process_name="notepad.exe",
        window_title="Untitled - Notepad",
        bounds=WindowRect(x=100, y=100, width=800, height=600),
    )

    evidence = broker.capture_and_redact(binding, task_id="task_103")
    file_path = Path(evidence.file_path)
    assert file_path.exists()

    # Fast-forward 25 hours into the future
    future_time = datetime.now(timezone.utc) + timedelta(hours=25)
    purged = broker.cleanup_expired(now=future_time)
    assert purged == 1
    assert not file_path.exists()
    assert len(broker.list_evidence()) == 0
