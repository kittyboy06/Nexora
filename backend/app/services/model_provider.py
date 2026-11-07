"""Provider-independent contract used by model discovery and inference routing."""

from typing import Protocol

from backend.app.models.chat import ChatRequest, ChatResponse
from backend.app.models.ollama import ModelItem


class ModelProvider(Protocol):
    async def list_models(self) -> list[ModelItem]: ...

    async def generate_chat(self, request: ChatRequest) -> ChatResponse: ...

    def model_matches(self, target: str, available_models: list[str]) -> bool: ...

    async def resolve_active_model(self) -> str: ...
