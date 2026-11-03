"""Tool to list running processes."""

from typing import Any
from pydantic import BaseModel, Field

from backend.app.models.agent import RiskLevel
from backend.app.services.app_service import AppService
from backend.app.tools.base import BaseTool


class AppGetRunningArgs(BaseModel):
    include_system: bool = Field(default=False, description="Whether to include protected Windows system processes.")
    limit: int = Field(default=100, description="Maximum number of process records to return.")


class AppGetRunningTool(BaseTool):
    """List running desktop processes."""

    name = "app_get_running"
    description = "List active non-system desktop processes with PID, name, memory, and status."
    risk_level = RiskLevel.SAFE
    args_schema = AppGetRunningArgs

    def __init__(self, service: AppService):
        self._service = service

    async def execute(self, include_system: bool = False, limit: int = 100, **kwargs: Any) -> dict[str, Any]:
        processes = self._service.get_running_processes(include_system=include_system, limit=limit)
        return {
            "processes": processes,
            "count": len(processes),
        }
