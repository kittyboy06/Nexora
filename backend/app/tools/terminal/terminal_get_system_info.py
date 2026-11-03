"""Tool to get host system information."""

from typing import Any
from pydantic import BaseModel

from backend.app.models.agent import RiskLevel
from backend.app.services.terminal_service import TerminalService
from backend.app.tools.base import BaseTool


class TerminalGetSystemInfoArgs(BaseModel):
    pass


class TerminalGetSystemInfoTool(BaseTool):
    """Get host system specifications and runtime information."""

    name = "terminal_get_system_info"
    description = "Get host system specs, OS release, CPU cores, RAM, and uptime."
    risk_level = RiskLevel.SAFE
    args_schema = TerminalGetSystemInfoArgs

    def __init__(self, service: TerminalService):
        self._service = service

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        return self._service.get_system_info()
