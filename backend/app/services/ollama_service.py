import logging
from typing import Any
import httpx
from backend.app.core.config import Settings
from backend.app.core.exceptions import (
    InferenceTimeoutException,
    ModelNotFoundException,
    OllamaMalformedResponseException,
    OllamaUnavailableException,
)
from backend.app.models.chat import ChatMessage, ChatRequest, ChatResponse
from backend.app.models.ollama import ModelItem, OllamaStatusResponse

logger = logging.getLogger("nexora.ollama")


class OllamaService:
    """Service wrapping local Ollama daemon communication."""

    def __init__(self, client: httpx.AsyncClient, settings: Settings):
        self.client = client
        self.settings = settings

    def _matches_model(self, target: str, available_models: list[str]) -> bool:
        """Check if target model exists, accounting for tags."""
        if target in available_models:
            return True
        # If target has no tag (e.g. 'qwen3.5'), match 'qwen3.5:latest'
        if ":" not in target and f"{target}:latest" in available_models:
            return True
        # If available model has tag and matches base
        for m in available_models:
            if m.startswith(f"{target}:"):
                return True
        return False

    async def check_reachability(self) -> bool:
        """Probe Ollama reachability with a short timeout."""
        try:
            resp = await self.client.get(
                "/api/tags",
                timeout=self.settings.OLLAMA_CONNECT_TIMEOUT_SECONDS,
            )
            return resp.status_code == 200
        except (httpx.RequestError, httpx.TimeoutException) as exc:
            logger.debug("Ollama reachability probe failed: %s", exc)
            return False

    async def list_models(self) -> list[ModelItem]:
        """Fetch all installed models from local Ollama."""
        try:
            resp = await self.client.get(
                "/api/tags",
                timeout=self.settings.OLLAMA_CONNECT_TIMEOUT_SECONDS,
            )
        except (httpx.ConnectError, httpx.NetworkError) as exc:
            logger.warning("Ollama connection failed during list_models: %s", exc)
            raise OllamaUnavailableException()
        except httpx.TimeoutException as exc:
            logger.warning("Ollama timeout during list_models: %s", exc)
            raise OllamaUnavailableException(message="Ollama connection timed out while querying models.")
        except httpx.RequestError as exc:
            logger.warning("Ollama request error during list_models: %s", exc)
            raise OllamaUnavailableException(message=f"Network error querying Ollama: {exc}")

        if resp.status_code != 200:
            logger.error("Ollama /api/tags returned status %d", resp.status_code)
            raise OllamaMalformedResponseException(
                message=f"Ollama returned unexpected HTTP {resp.status_code}",
                details={"status_code": resp.status_code, "body": resp.text[:200]},
            )

        try:
            data = resp.json()
            raw_models = data.get("models", [])
            items = []
            for m in raw_models:
                items.append(
                    ModelItem(
                        name=m.get("name", "unknown"),
                        size_bytes=m.get("size"),
                        modified_at=m.get("modified_at"),
                        digest=m.get("digest"),
                    )
                )
            return items
        except Exception as exc:
            logger.error("Failed to parse Ollama /api/tags payload: %s", exc)
            raise OllamaMalformedResponseException(details={"error": str(exc)})

    async def get_status(self) -> OllamaStatusResponse:
        """Check reachability and configured model availability without throwing."""
        try:
            models = await self.list_models()
            model_names = [m.name for m in models]
            is_available = self._matches_model(self.settings.OLLAMA_MODEL, model_names)
            return OllamaStatusResponse(
                reachable=True,
                model_available=is_available,
                configured_model=self.settings.OLLAMA_MODEL,
                installed_models=model_names,
            )
        except OllamaUnavailableException:
            return OllamaStatusResponse(
                reachable=False,
                model_available=False,
                configured_model=self.settings.OLLAMA_MODEL,
                installed_models=[],
            )
        except Exception as exc:
            logger.warning("Unexpected error during Ollama status check: %s", exc)
            return OllamaStatusResponse(
                reachable=False,
                model_available=False,
                configured_model=self.settings.OLLAMA_MODEL,
                installed_models=[],
            )

    async def generate_chat(self, request: ChatRequest) -> ChatResponse:
        """Execute chat completion against Ollama with model checks and timeouts."""
        target_model = request.model or self.settings.OLLAMA_MODEL

        # 1. Verify model is installed before starting generation
        models = await self.list_models()
        installed_names = [m.name for m in models]
        if not self._matches_model(target_model, installed_names):
            logger.warning("Requested model '%s' not found in %s", target_model, installed_names)
            raise ModelNotFoundException(
                model_name=target_model,
                details={"installed_models": installed_names},
            )

        # 2. Build Ollama chat payload
        payload: dict[str, Any] = {
            "model": target_model,
            "messages": [msg.model_dump() for msg in request.messages],
            "stream": False,
        }
        if request.temperature is not None:
            payload["options"] = {"temperature": request.temperature}

        logger.info("Dispatching chat request to Ollama (model=%s, messages=%d)", target_model, len(request.messages))

        # 3. Dispatch POST /api/chat with configured inference timeout
        try:
            resp = await self.client.post(
                "/api/chat",
                json=payload,
                timeout=self.settings.OLLAMA_INFERENCE_TIMEOUT_SECONDS,
            )
        except (httpx.ConnectError, httpx.NetworkError) as exc:
            logger.error("Connection failed during Ollama inference: %s", exc)
            raise OllamaUnavailableException()
        except httpx.TimeoutException:
            logger.error("Inference timed out after %.1fs", self.settings.OLLAMA_INFERENCE_TIMEOUT_SECONDS)
            raise InferenceTimeoutException(timeout_seconds=self.settings.OLLAMA_INFERENCE_TIMEOUT_SECONDS)
        except httpx.RequestError as exc:
            logger.error("Ollama network error during inference: %s", exc)
            raise OllamaUnavailableException(message=f"Network error during chat generation: {exc}")

        # 4. Handle HTTP response status
        if resp.status_code == 404:
            raise ModelNotFoundException(model_name=target_model)
        if resp.status_code != 200:
            logger.error("Ollama /api/chat error %d: %s", resp.status_code, resp.text[:200])
            raise OllamaMalformedResponseException(
                message=f"Ollama returned HTTP {resp.status_code} during chat generation",
                details={"status_code": resp.status_code, "body": resp.text[:200]},
            )

        # 5. Parse response payload
        try:
            data = resp.json()
            raw_msg = data.get("message", {})
            assistant_content = raw_msg.get("content", "")
            assistant_role = raw_msg.get("role", "assistant")

            # Ollama total_duration is reported in nanoseconds
            total_duration_ns = data.get("total_duration")
            duration_ms = (total_duration_ns / 1_000_000.0) if total_duration_ns is not None else None

            return ChatResponse(
                message=ChatMessage(role=assistant_role, content=assistant_content),
                model=data.get("model", target_model),
                done=data.get("done", True),
                eval_count=data.get("eval_count"),
                duration_ms=round(duration_ms, 2) if duration_ms is not None else None,
            )
        except Exception as exc:
            logger.error("Failed to parse Ollama chat response: %s", exc)
            raise OllamaMalformedResponseException(details={"error": str(exc), "raw_body": resp.text[:200]})
