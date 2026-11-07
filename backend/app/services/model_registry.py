"""Profile catalogue, live Ollama inventory and task-specific routing."""

import json
import logging
import sys
from pathlib import Path

from backend.app.core.config import Settings
from backend.app.core.exceptions import ModelNotFoundException
from backend.app.core.guard import InferenceGuard
from backend.app.core.json_utils import extract_json_object
from backend.app.models.chat import ChatMessage, ChatRequest
from backend.app.models.model_profile import (
    ModelProfile,
    ModelProfileCatalogue,
    ModelProfileListResponse,
    ModelProfileStatus,
    RouteSelection,
    TaskKind,
)
from backend.app.services.model_provider import ModelProvider

logger = logging.getLogger("nexora.model_registry")


class ModelProfileRegistry:
    """Loads editable profiles and filters them against the live local inventory."""

    def __init__(self, settings: Settings):
        self.path = settings.get_model_profiles_file()
        self.settings = settings
        self.catalogue = self._load()
        self._ensure_primary_fallback(self.catalogue)

    def _ensure_primary_fallback(self, catalogue: ModelProfileCatalogue) -> None:
        """Preserve pre-registry behavior when users configure a different primary model."""
        target_model = self.settings.OLLAMA_MODEL
        if not target_model:
            return
        if not any(profile.enabled and (profile.model in (target_model, "auto", "")) for profile in catalogue.profiles):
            fallback_id = "default-primary"
            existing_ids = {profile.profile_id for profile in catalogue.profiles}
            suffix = 2
            while fallback_id in existing_ids:
                fallback_id = f"default-primary-{suffix}"
                suffix += 1
            catalogue.profiles.append(ModelProfile(
                profile_id=fallback_id,
                model=target_model,
                specialties=[TaskKind.GENERAL],
                system_instruction="",
                role="planner",
                enabled=True,
            ))

    def reload(self) -> ModelProfileCatalogue:
        """Reload the profile catalogue from disk and refresh in-memory state."""
        catalogue = self._load()
        self._ensure_primary_fallback(catalogue)
        self.catalogue = catalogue
        logger.info("Reloaded %d model profiles from %s", len(self.catalogue.profiles), self.path)
        return self.catalogue

    def _load(self) -> ModelProfileCatalogue:
        try:
            if self.path.exists():
                data = json.loads(self.path.read_text(encoding="utf-8"))
                catalogue = ModelProfileCatalogue.model_validate(data)
                ids = [profile.profile_id for profile in catalogue.profiles]
                if len(ids) != len(set(ids)):
                    raise RuntimeError(f"Duplicate profile_id in model profile catalogue: {self.path}")
                return catalogue
        except Exception as exc:
            logger.warning("Could not load model profiles from %s: %s", self.path, exc)

        # Check PyInstaller bundle
        if getattr(sys, "frozen", False):
            try:
                meipass = getattr(sys, "_MEIPASS", "")
                if meipass:
                    bundled = Path(meipass) / "data" / "model_profiles.json"
                    if bundled.exists():
                        data = json.loads(bundled.read_text(encoding="utf-8"))
                        return ModelProfileCatalogue.model_validate(data)
            except Exception as exc:
                logger.warning("Could not load bundled model profiles: %s", exc)

        # Built-in fallback default profiles
        return ModelProfileCatalogue(profiles=[
            ModelProfile(
                profile_id="router",
                model="auto",
                specialties=[TaskKind.GENERAL],
                system_instruction="Classify task intent and return the requested routing JSON only.",
                role="router",
                enabled=True,
            ),
            ModelProfile(
                profile_id="general-planner",
                model="auto",
                specialties=[TaskKind.GENERAL],
                system_instruction="Create concise, tool-grounded plans and do not assume tools that are not listed.",
                role="planner",
                enabled=True,
            ),
            ModelProfile(
                profile_id="coding-planner",
                model="auto",
                specialties=[TaskKind.CODE],
                system_instruction="For coding goals, plan small, verifiable steps and use only registered tools.",
                role="planner",
                enabled=True,
            ),
            ModelProfile(
                profile_id="research-planner",
                model="auto",
                specialties=[TaskKind.RESEARCH],
                system_instruction="For research goals, identify evidence needs and use only registered tools.",
                role="planner",
                enabled=True,
            ),
            ModelProfile(
                profile_id="reasoning-planner",
                model="auto",
                specialties=[TaskKind.REASONING],
                system_instruction="For analytical goals, decompose dependencies and validate each conclusion.",
                role="planner",
                enabled=True,
            ),
        ])

    async def list_profiles(self, ollama: ModelProvider) -> ModelProfileListResponse:
        installed = [item.name for item in await ollama.list_models()]
        profiles = [
            ModelProfileStatus(**profile.model_dump(), installed=ollama.model_matches(profile.model, installed))
            for profile in self.catalogue.profiles if profile.enabled
        ]
        return ModelProfileListResponse(profiles=profiles, count=len(profiles))

    def profile(self, profile_id: str) -> ModelProfile:
        profile = next((p for p in self.catalogue.profiles if p.profile_id == profile_id and p.enabled), None)
        if profile is None:
            raise ModelNotFoundException(model_name=f"profile:{profile_id}")
        return profile


