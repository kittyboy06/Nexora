from typing import Any
from pydantic import BaseModel, Field
from backend.app.models.agent import RiskLevel
from backend.app.services.filesystem_service import FilesystemService
from backend.app.tools.base import BaseTool


class FileReadArgs(BaseModel):
    path: str = Field(..., min_length=1, description="Relative file path inside workspace")
    max_bytes: int = Field(default=5_000_000, ge=1, le=10_000_000, description="Maximum bytes to read")


class FileReadTool(BaseTool):
    name = "file_read"
    description = "Read text contents of a file within the workspace."
    risk_level = RiskLevel.SAFE
    args_schema = FileReadArgs

    def __init__(self, service: FilesystemService):
        self.service = service

    async def execute(self, path: str, max_bytes: int = 5_000_000) -> dict[str, Any]:
        return self.service.read_file(path=path, max_bytes=max_bytes)
