from typing import Any
from pydantic import BaseModel, Field
from backend.app.models.agent import RiskLevel
from backend.app.services.filesystem_service import FilesystemService
from backend.app.tools.base import BaseTool


class FileDeleteArgs(BaseModel):
    path: str = Field(..., min_length=1, description="Path to file or folder to delete inside workspace")
    recursive: bool = Field(default=False, description="Whether to recursively delete directories")


class FileDeleteTool(BaseTool):
    name = "file_delete"
    description = "Delete a file or folder within the workspace (Requires approval)."
    risk_level = RiskLevel.SENSITIVE
    args_schema = FileDeleteArgs

    def __init__(self, service: FilesystemService):
        self.service = service

    def get_risk_level(self, raw_args: dict[str, Any]) -> RiskLevel:
        return RiskLevel.SENSITIVE

    async def execute(self, path: str, recursive: bool = False) -> dict[str, Any]:
        return self.service.delete_file(path=path, recursive=recursive)