class HybridModelRouter:
    """Classify with a lightweight model, escalate uncertain routes, then pick a profile."""

    def __init__(self, profiles: ModelProfileRegistry, settings: Settings, ollama: ModelProvider, guard: InferenceGuard):
        self.profiles = profiles
        self.settings = settings
        self.ollama = ollama
        self.guard = guard

    async def route(self, task: str, profile_override: str | None = None) -> RouteSelection:
        inventory = [item.name for item in await self.ollama.list_models()]
        available = [
            profile for profile in self.profiles.catalogue.profiles
            if profile.enabled and self.ollama.model_matches(profile.model, inventory)
        ]
        if profile_override:
            profile = self.profiles.profile(profile_override)
            if not self.ollama.model_matches(profile.model, inventory):
                raise ModelNotFoundException(model_name=profile.model, details={"profile_id": profile.profile_id})
            kind = next(iter(profile.specialties), TaskKind.GENERAL)
            actual_model = profile.model
            if actual_model in ("auto", "", "default"):
                actual_model = await self.ollama.resolve_active_model()
            return RouteSelection(profile_id=profile.profile_id, model=actual_model, task_kind=kind,
                                  reason="manual profile override")

        router_model = self.settings.MODEL_ROUTER_MODEL
        if not router_model or not self.ollama.model_matches(router_model, inventory):
            router_model = self.settings.OLLAMA_MODEL
        if not router_model or not self.ollama.model_matches(router_model, inventory):
            router_model = await self.ollama.resolve_active_model()

        kind, confidence = await self._classify(task, router_model)
        escalated = False
        if kind is None or confidence < self.settings.MODEL_ROUTER_CONFIDENCE_THRESHOLD:
            fallback_model = self.settings.OLLAMA_MODEL or router_model
            if fallback_model != router_model and self.ollama.model_matches(fallback_model, inventory):
                escalated = True
                kind, confidence = await self._classify(task, fallback_model)
                if confidence < self.settings.MODEL_ROUTER_CONFIDENCE_THRESHOLD:
                    kind = None
            else:
                # The default configuration may use one model for both roles; do not repeat its call.
                kind = None
        if kind is None:
            kind = self._fallback_kind(task)
            reason = "capability fallback after uncertain classification"
        else:
            reason = "hybrid task classification"

        selected = next((p for p in available if kind in p.specialties and p.role != "router"), None)
        if selected is None:
            selected = next((p for p in available if TaskKind.GENERAL in p.specialties and p.role != "router"), None)
        if selected is None:
            selected = next((p for p in available if p.role != "router"), None)
        if selected is None:
            raise ModelNotFoundException(
                model_name=self.settings.OLLAMA_MODEL or "auto",
                details={"reason": "No enabled specialist profile references an installed model"},
            )
        actual_model = selected.model
        if actual_model in ("auto", "", "default"):
            actual_model = await self.ollama.resolve_active_model()

        return RouteSelection(profile_id=selected.profile_id, model=actual_model, task_kind=kind,
                              reason=reason, escalated=escalated)

    async def _classify(self, task: str, model: str) -> tuple[TaskKind | None, float]:
        prompt = (
            "Classify this user task. Return JSON only: "
            '{"task_kind":"code|research|reasoning|general","confidence":0.0}. '
            f"Use confidence below {self.settings.MODEL_ROUTER_CONFIDENCE_THRESHOLD:.2f} when unclear. Task: " + task
        )
        try:
            async with self.guard.acquire():
                response = await self.ollama.generate_chat(ChatRequest(
                    model=model,
                    temperature=0.0,
                    messages=[ChatMessage(role="system", content="You route tasks to specialist models."),
                              ChatMessage(role="user", content=prompt)],
                ))
            data = extract_json_object(response.message.content.strip())
            kind = TaskKind(data["task_kind"])
            confidence = float(data["confidence"])
            if not 0.0 <= confidence <= 1.0:
                return None, 0.0
            return kind, confidence
        except Exception as exc:
            logger.info("Model routing classification failed for %s: %s", model, exc)
            return None, 0.0

    @staticmethod
    def _fallback_kind(task: str) -> TaskKind:
        text = task.casefold()
        terms = {
            TaskKind.CODE: ("implement", "code", "debug", "python", "function", "test"),
            TaskKind.RESEARCH: ("research", "search", "sources", "compare", "latest"),
            TaskKind.REASONING: ("analyze", "architecture", "plan", "trade-off", "reason"),
        }
        scores = {kind: sum(token in text for token in tokens) for kind, tokens in terms.items()}
        best = max(scores, key=scores.get)
        return best if scores[best] else TaskKind.GENERAL
