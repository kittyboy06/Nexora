"""Tool to list installed desktop applications."""

from typing import Any
from pydantic import BaseModel, Field

from backend.app.models.agent import RiskLevel
from backend.app.services.app_service import AppService
from backend.app.tools.base import BaseTool


class AppListInstalledArgs(BaseModel):
    force_refresh: bool = Field(default=False, description="Whether to bypass the in-memory cache and re-scan the system.")


class AppListInstalledTool(BaseTool):
    """List installed desktop applications."""

    name = "app_list_installed"
    description = "List discovered desktop applications installed on the Windows system."
    risk_level = RiskLevel.SAFE
    args_schema = AppListInstalledArgs

    def __init__(self, service: AppService):
        self._service = service

    async def execute(self, force_refresh: bool = False, **kwargs: Any) -> dict[str, Any]:
        apps = self._service.list_installed_apps(force_refresh=force_refresh)
        return {
            "applications": apps,
            "count": len(apps),
        }
