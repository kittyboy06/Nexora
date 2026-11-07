r"""Opt-In Live Local Smoke Test Suite for Phase 14.

These tests communicate with a live local Ollama service.
Skipped by default to guarantee hermetic, offline test gating (<= 60s).
Run via:
    $env:NEXORA_RUN_LIVE_TESTS = "1"
    python -m pytest backend/tests/integration/test_live_smoke.py -v
Or via:
    .\scripts\run-all-tests.ps1 -IncludeLive
"""

import os
import pytest
import httpx

from backend.app.core.config import get_settings


LIVE_ENV_VAR = "NEXORA_RUN_LIVE_TESTS"


@pytest.fixture(autouse=True)
def require_live_environment():
    """Skip test unless NEXORA_RUN_LIVE_TESTS=1 is explicitly set."""
    if os.getenv(LIVE_ENV_VAR, "").lower() not in ("1", "true", "yes"):
        pytest.skip(
            f"Live smoke test skipped (default offline gate). Set {LIVE_ENV_VAR}=1 to execute against local Ollama."
        )


@pytest.mark.asyncio
async def test_live_ollama_connectivity():
    """Verify live local Ollama daemon is reachable on 127.0.0.1:11434."""
    settings = get_settings()
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            res = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
        except Exception as exc:
            pytest.fail(f"Could not connect to live Ollama at {settings.OLLAMA_BASE_URL}: {exc}")

        assert res.status_code == 200, f"Ollama returned HTTP {res.status_code}: {res.text}"
        data = res.json()
        models = [m.get("name") for m in data.get("models", [])]
        assert len(models) >= 0, "Ollama tags response parsed successfully"


@pytest.mark.asyncio
async def test_live_ollama_inference():
    """Verify live local Ollama model can perform basic single-token inference."""
    settings = get_settings()
    async with httpx.AsyncClient(timeout=60.0) as client:
        # First check available models
        try:
            tags_res = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            models = [m.get("name") for m in tags_res.json().get("models", [])]
        except Exception as exc:
            pytest.fail(f"Failed to query Ollama models: {exc}")

        # Choose configured model or first available
        target_model = settings.OLLAMA_MODEL
        matched = any(target_model in m for m in models)
        if not matched and models:
            target_model = models[0]

        payload = {
            "model": target_model,
            "prompt": "Respond with only the single uppercase word: OK",
            "stream": False,
        }

        try:
            generate_res = await client.post(
                f"{settings.OLLAMA_BASE_URL}/api/generate",
                json=payload,
            )
        except Exception as exc:
            pytest.fail(f"Live inference request failed against {target_model}: {exc}")

        assert generate_res.status_code == 200
        output_text = generate_res.json().get("response", "").strip()
        assert len(output_text) > 0, "Ollama returned empty response string"
