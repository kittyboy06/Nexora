from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from backend.app.api.dependencies import get_model_profile_registry, get_ollama_service
from backend.app.models.ollama import ModelListResponse, OllamaStatusResponse
from backend.app.services.ollama_service import OllamaService
from backend.app.models.model_profile import ModelProfileListResponse
from backend.app.services.model_registry import ModelProfileRegistry

router = APIRouter(prefix="/ollama", tags=["Ollama"])


class SetActiveModelRequest(BaseModel):
    model: str = Field(..., min_length=1, description="Model tag to set as active")


class SetActiveModelResponse(BaseModel):
    status: str = "ok"
    active_model: str


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


@router.get("/active-model", response_model=SetActiveModelResponse, summary="Get currently active model")
async def get_active_model(
    service: OllamaService = Depends(get_ollama_service),
) -> SetActiveModelResponse:
    """Returns the currently active or auto-discovered model tag."""
    active = await service.resolve_active_model()
    return SetActiveModelResponse(status="ok", active_model=active)


@router.post("/active-model", response_model=SetActiveModelResponse, summary="Set active model at runtime")
async def set_active_model(
    payload: SetActiveModelRequest,
    service: OllamaService = Depends(get_ollama_service),
) -> SetActiveModelResponse:
    """Dynamically set the active model used across NEXORA operations."""
    service.set_active_model(payload.model)
    return SetActiveModelResponse(status="ok", active_model=payload.model)


@router.get("/profiles", response_model=ModelProfileListResponse, summary="List specialist profiles and local model availability")
async def list_model_profiles(
    refresh: bool = False,
    service: OllamaService = Depends(get_ollama_service),
    registry: ModelProfileRegistry = Depends(get_model_profile_registry),
) -> ModelProfileListResponse:
    """Show configured specialist profiles and whether each model is installed."""
    if refresh:
        registry.reload()
    return await registry.list_profiles(service)


@router.post("/profiles/reload", response_model=ModelProfileListResponse, summary="Reload specialist profile catalogue from disk")
async def reload_model_profiles(
    service: OllamaService = Depends(get_ollama_service),
    registry: ModelProfileRegistry = Depends(get_model_profile_registry),
) -> ModelProfileListResponse:
    """Reload profile definitions from disk and report updated catalogue with local model availability."""
    registry.reload()
    return await registry.list_profiles(service)
