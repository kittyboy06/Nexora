from fastapi import APIRouter, Depends
from backend.app.api.dependencies import get_inference_guard, get_ollama_service
from backend.app.core.guard import InferenceGuard
from backend.app.models.chat import ChatRequest, ChatResponse
from backend.app.services.ollama_service import OllamaService

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("", response_model=ChatResponse, summary="Execute chat generation")
async def chat(
    request: ChatRequest,
    service: OllamaService = Depends(get_ollama_service),
    guard: InferenceGuard = Depends(get_inference_guard),
) -> ChatResponse:
    """
    Generate model completion for client-provided message history.
    Enforces GPU concurrency bounds to protect 8 GB VRAM.
    """
    async with guard.acquire():
        return await service.generate_chat(request)
