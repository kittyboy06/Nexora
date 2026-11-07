import asyncio
from pydantic import BaseModel, Field
from backend.app.models.agent import RiskLevel
from backend.app.tools.base import BaseTool


class FileReadArgs(BaseModel):
    filepath: str = Field(..., min_length=1, description="Path to simulated file")


class MockFileReadTool(BaseTool):
    name = "mock_file_read"
    description = "Read simulated file contents without accessing host filesystem."
    risk_level = RiskLevel.SENSITIVE
    args_schema = FileReadArgs

    async def execute(self, filepath: str) -> dict:
        await asyncio.sleep(0.05)
        # Returns simulated mock content safely without touching real disks
        return {
            "filepath": filepath,
            "simulated": True,
            "content": f"[SIMULATED FILE CONTENT FOR '{filepath}']\nSystem parameters verified. Configuration active.",
            "byte_count": 86,
        }
