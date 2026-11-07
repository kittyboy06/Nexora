"""End-to-End lifecycle tests for Phase 12: Desktop Vision and Interaction Platform."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest
import pytest_asyncio
import httpx

from backend.tests.fixtures.desktop_mock_adapter import MockDesktopAdapter
from backend.app.desktop.models import DesktopActionType, UIElementNode, WindowRect
from backend.app.desktop.service import DesktopService
from backend.app.desktop.tools import register_desktop_tools
from backend.app.main import create_app
from backend.app.tools.registry import ToolRegistry


@pytest_asyncio.fixture
async def desktop_e2e_env(tmp_path: Path):
    """Set up full Phase 12 test environment with isolated quarantine and mock adapter."""
    quarantine_dir = tmp_path / "quarantine"
    adapter = MockDesktopAdapter()
    service = DesktopService(
        quarantine_dir=quarantine_dir,
        adapter=adapter,
        settle_delay_sec=0.0,
    )

    registry = ToolRegistry()
    register_desktop_tools(
        tool_registry=registry,
        session_manager=service.session_manager,
        tree_inspector=service.tree_inspector,
        capture_broker=service.capture_broker,
        executor=service.executor,
        emergency_manager=service.emergency_manager,
    )

    app = create_app()
    app.state.desktop_service = service
    app.state.tool_registry = registry

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        yield {
            "client": client,
            "service": service,
            "adapter": adapter,
            "registry": registry,
            "quarantine_dir": quarantine_dir,
        }


@pytest.mark.asyncio
async def test_full_desktop_automation_lifecycle_e2e(desktop_e2e_env):
    """Verify complete end-to-end desktop discovery, shielding, capture, actions, focus checks, and emergency stop."""
    client: httpx.AsyncClient = desktop_e2e_env["client"]
    service: DesktopService = desktop_e2e_env["service"]
    adapter: MockDesktopAdapter = desktop_e2e_env["adapter"]
    registry: ToolRegistry = desktop_e2e_env["registry"]

    # 1. Window Discovery excludes shielded security processes by default
    win_resp = await client.get("/api/desktop/windows")
    assert win_resp.status_code == 200
    windows = win_resp.json()
    assert len(windows) >= 2
    assert not any(w["process_name"] == "1password.exe" for w in windows)

    # 2. Attempting to bind a shielded window is rejected fail-closed
    shield_resp = await client.post("/api/desktop/bind", json={"hwnd": 9001})
    assert shield_resp.status_code == 403
    err_body = shield_resp.json()
    err_msg = err_body.get("detail") or err_body.get("error", {}).get("message", "")
    assert "shielded from automation" in err_msg

    # 3. Agent binds safe target application (Notepad HWND 1001)
    bind_resp = await client.post("/api/desktop/bind", json={"hwnd": 1001})
    assert bind_resp.status_code == 200
    binding = bind_resp.json()
    assert binding["hwnd"] == 1001
    assert binding["process_name"] == "notepad.exe"

    # 4. Agent inspects accessibility UI tree
    tree_resp = await client.get("/api/desktop/tree")
    assert tree_resp.status_code == 200
    tree_data = tree_resp.json()
    assert tree_data["automation_id"] == "NotepadWindow"
    assert any(c["automation_id"] == "TextEditor" for c in tree_data["children"])

    # 5. Agent captures window-bounded screenshot evidence
    cap_resp = await client.post("/api/desktop/capture?task_id=task_e2e_101")
    assert cap_resp.status_code == 200
    evidence = cap_resp.json()
    assert evidence["image_id"].startswith("snap_")
    assert evidence["is_redacted"] is False
    assert Path(evidence["file_path"]).exists()

    # 6. Agent executes mutating action: TYPE_TEXT with postcondition verification
    action_payload = {
        "binding": binding,
        "action_type": "type_text",
        "target_element_id": "elem_notepad_editor",
        "text_input": "Verified End-to-End Execution",
        "expected_postcondition": "text_contains:Verified End-to-End Execution",
    }
    act_resp = await client.post("/api/desktop/actions?task_id=task_e2e_101", json=action_payload)
    assert act_resp.status_code == 200
    act_data = act_resp.json()
    assert act_data["status"] == "SUCCESS"
    assert act_data["verification_ok"] is True
    assert act_data["pre_action_screenshot_id"] is not None
    assert act_data["post_action_screenshot_id"] is not None

    # Verify text was injected into editor
    live_tree = adapter.inspect_tree(1001)
    editor_node = next(c for c in live_tree.children if c.control_type == "Edit")
    assert "Verified End-to-End Execution" in editor_node.value

    # 7. Fail-Closed Focus Guard: foreground shift aborts with UNCERTAIN before input sent
    adapter.set_foreground_window(1002)  # Focus shifted to Calculator
    focus_loss_payload = {
        "binding": binding,
        "action_type": "type_text",
        "target_element_id": "elem_notepad_editor",
        "text_input": "This should never be typed",
    }
    focus_loss_resp = await client.post("/api/desktop/actions", json=focus_loss_payload)
    assert focus_loss_resp.status_code == 200
    fl_data = focus_loss_resp.json()
    assert fl_data["status"] == "UNCERTAIN"
    assert fl_data["verification_ok"] is False
    assert "Focus lost" in fl_data["message"]
    # Confirm text was NOT typed
    assert "This should never be typed" not in editor_node.value

    # Restore foreground focus
    adapter.set_foreground_window(1001)

    # 8. Bounds Violation: click outside target window rect fails closed
    out_of_bounds_payload = {
        "binding": binding,
        "action_type": "click",
        "relative_coords": [1200, 950],  # Beyond 800x600 window
    }
    oob_resp = await client.post("/api/desktop/actions", json=out_of_bounds_payload)
    assert oob_resp.status_code == 200
    oob_data = oob_resp.json()
    assert oob_data["status"] == "UNCERTAIN"
    assert "Bounds violation" in oob_data["message"]

    # 9. Global Emergency Stop: instant halt blocks in-flight and queued actions
    estop_resp = await client.post("/api/desktop/emergency-stop", json={"reason": "Operator Emergency Killswitch"})
    assert estop_resp.status_code == 200
    assert estop_resp.json()["status"] == "STOPPED"
    assert service.is_emergency_stop_active() is True

    # Any subsequent action returns CANCELLED
    blocked_resp = await client.post("/api/desktop/actions", json=action_payload)
    assert blocked_resp.status_code == 200
    assert blocked_resp.json()["status"] == "CANCELLED"
    assert "Emergency stop is active" in blocked_resp.json()["message"]

    # Reset Emergency Stop
    reset_resp = await client.post("/api/desktop/emergency-stop/reset")
    assert reset_resp.status_code == 200
    assert reset_resp.json()["status"] == "ACTIVE"
    assert service.is_emergency_stop_active() is False

    # 10. Evidence Query and Image Download
    ev_list_resp = await client.get("/api/desktop/evidence?task_id=task_e2e_101")
    assert ev_list_resp.status_code == 200
    records = ev_list_resp.json()
    assert len(records) >= 3  # Pre-action, post-action, explicit capture

    sample_id = records[0]["image_id"]
    img_file_resp = await client.get(f"/api/desktop/evidence/{sample_id}/file")
    assert img_file_resp.status_code == 200
    assert img_file_resp.headers["content-type"] == "image/png"
    assert len(img_file_resp.content) > 0

    # 11. 24-Hour Quarantine Expiry Cleanup
    future_time = datetime.now(timezone.utc) + timedelta(hours=25)
    purged_count = service.capture_broker.cleanup_expired(now=future_time)
    assert purged_count >= 3
    assert len(service.list_evidence()) == 0
