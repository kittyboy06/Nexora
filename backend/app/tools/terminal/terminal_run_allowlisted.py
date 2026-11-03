"""Tool to execute allowlisted terminal commands."""

from typing import Any
from pydantic import BaseModel, Field

from backend.app.models.agent import RiskLevel
from backend.app.services.terminal_service import TerminalService
from backend.app.tools.base import BaseTool


class TerminalRunAllowlistedArgs(BaseModel):
    command: str = Field(..., description="Allowlisted command binary (e.g. python, pip, git, node, npm, pytest, whoami, ipconfig).")
    args: list[str] | None = Field(default=None, description="Optional command-line argument list.")


class TerminalRunAllowlistedTool(BaseTool):
    """Execute an allowlisted terminal command inside the workspace sandbox."""

    name = "terminal_run_allowlisted"
    description = "Execute an allowlisted terminal command inside the workspace sandbox."
    risk_level = RiskLevel.CONTROLLED
    args_schema = TerminalRunAllowlistedArgs

    def __init__(self, service: TerminalService):
        self._service = service

    async def execute(self, command: str, args: list[str] | None = None, **kwargs: Any) -> dict[str, Any]:
        return await self._service.execute_command(command=command, args=args)
