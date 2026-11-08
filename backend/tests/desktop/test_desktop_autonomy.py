"""Unit tests for Phase 15 Autonomous Desktop Loop, Budgets, and Fail-Closed Guardrails."""

from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend.app.desktop.autonomy import AutonomousSessionController
from backend.app.desktop.models import (
    AutonomousSessionConfig,
    DesktopActionRequest,
    DesktopActionType,
    TargetWindowBinding,
    WindowRect,
)
from backend.app.desktop.service import DesktopService
from backend.app.main import create_app
from backend.tests.fixtures.desktop_mock_adapter import MockDesktopAdapter


@pytest.fixture
def temp_quarantine_dir(tmp_path: Path):
    d = tmp_path / "quarantine"
    d.mkdir(parents=True, exist_ok=True)
    return d


@pytest.fixture
def mock_adapter():
    return MockDesktopAdapter()


@pytest.fixture
def desktop_service(mock_adapter: MockDesktopAdapter, temp_quarantine_dir: Path):
    return DesktopService(
        quarantine_dir=temp_quarantine_dir,
        adapter=mock_adapter,
        settle_delay_sec=0.0,
    )


@pytest.fixture
def autonomy_controller(desktop_service: DesktopService):
    return AutonomousSessionController(desktop_service=desktop_service)


def test_start_session_validates_and_initializes(autonomy_controller: AutonomousSessionController):
    config = AutonomousSessionConfig(
        session_id="sess_01",
        goal="Automate notepad text typing",
        allowed_hwnds=[1001],
        max_actions=5,
        max_duration_seconds=300.0,
    )

    state = autonomy_controller.start_session(config)
    assert state.session_id == "sess_01"
    assert state.status == "RUNNING"
    assert state.action_count == 0
    assert state.max_actions == 5


def test_action_budget_enforcement(autonomy_controller: AutonomousSessionController):
    import asyncio

    config = AutonomousSessionConfig(
        session_id="sess_budget",
        goal="Two-step task",
        allowed_hwnds=[1001],
        max_actions=2,
        max_duration_seconds=600.0,
    )
    autonomy_controller.start_session(config)

    # Step 1
    res1 = asyncio.run(autonomy_controller.execute_step("sess_budget"))
    assert res1.step_number == 1
    assert res1.is_terminal is False

    # Step 2 (reaches budget)
    res2 = asyncio.run(autonomy_controller.execute_step("sess_budget"))
    assert res2.step_number == 2
    assert res2.is_terminal is True
    assert res2.terminal_reason == "BUDGET_ACTIONS_EXHAUSTED"
    assert res2.session_state.status == "EXHAUSTED"

    # Step 3 (already exhausted)
    res3 = asyncio.run(autonomy_controller.execute_step("sess_budget"))
    assert res3.is_terminal is True


def test_emergency_stop_halts_autonomy_loop(
    autonomy_controller: AutonomousSessionController,
    desktop_service: DesktopService,
):
    import asyncio

    config = AutonomousSessionConfig(
        session_id="sess_estop",
        goal="Run safely",
        allowed_hwnds=[1001],
        max_actions=10,
    )
    autonomy_controller.start_session(config)

    # Trigger emergency stop
    desktop_service.emergency_manager.trigger_stop("Operator emergency button")

    res = asyncio.run(autonomy_controller.execute_step("sess_estop"))
    assert res.is_terminal is True
    assert res.terminal_reason == "EMERGENCY_STOPPED"
    assert res.session_state.status == "EMERGENCY_STOPPED"


def test_focus_guard_pauses_when_window_shifts(
    autonomy_controller: AutonomousSessionController,
    mock_adapter: MockDesktopAdapter,
):
    import asyncio

    config = AutonomousSessionConfig(
        session_id="sess_focus",
        goal="Strict focus task",
        allowed_hwnds=[1001],  # Only notepad allowed
        max_actions=10,
    )
    autonomy_controller.start_session(config)

    # Shift foreground to calculator (1002) and disable refocus in mock
    mock_adapter.foreground_hwnd = 1002
    # Override set_foreground_window to simulate another window refusing focus
    mock_adapter.set_foreground_window = lambda h: None

    res = asyncio.run(autonomy_controller.execute_step("sess_focus"))
    assert res.session_state.status == "PAUSED"
    assert res.terminal_reason == "FOCUS_LOST"
    assert "outside allowed targets" in (res.session_state.last_action_message or "")


def test_api_desktop_autonomy_endpoints(temp_quarantine_dir: Path, mock_adapter: MockDesktopAdapter):
    app = create_app()
    service = DesktopService(quarantine_dir=temp_quarantine_dir, adapter=mock_adapter, settle_delay_sec=0.0)
    app.state.desktop_service = service

    client = TestClient(app)

    # 1. Start session
    start_resp = client.post(
        "/api/desktop/autonomy/start",
        json={
            "session_id": "api_sess_1",
            "goal": "Test API autonomy loop",
            "allowed_hwnds": [1001],
            "max_actions": 3,
            "max_duration_seconds": 300.0,
        },
    )
    assert start_resp.status_code == 200
    state = start_resp.json()
    assert state["session_id"] == "api_sess_1"
    assert state["status"] == "RUNNING"

    # 2. Step session
    step_resp = client.post("/api/desktop/autonomy/api_sess_1/step")
    assert step_resp.status_code == 200
    step_data = step_resp.json()
    assert step_data["step_number"] == 1
    assert step_data["is_terminal"] is False

    # 3. Pause session
    pause_resp = client.post("/api/desktop/autonomy/api_sess_1/pause")
    assert pause_resp.status_code == 200
    assert pause_resp.json()["status"] == "PAUSED"

    # 4. Resume session
    resume_resp = client.post("/api/desktop/autonomy/api_sess_1/resume")
    assert resume_resp.status_code == 200
    assert resume_resp.json()["status"] == "RUNNING"

    # 5. Stop session
    stop_resp = client.post("/api/desktop/autonomy/api_sess_1/stop")
    assert stop_resp.status_code == 200
    assert stop_resp.json()["status"] == "STOPPED"
