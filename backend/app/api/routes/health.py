from fastapi import APIRouter, Depends
from backend.app.api.dependencies import get_app_settings
from backend.app.core.config import Settings
from backend.app.models.health import HealthCheckResponse

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("", response_model=HealthCheckResponse, summary="Backend health check")
async def health_check(settings: Settings = Depends(get_app_settings)) -> HealthCheckResponse:
    """
    Returns operational health of the FastAPI backend.
    This check succeeds independently of Ollama daemon status.
    """
    return HealthCheckResponse(
        status="ok",
        app_name=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.APP_ENV,
    )
