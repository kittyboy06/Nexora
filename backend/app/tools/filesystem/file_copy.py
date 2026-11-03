from typing import Any
from pydantic import BaseModel, Field
from backend.app.models.agent import RiskLevel
from backend.app.services.filesystem_service import FilesystemService
from backend.app.tools.base import BaseTool


class FileCopyArgs(BaseModel):
    source: str = Field(..., min_length=1, description="Source path inside workspace")
    destination: str = Field(..., min_length=1, description="Destination path inside workspace")
    overwrite: bool = Field(default=False, description="Whether to overwrite existing destination")


class FileCopyTool(BaseTool):
    name = "file_copy"
    description = "Copy a file or directory within the workspace."
    risk_level = RiskLevel.CONTROLLED
    args_schema = FileCopyArgs

    def __init__(self, service: FilesystemService):
        self.service = service

    def get_risk_level(self, raw_args: dict[str, Any]) -> RiskLevel:
        if raw_args.get("overwrite") is True:
            return RiskLevel.SENSITIVE
        return RiskLevel.CONTROLLED

    async def execute(self, source: str, destination: str, overwrite: bool = False) -> dict[str, Any]:
        return self.service.copy_file(source=source, destination=destination, overwrite=overwrite)
