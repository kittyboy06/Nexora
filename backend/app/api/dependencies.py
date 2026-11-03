import httpx
from fastapi import Depends, Request
from backend.app.core.config import Settings, get_settings
from backend.app.core.guard import InferenceGuard
from backend.app.services.ollama_service import OllamaService


def get_app_settings() -> Settings:
    """Dependency provider for cached application settings."""
    return get_settings()


def get_http_client(request: Request) -> httpx.AsyncClient:
    """Dependency provider for the shared application httpx client."""
    client: httpx.AsyncClient = getattr(request.app.state, "http_client", None)
    if client is None:
        raise RuntimeError("Application HTTP client has not been initialized in lifespan.")
    return client


def get_inference_guard(request: Request) -> InferenceGuard:
    """Dependency provider for the GPU concurrency guard."""
    guard: InferenceGuard = getattr(request.app.state, "inference_guard", None)
    if guard is None:
        raise RuntimeError("InferenceGuard has not been initialized in lifespan.")
    return guard


def get_ollama_service(
    client: httpx.AsyncClient = Depends(get_http_client),
    settings: Settings = Depends(get_app_settings),
) -> OllamaService:
    """Dependency provider for OllamaService instance."""
    return OllamaService(client=client, settings=settings)
