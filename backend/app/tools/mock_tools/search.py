import asyncio
from pydantic import BaseModel, Field
from backend.app.models.agent import RiskLevel
from backend.app.tools.base import BaseTool


class SearchArgs(BaseModel):
    query: str = Field(..., min_length=1, description="Search terms or question")
    max_results: int = Field(default=3, ge=1, le=10, description="Max search snippets to return")


class MockSearchTool(BaseTool):
    name = "mock_search"
    description = "Simulate searching the web or documentation for information."
    risk_level = RiskLevel.SAFE
    args_schema = SearchArgs

    async def execute(self, query: str, max_results: int = 3) -> dict:
        await asyncio.sleep(0.05)  # Simulate I/O latency
        results = [
            {"title": f"Result {i+1} for '{query}'", "snippet": f"Simulated information snippet regarding {query}."}
            for i in range(max_results)
        ]
        return {"query": query, "results": results, "count": len(results)}
