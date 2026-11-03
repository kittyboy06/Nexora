from typing import Any
from pydantic import BaseModel, Field
from backend.app.models.agent import RiskLevel
from backend.app.services.filesystem_service import FilesystemService
from backend.app.tools.base import BaseTool


class FileRenameArgs(BaseModel):
    source: str = Field(..., min_length=1, description="Source path inside workspace")
    target_name: str = Field(..., min_length=1, description="New name or target path inside workspace")


class FileRenameTool(BaseTool):
    name = "file_rename"
    description = "Rename a file or directory within the workspace."
    risk_level = RiskLevel.CONTROLLED
    args_schema = FileRenameArgs

    def __init__(self, service: FilesystemService):
        self.service = service

    async def execute(self, source: str, target_name: str) -> dict[str, Any]:
        return self.service.rename_file(source=source, target_name=target_name)
