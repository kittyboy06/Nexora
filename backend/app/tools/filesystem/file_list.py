from typing import Any
from pydantic import BaseModel, Field
from backend.app.models.agent import RiskLevel
from backend.app.services.filesystem_service import FilesystemService
from backend.app.tools.base import BaseTool


class FileListArgs(BaseModel):
    path: str = Field(default=".", description="Relative folder path inside workspace")


class FileListTool(BaseTool):
    name = "file_list"
    description = "List files and subdirectories within a workspace directory."
    risk_level = RiskLevel.SAFE
    args_schema = FileListArgs

    def __init__(self, service: FilesystemService):
        self.service = service

    async def execute(self, path: str = ".") -> dict[str, Any]:
        return self.service.list_dir(path=path)
