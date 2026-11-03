"""Tests for Windows Application Control & Process Supervisor (Milestone 3B)."""

import os
from pathlib import Path
import shutil
import sys
import pytest

from backend.app.core.config import get_settings
from backend.app.core.exceptions import (
    AppNotFoundException,
    ProcessNotFoundException,
    SystemProcessProtectedException,
)
from backend.app.models.agent import RiskLevel
from backend.app.services.app_service import AppService
from backend.app.tools.windows.app_close import AppCloseTool
from backend.app.tools.windows.app_find import AppFindTool
from backend.app.tools.windows.app_get_details import AppGetDetailsTool
from backend.app.tools.windows.app_get_running import AppGetRunningTool
from backend.app.tools.windows.app_launch import AppLaunchTool
from backend.app.tools.windows.app_list_installed import AppListInstalledTool


@pytest.fixture
def app_service():
    settings = get_settings()
    return AppService(settings=settings)


def test_list_installed_apps(app_service):
    """Verify application discovery scans registry and system utilities."""
    apps = app_service.list_installed_apps()
    assert isinstance(apps, list)
    assert len(apps) > 0

    first = apps[0]
    assert "name" in first
    assert "source" in first

    # Test in-memory caching
    apps_cached = app_service.list_installed_apps()
    assert len(apps_cached) == len(apps)


def test_find_app(app_service):
    """Test searching for installed applications."""
    # Empty query
    assert app_service.find_app("") == []
    assert app_service.find_app("   ") == []

    # Common built-in utility
    results = app_service.find_app("notepad")
    assert len(results) > 0
    assert any("notepad" in r["name"].lower() for r in results)

    # Completely non-existent app
    no_results = app_service.find_app("completely_nonexistent_app_xyz_12345")
    assert no_results == []


def test_resolve_executable(app_service):
    """Verify executable resolution and validation."""
    py_exe = sys.executable
    resolved = app_service.resolve_executable(py_exe)
    assert resolved == Path(py_exe).resolve()

    # Non-existent app raises AppNotFoundException
    with pytest.raises(AppNotFoundException):
        app_service.resolve_executable("non_existent_app_12345.exe")

    # Non-.exe file raises AppNotFoundException
    readme_path = Path("README.md").resolve()
    if not readme_path.exists():
        readme_path.touch()
    with pytest.raises(AppNotFoundException):
        app_service.resolve_executable(str(readme_path))


def test_app_launch_and_lifecycle(app_service):
    """Test launching a desktop process, tracking PID, inspecting details, and closing."""
    py_exe = sys.executable
    # Launch lightweight background process that sleeps
    res = app_service.launch_app(py_exe, arguments=["-c", "import time; time.sleep(15)"])
    pid = res["pid"]
    assert pid in app_service.launched_pids
    assert res["status"] == "launched"

    try:
        # Inspect process details
        details = app_service.get_process_details(pid)
        assert details["pid"] == pid
        assert details["is_managed"] is True
        assert details["is_protected"] is False
        assert details["memory_mb"] > 0
        assert details["uptime_seconds"] >= 0

        # Verify it appears in running processes
        running = app_service.get_running_processes(include_system=False, limit=1000)
        pids = [p["pid"] for p in running]
        assert pid in pids

        # Close process gracefully
        close_res = app_service.close_app(pid, force=False)
        assert close_res["status"] in ("closed", "terminated")
        assert pid not in app_service.launched_pids
    finally:
        # Ensure cleanup if test fails
        if pid in app_service.launched_pids:
            try:
                app_service.close_app(pid, force=True)
            except Exception:
                pass


def test_protected_system_process_rejection(app_service):
    """Verify that attempting to terminate protected system processes is blocked."""
    # Protected PID 0 or PID 4
    with pytest.raises(SystemProcessProtectedException):
        app_service.close_app(0)

    with pytest.raises(SystemProcessProtectedException):
        app_service.close_app(4)

    # Find explorer.exe PID if running
    running = app_service.get_running_processes(include_system=True)
    explorer = next((p for p in running if p["name"].lower() == "explorer.exe"), None)
    if explorer:
        with pytest.raises(SystemProcessProtectedException):
            app_service.close_app(explorer["pid"])


def test_process_not_found(app_service):
    """Test operations on non-existent PIDs."""
    invalid_pid = 99999999
    with pytest.raises(ProcessNotFoundException):
        app_service.get_process_details(invalid_pid)

    with pytest.raises(ProcessNotFoundException):
        app_service.close_app(invalid_pid)


@pytest.mark.asyncio
async def test_windows_tool_adapters(app_service):
    """Verify tool adapters execute and return structured output with correct risk levels."""
    list_tool = AppListInstalledTool(app_service)
    assert list_tool.risk_level == RiskLevel.SAFE
    list_out = await list_tool.execute()
    assert "applications" in list_out
    assert list_out["count"] > 0

    find_tool = AppFindTool(app_service)
    assert find_tool.risk_level == RiskLevel.SAFE
    find_out = await find_tool.execute(query="notepad")
    assert "matches" in find_out

    running_tool = AppGetRunningTool(app_service)
    assert running_tool.risk_level == RiskLevel.SAFE
    run_out = await running_tool.execute(limit=10)
    assert "processes" in run_out

    # Launch tool
    launch_tool = AppLaunchTool(app_service)
    assert launch_tool.risk_level == RiskLevel.CONTROLLED
    py_exe = sys.executable
    launch_out = await launch_tool.execute(app_name_or_path=py_exe, arguments=["-c", "import time; time.sleep(15)"])
    pid = launch_out["pid"]

    try:
        # Details tool
        details_tool = AppGetDetailsTool(app_service)
        assert details_tool.risk_level == RiskLevel.SAFE
        det_out = await details_tool.execute(pid=pid)
        assert det_out["pid"] == pid

        # Close tool
        close_tool = AppCloseTool(app_service)
        assert close_tool.risk_level == RiskLevel.SENSITIVE
        close_out = await close_tool.execute(pid=pid)
        assert close_out["pid"] == pid
    finally:
        if pid in app_service.launched_pids:
            try:
                app_service.close_app(pid, force=True)
            except Exception:
                pass
