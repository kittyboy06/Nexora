"""Tool to get directory information."""

from typing import Any
from pydantic import BaseModel

from backend.app.models.agent import RiskLevel
from backend.app.services.terminal_service import TerminalService
from backend.app.tools.base import BaseTool


class TerminalGetDirectoryArgs(BaseModel):
    pass


class TerminalGetDirectoryTool(BaseTool):
    """Get current working directory and designated workspace jail."""

    name = "terminal_get_directory"
    description = "Get current working directory and designated workspace jail."
    risk_level = RiskLevel.SAFE
    args_schema = TerminalGetDirectoryArgs

    def __init__(self, service: TerminalService):
        self._service = service

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        return self._service.get_directory_info()
