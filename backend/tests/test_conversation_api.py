"""Integration tests for Phase 15 Conversation REST API and Intent Routing."""

import json
import pytest
import httpx
from httpx import ASGITransport

from backend.app.api.dependencies import get_ollama_service
from backend.app.core.config import get_settings
from backend.app.main import create_app
from backend.app.services.ollama_service import OllamaService


@pytest.mark.asyncio
async def test_conversation_lifecycle_and_modes():
    app = create_app()
    settings = get_settings()

    def mock_ollama_handler(request: httpx.Request):
        if request.url.path == "/api/chat":
            content_str = request.content.decode("utf-8")
            # If intent classification prompt
            if "NEXORA's intent classifier" in content_str:
                return httpx.Response(
                    200,
                    json={
                        "model": "auto",
                        "message": {
                            "role": "assistant",
                            "content": json.dumps({
                                "intent": "answer",
                                "summary": "Conversational reply",
                                "confidence": 0.95
                            })
                        },
                        "done": True,
                    }
                )
            # Default conversational chat reply
            return httpx.Response(
                200,
                json={
                    "model": "auto",
                    "message": {
                        "role": "assistant",
                        "content": "Hello! I am NEXORA, your local autonomous assistant."
                    },
                    "done": True,
                }
            )
        # /api/tags
        return httpx.Response(200, json={"models": [{"name": "mock-model:latest"}]})

    mock_transport = httpx.MockTransport(mock_ollama_handler)
    mock_client = httpx.AsyncClient(transport=mock_transport, base_url="http://mock-ollama:11434")
    app.dependency_overrides[get_ollama_service] = lambda: OllamaService(client=mock_client, settings=settings)

    async with app.router.lifespan_context(app):
        app.state.http_client = mock_client
        app.state.ollama_service = OllamaService(client=mock_client, settings=settings)
        if hasattr(app.state, "conversation_service"):
            app.state.conversation_service.ollama = app.state.ollama_service
            app.state.conversation_service.intent_classifier.ollama = app.state.ollama_service

        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 1. Create conversation
            create_res = await client.post("/api/conversations", json={"title": "General Inquiries"})
            assert create_res.status_code == 201
            conv_data = create_res.json()["conversation"]
            conv_id = conv_data["conversation_id"]
            assert conv_id.startswith("conv_")
            assert conv_data["title"] == "General Inquiries"

            # 2. List conversations
            list_res = await client.get("/api/conversations")
            assert list_res.status_code == 200
            convs = list_res.json()["conversations"]
            assert any(c["conversation_id"] == conv_id for c in convs)

            # 3. Post ordinary question (Answer Only) -> MUST NOT create work item
            msg_res = await client.post(
                f"/api/conversations/{conv_id}/messages",
                json={"content": "Hello, how are you today?", "mode": "auto"}
            )
            assert msg_res.status_code == 200
            body = msg_res.json()
            assert body["message"]["role"] == "assistant"
            assert "NEXORA" in body["message"]["content"]
            assert body["work_item"] is None

            # Verify conversation state
            get_res = await client.get(f"/api/conversations/{conv_id}")
            assert get_res.status_code == 200
            conv = get_res.json()["conversation"]
            assert len(conv["messages"]) == 2
            assert len(conv["work_items"]) == 0

            # 4. Post explicit research mode -> Creates research work item
            res_msg = await client.post(
                f"/api/conversations/{conv_id}/messages",
                json={"content": "Search the web for local LLM benchmarks", "mode": "research"}
            )
            assert res_msg.status_code == 200
            res_body = res_msg.json()
            assert res_body["work_item"] is not None
            assert res_body["work_item"]["intent"] == "research"
            assert res_body["work_item"]["target_module"] == "research"

            # 5. Secret scrubbing test
            sec_res = await client.post(
                f"/api/conversations/{conv_id}/messages",
                json={"content": "My secret is sk-abcdef1234567890abcdef123456", "mode": "answer_only"}
            )
            assert sec_res.status_code == 200
            conv_updated = (await client.get(f"/api/conversations/{conv_id}")).json()["conversation"]
            last_user_msg = [m for m in conv_updated["messages"] if m["role"] == "user"][-1]
            assert "sk-" not in last_user_msg["content"]
            assert "[REDACTED_SECRET]" in last_user_msg["content"]

            # 6. Delete conversation
            del_res = await client.delete(f"/api/conversations/{conv_id}")
            assert del_res.status_code == 200
            assert del_res.json()["status"] == "ok"
