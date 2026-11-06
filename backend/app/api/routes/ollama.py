from fastapi import APIRouter, Depends
from backend.app.api.dependencies import get_ollama_service
from backend.app.models.ollama import ModelListResponse, OllamaStatusResponse
from backend.app.services.ollama_service import OllamaService
from backend.app.core.config import Settings, get_settings
from backend.app.models.model_profile import ModelProfileListResponse
from backend.app.services.model_registry import ModelProfileRegistry

router = APIRouter(prefix="/ollama", tags=["Ollama"])


@router.get("/status", response_model=OllamaStatusResponse, summary="Ollama connectivity and model status")
async def get_ollama_status(
    service: OllamaService = Depends(get_ollama_service),
) -> OllamaStatusResponse:
    """
    Returns Ollama reachability and whether the configured model is locally available.
    Does not raise an error if Ollama is offline.
    """
    return await service.get_status()


@router.get("/models", response_model=ModelListResponse, summary="List locally installed Ollama models")
async def list_ollama_models(
    service: OllamaService = Depends(get_ollama_service),
) -> ModelListResponse:
    """
    Returns list of all models currently installed in the local Ollama instance.
    Raises HTTP 503 if Ollama is offline.
    """
    models = await service.list_models()
    return ModelListResponse(models=models, count=len(models))


@router.get("/profiles", response_model=ModelProfileListResponse, summary="List specialist profiles and local model availability")
async def list_model_profiles(
    service: OllamaService = Depends(get_ollama_service),
    settings: Settings = Depends(get_settings),
) -> ModelProfileListResponse:
    """Show configured specialist profiles and whether each model is installed."""
    return await ModelProfileRegistry(settings).list_profiles(service)
