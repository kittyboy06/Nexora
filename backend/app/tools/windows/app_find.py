"""Tool to search installed desktop applications."""

from typing import Any
from pydantic import BaseModel, Field

from backend.app.models.agent import RiskLevel
from backend.app.services.app_service import AppService
from backend.app.tools.base import BaseTool


class AppFindArgs(BaseModel):
    query: str = Field(..., description="Application name, keyword, or publisher to search for.")


class AppFindTool(BaseTool):
    """Find installed applications by name or keyword."""

    name = "app_find"
    description = "Search for installed applications by name, keyword, or publisher."
    risk_level = RiskLevel.SAFE
    args_schema = AppFindArgs

    def __init__(self, service: AppService):
        self._service = service

    async def execute(self, query: str, **kwargs: Any) -> dict[str, Any]:
        matches = self._service.find_app(query)
        return {
            "query": query,
            "matches": matches,
            "count": len(matches),
        }
