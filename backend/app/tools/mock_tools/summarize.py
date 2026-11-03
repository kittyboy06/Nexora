import asyncio
from pydantic import BaseModel, Field
from backend.app.models.agent import RiskLevel
from backend.app.tools.base import BaseTool


class SummarizeArgs(BaseModel):
    text: str = Field(..., min_length=1, description="Input text to summarize")
    max_words: int = Field(default=50, ge=5, le=200, description="Max word count for summary")


class MockSummarizeTool(BaseTool):
    name = "mock_summarize"
    description = "Condense and extract key points from text."
    risk_level = RiskLevel.SAFE
    args_schema = SummarizeArgs

    async def execute(self, text: str, max_words: int = 50) -> dict:
        await asyncio.sleep(0.05)
        words = text.split()
        summary_words = words[:max_words]
        summary = " ".join(summary_words)
        if len(words) > max_words:
            summary += "..."
        return {"original_word_count": len(words), "summary": summary}
