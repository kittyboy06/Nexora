"""Tool to launch a verified desktop application."""

from typing import Any
from pydantic import BaseModel, Field

from backend.app.models.agent import RiskLevel
from backend.app.services.app_service import AppService
from backend.app.tools.base import BaseTool


class AppLaunchArgs(BaseModel):
    app_name_or_path: str = Field(..., description="Application name, executable name, or validated file path.")
    arguments: list[str] | None = Field(default=None, description="Optional command-line arguments to pass to the application.")


class AppLaunchTool(BaseTool):
    """Launch a verified desktop application."""

    name = "app_launch"
    description = "Launch a verified desktop application asynchronously and track its PID."
    risk_level = RiskLevel.CONTROLLED
    args_schema = AppLaunchArgs

    def __init__(self, service: AppService):
        self._service = service

    async def execute(self, app_name_or_path: str, arguments: list[str] | None = None, **kwargs: Any) -> dict[str, Any]:
        return self._service.launch_app(app_name_or_path=app_name_or_path, arguments=arguments)
