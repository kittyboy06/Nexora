"""Terminal tools package."""

from backend.app.services.terminal_service import TerminalService
from backend.app.tools.registry import ToolRegistry
from backend.app.tools.terminal.terminal_get_directory import TerminalGetDirectoryTool
from backend.app.tools.terminal.terminal_get_system_info import TerminalGetSystemInfoTool
from backend.app.tools.terminal.terminal_install_package import TerminalInstallPackageTool
from backend.app.tools.terminal.terminal_run_allowlisted import TerminalRunAllowlistedTool
from backend.app.tools.terminal.terminal_run_script import TerminalRunScriptTool


def register_terminal_tools(registry: ToolRegistry, service: TerminalService) -> None:
    """Register all 5 terminal tools in the registry."""
    registry.register(TerminalGetSystemInfoTool(service))
    registry.register(TerminalGetDirectoryTool(service))
    registry.register(TerminalRunAllowlistedTool(service))
    registry.register(TerminalRunScriptTool(service))
    registry.register(TerminalInstallPackageTool(service))
