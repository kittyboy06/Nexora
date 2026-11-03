"""Tool to close a running application."""

from typing import Any
from pydantic import BaseModel, Field

from backend.app.models.agent import RiskLevel
from backend.app.services.app_service import AppService
from backend.app.tools.base import BaseTool


class AppCloseArgs(BaseModel):
    pid: int = Field(..., description="Process identifier (PID) to terminate.")
    force: bool = Field(default=False, description="Whether to forcefully terminate (kill) instead of graceful close.")


class AppCloseTool(BaseTool):
    """Close a running application. Sensitive operation requiring approval."""

    name = "app_close"
    description = "Close a running application by PID. Requires human approval. System processes are protected."
    risk_level = RiskLevel.SENSITIVE
    args_schema = AppCloseArgs

    def __init__(self, service: AppService):
        self._service = service

    async def execute(self, pid: int, force: bool = False, **kwargs: Any) -> dict[str, Any]:
        return self._service.close_app(pid=pid, force=force)
