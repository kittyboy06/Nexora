"""Tool to get runtime details of a process."""

from typing import Any
from pydantic import BaseModel, Field

from backend.app.models.agent import RiskLevel
from backend.app.services.app_service import AppService
from backend.app.tools.base import BaseTool


class AppGetDetailsArgs(BaseModel):
    pid: int = Field(..., description="Process identifier (PID) to inspect.")


class AppGetDetailsTool(BaseTool):
    """Get performance and runtime details for a process."""

    name = "app_get_details"
    description = "Get runtime status, CPU, memory, uptime, and metadata for a specific process PID."
    risk_level = RiskLevel.SAFE
    args_schema = AppGetDetailsArgs

    def __init__(self, service: AppService):
        self._service = service

    async def execute(self, pid: int, **kwargs: Any) -> dict[str, Any]:
        return self._service.get_process_details(pid=pid)
