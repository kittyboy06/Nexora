"""Tool to execute a Python script inside the workspace sandbox."""

from typing import Any
from pydantic import BaseModel, Field

from backend.app.models.agent import RiskLevel
from backend.app.services.terminal_service import TerminalService
from backend.app.tools.base import BaseTool


class TerminalRunScriptArgs(BaseModel):
    script_path: str = Field(..., description="Relative path to Python (.py) script inside the workspace.")
    args: list[str] | None = Field(default=None, description="Optional command-line arguments to pass to the script.")


class TerminalRunScriptTool(BaseTool):
    """Execute a Python script located within the workspace sandbox."""

    name = "terminal_run_script"
    description = "Execute a Python script located within the workspace sandbox."
    risk_level = RiskLevel.CONTROLLED
    args_schema = TerminalRunScriptArgs

    def __init__(self, service: TerminalService):
        self._service = service

    async def execute(self, script_path: str, args: list[str] | None = None, **kwargs: Any) -> dict[str, Any]:
        return await self._service.run_script(script_path=script_path, args=args)
