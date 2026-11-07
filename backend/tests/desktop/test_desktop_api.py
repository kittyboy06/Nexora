"""Integration tests for Desktop Vision and Interaction REST API Endpoints (Milestone 6)."""

from pathlib import Path
import pytest
import pytest_asyncio
import httpx

from backend.app.desktop.mock_adapter import MockDesktopAdapter
from backend.app.desktop.models import DesktopActionType
from backend.app.desktop.service import DesktopService
from backend.app.main import create_app


@pytest_asyncio.fixture
async def desktop_api_client(tmp_path: Path):
    """Set up test client with isolated DesktopService and Mock adapter."""
    quarantine_dir = tmp_path / "quarantine"
    adapter = MockDesktopAdapter()
    service = DesktopService(
        quarantine_dir=quarantine_dir,
        adapter=adapter,
        settle_delay_sec=0.0,
    )

    app = create_app()
    app.state.desktop_service = service

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        yield client, service, adapter


@pytest.mark.asyncio
async def test_api_window_discovery_and_binding(desktop_api_client):
    """Verify listing windows and binding/releasing target sessions."""
    client, service, _ = desktop_api_client

    # 1. List windows
    resp = await client.get("/api/desktop/windows")
    assert resp.status_code == 200
    windows = resp.json()
    assert len(windows) >= 2
    assert not any(w["process_name"] == "1password.exe" for w in windows)

    # 2. Filter windows by query
    query_resp = await client.get("/api/desktop/windows?query=calc")
    assert query_resp.status_code == 200
    calc_windows = query_resp.json()
    assert len(calc_windows) == 1
    assert calc_windows[0]["hwnd"] == 1002

    # 3. Bind shielded window (HWND 9001) -> 403 Forbidden
    bad_bind = await client.post("/api/desktop/bind", json={"hwnd": 9001})
    assert bad_bind.status_code == 403
    err_body = bad_bind.json()
    err_msg = err_body.get("detail") or err_body.get("error", {}).get("message", "")
    assert "shielded from automation" in err_msg

    # 4. Bind nonexistent window -> 404 Not Found
    bad_hwnd = await client.post("/api/desktop/bind", json={"hwnd": 99999})
    assert bad_hwnd.status_code == 404

    # 5. Bind safe window (Notepad HWND 1001)
    bind_resp = await client.post("/api/desktop/bind", json={"hwnd": 1001})
    assert bind_resp.status_code == 200
    binding = bind_resp.json()
    assert binding["hwnd"] == 1001
    assert binding["process_name"] == "notepad.exe"

    # 6. Retrieve active binding
    get_binding = await client.get("/api/desktop/binding")
    assert get_binding.status_code == 200
    assert get_binding.json()["hwnd"] == 1001

    # 7. Release binding
    rel_resp = await client.post("/api/desktop/release")
    assert rel_resp.status_code == 200
    assert rel_resp.json()["released"] is True

    get_none = await client.get("/api/desktop/binding")
    assert get_none.json() is None


@pytest.mark.asyncio
async def test_api_tree_and_capture(desktop_api_client):
    """Verify tree inspection and window-bounded screenshot capture."""
    client, service, _ = desktop_api_client

    # Bind Notepad
    await client.post("/api/desktop/bind", json={"hwnd": 1001})

    # 1. Inspect tree
    tree_resp = await client.get("/api/desktop/tree")
    assert tree_resp.status_code == 200
    tree_data = tree_resp.json()
    assert tree_data["automation_id"] == "NotepadWindow"
    assert len(tree_data["children"]) >= 1

    # 2. Capture screenshot
    cap_resp = await client.post("/api/desktop/capture?task_id=task_api_test")
    assert cap_resp.status_code == 200
    cap_data = cap_resp.json()
    assert cap_data["image_id"].startswith("snap_")
    assert cap_data["is_redacted"] is False
    image_id = cap_data["image_id"]

    # 3. List evidence
    ev_resp = await client.get("/api/desktop/evidence?task_id=task_api_test")
    assert ev_resp.status_code == 200
    evidence_list = ev_resp.json()
    assert len(evidence_list) == 1
    assert evidence_list[0]["image_id"] == image_id

    # 4. Fetch raw image file
    file_resp = await client.get(f"/api/desktop/evidence/{image_id}/file")
    assert file_resp.status_code == 200
    assert file_resp.headers["content-type"] == "image/png"
    assert len(file_resp.content) > 0


@pytest.mark.asyncio
async def test_api_action_and_emergency_stop(desktop_api_client):
    """Verify executing desktop actions and halting via emergency stop."""
    client, service, _ = desktop_api_client

    # Bind Notepad
    bind_resp = await client.post("/api/desktop/bind", json={"hwnd": 1001})
    binding_data = bind_resp.json()

    # 1. Execute Type Text Action
    action_payload = {
        "binding": binding_data,
        "action_type": "type_text",
        "target_element_id": "elem_notepad_editor",
        "text_input": "API Test Note",
        "expected_postcondition": "text_contains:API Test Note",
    }
    act_resp = await client.post("/api/desktop/actions", json=action_payload)
    assert act_resp.status_code == 200
    act_data = act_resp.json()
    assert act_data["status"] == "SUCCESS"
    assert act_data["verification_ok"] is True

    # 2. Trigger Emergency Stop
    estop_resp = await client.post("/api/desktop/emergency-stop", json={"reason": "Operator halted automation"})
    assert estop_resp.status_code == 200
    assert estop_resp.json()["status"] == "STOPPED"
    assert service.is_emergency_stop_active() is True

    # 3. Attempting action while emergency stop is active returns CANCELLED
    blocked_resp = await client.post("/api/desktop/actions", json=action_payload)
    assert blocked_resp.status_code == 200
    assert blocked_resp.json()["status"] == "CANCELLED"
    assert "Emergency stop is active" in blocked_resp.json()["message"]

    # 4. Reset Emergency Stop
    reset_resp = await client.post("/api/desktop/emergency-stop/reset")
    assert reset_resp.status_code == 200
    assert reset_resp.json()["status"] == "ACTIVE"
    assert service.is_emergency_stop_active() is False
