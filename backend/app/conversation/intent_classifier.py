"""Hybrid intent classifier distinguishing conversational queries from operational goals."""

from __future__ import annotations

import logging
from typing import Any
from backend.app.core.guard import InferenceGuard
from backend.app.core.json_utils import extract_json_object
from backend.app.models.chat import ChatMessage, ChatRequest
from backend.app.models.conversation import ChatMode, WorkItemIntent
from backend.app.services.ollama_service import OllamaService

logger = logging.getLogger("nexora.conversation.intent")

GREETING_WORDS = {
    "hi", "hello", "hey", "greetings", "good morning", "good afternoon",
    "good evening", "howdy", "sup", "yo", "what's up", "whats up"
}

QUESTION_PREFIXES = (
    "what is", "what are", "what can you", "who are you", "who made you",
    "how do i", "how does", "why is", "why does", "explain", "tell me about",
    "can you explain", "define", "help", "thank you", "thanks"
)


class IntentClassificationResult:
    def __init__(self, intent: WorkItemIntent, summary: str, confidence: float = 1.0):
        self.intent = intent
        self.summary = summary
        self.confidence = confidence


class IntentClassifier:
    """Classifies user messages to decide if an operational work item is needed."""

    def __init__(self, ollama: OllamaService, guard: InferenceGuard):
        self.ollama = ollama
        self.guard = guard

    async def classify(
        self, prompt: str, mode: ChatMode = ChatMode.AUTO, model: str | None = None
    ) -> IntentClassificationResult:
        """Classify user prompt into an intent respecting mode overrides."""
        # 1. Explicit Mode Overrides
        if mode == ChatMode.ANSWER_ONLY:
            return IntentClassificationResult(WorkItemIntent.ANSWER, "Conversational answer requested")
        if mode == ChatMode.TASK:
            return IntentClassificationResult(WorkItemIntent.TASK, f"Execute task: {prompt[:80]}")
        if mode == ChatMode.RESEARCH:
            return IntentClassificationResult(WorkItemIntent.RESEARCH, f"Web research: {prompt[:80]}")
        if mode == ChatMode.DESKTOP_VISION:
            return IntentClassificationResult(WorkItemIntent.DESKTOP_VISION, f"Desktop automation: {prompt[:80]}")
        if mode == ChatMode.SCHEDULE:
            return IntentClassificationResult(WorkItemIntent.SCHEDULE, f"Schedule workflow: {prompt[:80]}")

        # 2. Fast Rule-Based Matching for Common Conversational Inputs
        cleaned = prompt.strip().casefold()
        if cleaned in GREETING_WORDS or any(cleaned.startswith(p) for p in QUESTION_PREFIXES):
            return IntentClassificationResult(WorkItemIntent.ANSWER, "Conversational inquiry", confidence=0.99)

        # Keyword heuristics for specific operational categories
        if any(w in cleaned for w in ("import skill", "install skill", "add skill", "load skill")):
            return IntentClassificationResult(WorkItemIntent.SKILL_IMPORT, "Import and review skill package", confidence=0.9)
        if any(w in cleaned for w in ("connect mcp", "add mcp", "install mcp", "register mcp", "mcp server")):
            return IntentClassificationResult(WorkItemIntent.MCP_ONBOARD, "Onboard Model Context Protocol server", confidence=0.9)
        if any(w in cleaned for w in ("search the web", "look up online", "browse web", "google for", "find on internet")):
            return IntentClassificationResult(WorkItemIntent.RESEARCH, f"Web research: {prompt[:80]}", confidence=0.88)
        if any(w in cleaned for w in ("click on", "look at my screen", "inspect window", "automate desktop")):
            return IntentClassificationResult(WorkItemIntent.DESKTOP_VISION, f"Desktop vision action: {prompt[:80]}", confidence=0.88)
        if any(w in cleaned for w in ("schedule every", "run every day", "recurring task", "cron job", "run every hour")):
            return IntentClassificationResult(WorkItemIntent.SCHEDULE, f"Schedule workflow: {prompt[:80]}", confidence=0.9)

        # 3. Model-Assisted Intent Classification (if available)
        try:
            target_model = model or await self.ollama.resolve_active_model()
            classify_prompt = (
                "You are NEXORA's intent classifier. Determine if the user is asking a conversational question "
                "or requesting an operational task.\n"
                "Return JSON ONLY:\n"
                '{"intent": "answer|task|research|skill_import|mcp_onboard|desktop_vision|schedule", '
                '"summary": "concise description of work to do", "confidence": 0.0-1.0}\n\n'
                f"User Prompt: {prompt}"
            )
            async with self.guard.acquire():
                resp = await self.ollama.generate_chat(
                    ChatRequest(
                        model=target_model,
                        temperature=0.0,
                        messages=[ChatMessage(role="user", content=classify_prompt)],
                    )
                )
            data = extract_json_object(resp.message.content)
            intent_str = str(data.get("intent", "answer")).casefold()
            summary = str(data.get("summary", prompt[:80]))
            confidence = float(data.get("confidence", 0.8))

            for intent_enum in WorkItemIntent:
                if intent_enum.value == intent_str:
                    return IntentClassificationResult(intent_enum, summary, confidence)
        except Exception as exc:
            logger.debug("Model-assisted intent classification fell back: %s", exc)

        # 4. Fallback Default: If imperative action verbs are present, treat as task; else answer
        imperatives = ("create", "build", "run", "make", "execute", "delete", "write", "generate", "start", "stop")
        if any(cleaned.startswith(w) or f" {w} " in cleaned for w in imperatives):
            return IntentClassificationResult(WorkItemIntent.TASK, f"Task: {prompt[:80]}", confidence=0.7)

        return IntentClassificationResult(WorkItemIntent.ANSWER, "Conversational reply", confidence=0.75)
