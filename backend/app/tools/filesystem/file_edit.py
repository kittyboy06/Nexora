from typing import Any
from pydantic import BaseModel, Field
from backend.app.models.agent import RiskLevel
from backend.app.services.filesystem_service import FilesystemService
from backend.app.tools.base import BaseTool


class FileEditArgs(BaseModel):
    path: str = Field(..., min_length=1, description="Relative file path inside workspace")
    target: str = Field(..., min_length=1, description="Exact substring to find and replace")
    replacement: str = Field(..., description="Replacement text string")


class FileEditTool(BaseTool):
    name = "file_edit"
    description = "Replace a specific substring block in an existing workspace file."
    risk_level = RiskLevel.CONTROLLED
    args_schema = FileEditArgs

    def __init__(self, service: FilesystemService):
        self.service = service

    async def execute(self, path: str, target: str, replacement: str) -> dict[str, Any]:
        return self.service.edit_file(path=path, target_text=target, replacement_text=replacement)
