import json

import pytest
from backend.app.core.config import Settings
from backend.app.core.guard import InferenceGuard
from backend.app.models.model_profile import TaskKind
from backend.app.services.model_registry import HybridModelRouter, ModelProfileRegistry


class FakeOllama:
    def __init__(self, answers):
        self.answers = list(answers)
        self.requests = []

    async def list_models(self):
        class Item:
            name = "router-small:latest"
        class Worker:
            name = "worker-large:latest"
        return [Item(), Worker()]

    @staticmethod
    def model_matches(target, available):
        return target in available or f"{target}:latest" in available

    async def generate_chat(self, request):
        self.requests.append(request)
        class Message:
            def __init__(self, content):
                self.content = content
        class Response:
            def __init__(self, content):
                self.message = Message(content)
        return Response(self.answers.pop(0))


@pytest.fixture
def profiles_file(tmp_path):
    path = tmp_path / "profiles.json"
    path.write_text(json.dumps({"profiles": [
        {"profile_id": "router", "model": "router-small", "specialties": ["general"], "role": "router"},
        {"profile_id": "general", "model": "worker-large", "specialties": ["general"]},
        {"profile_id": "coder", "model": "worker-large", "specialties": ["code"], "system_instruction": "Code carefully."},
        {"profile_id": "researcher", "model": "worker-large", "specialties": ["research"]},
    ]}), encoding="utf-8")
    return path


def make_router(profiles_file, ollama, primary_model="worker-large"):
    settings = Settings(
        OLLAMA_MODEL=primary_model,
        MODEL_ROUTER_MODEL="router-small",
        MODEL_ROUTER_CONFIDENCE_THRESHOLD=0.65,
        MODEL_PROFILES_FILE=str(profiles_file),
    )
    return HybridModelRouter(ModelProfileRegistry(settings), settings, ollama, InferenceGuard())


@pytest.mark.asyncio
async def test_routes_confident_classification_to_specialist(profiles_file):
    ollama = FakeOllama(['{"task_kind":"code","confidence":0.94}'])
    decision = await make_router(profiles_file, ollama).route("Implement a parser")
    assert decision.profile_id == "coder"
    assert decision.model == "worker-large"
    assert decision.task_kind == TaskKind.CODE
    assert len(ollama.requests) == 1


@pytest.mark.asyncio
async def test_uncertain_small_router_escalates_to_primary_model(profiles_file):
    ollama = FakeOllama([
        '{"task_kind":"general","confidence":0.4}',
        '{"task_kind":"research","confidence":0.9}',
    ])
    decision = await make_router(profiles_file, ollama).route("Compare two published studies")
    assert decision.profile_id == "researcher"
    assert decision.escalated is True
    assert [request.model for request in ollama.requests] == ["router-small", "worker-large"]


@pytest.mark.asyncio
async def test_manual_profile_override_skips_classifier(profiles_file):
    ollama = FakeOllama([])
    decision = await make_router(profiles_file, ollama).route("anything", profile_override="coder")
    assert decision.profile_id == "coder"
    assert decision.reason == "manual profile override"
    assert ollama.requests == []


@pytest.mark.asyncio
async def test_invalid_classifier_falls_back_to_task_signals(profiles_file):
    ollama = FakeOllama(["not json"])
    decision = await make_router(profiles_file, ollama).route("Please debug this Python function")
    assert decision.profile_id == "coder"
    assert decision.task_kind == TaskKind.CODE
    assert "fallback" in decision.reason


@pytest.mark.asyncio
async def test_same_router_and_primary_model_uses_fallback_without_duplicate_call(profiles_file):
    ollama = FakeOllama(['{"task_kind":"general","confidence":0.3}'])
    decision = await make_router(profiles_file, ollama, primary_model="router-small").route("Debug this Python code")
    assert decision.profile_id == "coder"
    assert decision.escalated is False
    assert len(ollama.requests) == 1
