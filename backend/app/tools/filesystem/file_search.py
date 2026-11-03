from typing import Any
from pydantic import BaseModel, Field
from backend.app.models.agent import RiskLevel
from backend.app.services.filesystem_service import FilesystemService
from backend.app.tools.base import BaseTool


class FileSearchArgs(BaseModel):
    pattern: str = Field(..., min_length=1, description="Glob pattern to search (e.g. '*.py', '*report*')")
    path: str = Field(default=".", description="Subdirectory to search inside workspace")


class FileSearchTool(BaseTool):
    name = "file_search"
    description = "Recursively search for files matching a pattern within workspace."
    risk_level = RiskLevel.SAFE
    args_schema = FileSearchArgs

    def __init__(self, service: FilesystemService):
        self.service = service

    async def execute(self, pattern: str, path: str = ".") -> dict[str, Any]:
        return self.service.search_files(pattern=pattern, path=path)
