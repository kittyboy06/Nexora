from typing import Literal
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"] = Field(..., description="Message role")
    content: str = Field(..., min_length=1, description="Message text content")


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(..., min_length=1, description="Conversation history (client-managed)")
    model: str | None = Field(default=None, description="Optional override for model name")
    temperature: float | None = Field(default=None, ge=0.0, le=2.0, description="Sampling temperature")


class ChatResponse(BaseModel):
    message: ChatMessage = Field(..., description="Generated assistant message")
    model: str = Field(..., description="Model used for generation")
    done: bool = Field(default=True, description="Whether generation is complete")
    eval_count: int | None = Field(default=None, description="Number of tokens generated")
    duration_ms: float | None = Field(default=None, description="Total generation duration in milliseconds")
