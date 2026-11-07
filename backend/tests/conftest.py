import pytest
import pytest_asyncio
import httpx
from httpx import ASGITransport
from backend.app.api.dependencies import get_app_settings
from backend.app.core.config import Settings
from backend.app.core.guard import InferenceGuard
from backend.app.main import create_app


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        APP_NAME="NEXORA_TEST",
        APP_ENV="test",
        OLLAMA_BASE_URL="http://mock-ollama:11434",
        OLLAMA_MODEL="qwen3.5:9b",
        OLLAMA_CONNECT_TIMEOUT_SECONDS=1.0,
        OLLAMA_INFERENCE_TIMEOUT_SECONDS=2.0,
        INFERENCE_CONCURRENCY_LIMIT=1,
        INFERENCE_SEMAPHORE_TIMEOUT_SECONDS=0.1,
        LOG_LEVEL="DEBUG",
    )


@pytest_asyncio.fixture
async def app_with_mock_ollama(test_settings: Settings):
    """Factory fixture returning an app configured with a mock HTTP transport."""

    def _build_app(handler):
        mock_transport = httpx.MockTransport(handler)
        mock_http_client = httpx.AsyncClient(
            transport=mock_transport,
            base_url=test_settings.OLLAMA_BASE_URL,
        )

        app = create_app()
        # Override settings and state for testing
        app.dependency_overrides[get_app_settings] = lambda: test_settings
        app.state.http_client = mock_http_client
        app.state.inference_guard = InferenceGuard(
            limit=test_settings.INFERENCE_CONCURRENCY_LIMIT,
            timeout=test_settings.INFERENCE_SEMAPHORE_TIMEOUT_SECONDS,
        )
        return app, mock_http_client

    return _build_app
