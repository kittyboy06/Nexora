from typing import Any
from pydantic import BaseModel, Field
from backend.app.models.agent import RiskLevel
from backend.app.services.filesystem_service import FilesystemService
from backend.app.tools.base import BaseTool


class FileCreateArgs(BaseModel):
    path: str = Field(..., min_length=1, description="Relative destination file path inside workspace")
    content: str = Field(..., description="Text content to write")
    overwrite: bool = Field(default=False, description="Whether to overwrite existing file")


class FileCreateTool(BaseTool):
    name = "file_create"
    description = "Create a new file with content inside the workspace."
    risk_level = RiskLevel.CONTROLLED
    args_schema = FileCreateArgs

    def __init__(self, service: FilesystemService):
        self.service = service

    def get_risk_level(self, raw_args: dict[str, Any]) -> RiskLevel:
        # Overwriting existing content escalates to SENSITIVE
        if raw_args.get("overwrite") is True:
            return RiskLevel.SENSITIVE
        return RiskLevel.CONTROLLED

    async def execute(self, path: str, content: str, overwrite: bool = False) -> dict[str, Any]:
        return self.service.create_file(path=path, content=content, overwrite=overwrite)
