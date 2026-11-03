"""Windows application control tools package."""

from backend.app.services.app_service import AppService
from backend.app.tools.registry import ToolRegistry
from backend.app.tools.windows.app_close import AppCloseTool
from backend.app.tools.windows.app_find import AppFindTool
from backend.app.tools.windows.app_get_details import AppGetDetailsTool
from backend.app.tools.windows.app_get_running import AppGetRunningTool
from backend.app.tools.windows.app_launch import AppLaunchTool
from backend.app.tools.windows.app_list_installed import AppListInstalledTool


def register_windows_tools(registry: ToolRegistry, service: AppService) -> None:
    """Register all 6 Windows application control tools in the registry."""
    registry.register(AppListInstalledTool(service))
    registry.register(AppFindTool(service))
    registry.register(AppLaunchTool(service))
    registry.register(AppGetRunningTool(service))
    registry.register(AppGetDetailsTool(service))
    registry.register(AppCloseTool(service))
