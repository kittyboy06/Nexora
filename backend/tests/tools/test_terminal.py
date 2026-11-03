"""Tests for Controlled Terminal Intelligence (Milestone 3C)."""

from pathlib import Path
import sys
import pytest

from backend.app.core.config import get_settings
from backend.app.core.exceptions import (
    CommandExecutionTimeoutException,
    CommandNotAllowedException,
    PathTraversalException,
)
from backend.app.models.agent import RiskLevel
from backend.app.services.terminal_service import TerminalService
from backend.app.tools.terminal.terminal_get_directory import TerminalGetDirectoryTool
from backend.app.tools.terminal.terminal_get_system_info import TerminalGetSystemInfoTool
from backend.app.tools.terminal.terminal_install_package import TerminalInstallPackageTool
from backend.app.tools.terminal.terminal_run_allowlisted import TerminalRunAllowlistedTool
from backend.app.tools.terminal.terminal_run_script import TerminalRunScriptTool


@pytest.fixture
def terminal_service(tmp_path):
    settings = get_settings()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return TerminalService(settings=settings, workspace_root=workspace)


def test_get_system_info(terminal_service):
    """Verify system info returns required host metrics without shell execution."""
    info = terminal_service.get_system_info()
    assert "os_name" in info
    assert "ram_total_mb" in info
    assert "uptime_seconds" in info
    assert info["ram_total_mb"] > 0
    assert info["uptime_seconds"] >= 0


def test_get_directory_info(terminal_service):
    """Verify directory info returns cwd and workspace jail."""
    dir_info = terminal_service.get_directory_info()
    assert "current_working_directory" in dir_info
    assert "workspace_directory" in dir_info
    assert dir_info["workspace_directory"] == str(terminal_service.workspace_root)


def test_redact_secrets(terminal_service):
    """Verify sensitive tokens and credentials are masked in command output."""
    raw = "Connected with api_key=sk-abc1234567890xyz and Authorization: Bearer token99887766554433"
    redacted = terminal_service.redact_secrets(raw)
    assert "sk-abc1234567890xyz" not in redacted
    assert "token99887766554433" not in redacted
    assert "[REDACTED]" in redacted


@pytest.mark.asyncio
async def test_execute_command_allowlist_enforcement(terminal_service):
    """Verify allowlist blocks unauthorized binaries and elevation commands."""
    # Disallowed binary
    with pytest.raises(CommandNotAllowedException) as exc:
        await terminal_service.execute_command("powershell", ["-Command", "dir"])
    assert "not in the allowed terminal commands allowlist" in str(exc.value)

    # Elevation command
    with pytest.raises(CommandNotAllowedException) as exc:
        await terminal_service.execute_command("runas", ["/user:Administrator", "cmd"])
    assert "elevation commands" in str(exc.value).lower()

    # Elevation in arguments
    with pytest.raises(CommandNotAllowedException) as exc:
        await terminal_service.execute_command("python", ["sudo", "script.py"])
    assert "elevation arguments" in str(exc.value).lower()


@pytest.mark.asyncio
async def test_execute_command_success(terminal_service):
    """Verify execution of allowlisted Python command in sandbox."""
    res = await terminal_service.execute_command("python", ["-c", "print('hello nexora')"])
    assert res["exit_code"] == 0
    assert "hello nexora" in res["stdout"]
    assert res["truncated"] is False
    assert res["duration_ms"] > 0


@pytest.mark.asyncio
async def test_execute_command_timeout(terminal_service):
    """Verify execution aborts and terminates process on timeout."""
    with pytest.raises(CommandExecutionTimeoutException):
        await terminal_service.execute_command(
            "python",
            ["-c", "import time; time.sleep(3)"],
            timeout=0.3,
        )


@pytest.mark.asyncio
async def test_execute_command_truncation(terminal_service):
    """Verify stdout exceeding byte threshold is truncated."""
    # Output 70,000 characters (exceeds 51,200 threshold)
    res = await terminal_service.execute_command("python", ["-c", "print('A' * 70000)"])
    assert res["exit_code"] == 0
    assert res["truncated"] is True
    assert "[...OUTPUT TRUNCATED BY NEXORA...]" in res["stdout"]


@pytest.mark.asyncio
async def test_run_script_lifecycle_and_security(terminal_service):
    """Test executing a Python script in workspace and verify path jail."""
    # 1. Create a script in workspace
    script_file = terminal_service.workspace_root / "hello.py"
    script_file.write_text("import sys\nprint('Script arg:', sys.argv[1] if len(sys.argv) > 1 else 'none')")

    res = await terminal_service.run_script("hello.py", args=["test1234"])
    assert res["exit_code"] == 0
    assert "Script arg: test1234" in res["stdout"]

    # 2. Non-existent script
    with pytest.raises(FileNotFoundError):
        await terminal_service.run_script("non_existent.py")

    # 3. Non-.py script rejected
    txt_file = terminal_service.workspace_root / "test.txt"
    txt_file.write_text("hello")
    with pytest.raises(CommandNotAllowedException):
        await terminal_service.run_script("test.txt")

    # 4. Path traversal escape rejected
    with pytest.raises(PathTraversalException):
        await terminal_service.run_script("../../escape.py")


@pytest.mark.asyncio
async def test_install_package_validation(terminal_service):
    """Verify package name validation and command construction."""
    # Unsupported manager
    with pytest.raises(CommandNotAllowedException):
        await terminal_service.install_package("requests", manager="apt")

    # Unsafe flag injection
    with pytest.raises(CommandNotAllowedException):
        await terminal_service.install_package("-r requirements.txt", manager="pip")

    with pytest.raises(CommandNotAllowedException):
        await terminal_service.install_package("requests; rm -rf /", manager="pip")


@pytest.mark.asyncio
async def test_terminal_tool_adapters(terminal_service):
    """Verify tool adapter properties, risk levels, and execution."""
    sys_tool = TerminalGetSystemInfoTool(terminal_service)
    assert sys_tool.risk_level == RiskLevel.SAFE
    sys_out = await sys_tool.execute()
    assert "os_name" in sys_out

    dir_tool = TerminalGetDirectoryTool(terminal_service)
    assert dir_tool.risk_level == RiskLevel.SAFE
    dir_out = await dir_tool.execute()
    assert "workspace_directory" in dir_out

    run_tool = TerminalRunAllowlistedTool(terminal_service)
    assert run_tool.risk_level == RiskLevel.CONTROLLED
    run_out = await run_tool.execute(command="python", args=["-c", "print('test allowlist')"])
    assert "test allowlist" in run_out["stdout"]

    script_tool = TerminalRunScriptTool(terminal_service)
    assert script_tool.risk_level == RiskLevel.CONTROLLED
    test_script = terminal_service.workspace_root / "test_run.py"
    test_script.write_text("print('script tool ok')")
    script_out = await script_tool.execute(script_path="test_run.py")
    assert "script tool ok" in script_out["stdout"]

    pkg_tool = TerminalInstallPackageTool(terminal_service)
    assert pkg_tool.risk_level == RiskLevel.SENSITIVE
