import json
import logging
from typing import Any
from uuid import uuid4

from backend.app.agent.plan_validator import PlanValidator
from backend.app.core.config import Settings
from backend.app.core.exceptions import PlanValidationException
from backend.app.core.guard import InferenceGuard
from backend.app.models.agent import TaskPlan
from backend.app.models.chat import ChatMessage, ChatRequest
from backend.app.services.ollama_service import OllamaService
from backend.app.tools.registry import ToolRegistry

logger = logging.getLogger("nexora.planner")

PLANNER_SYSTEM_PROMPT = """You are NEXORA's Autonomous Task Planner.
Your job is to break down the user's objective into a structured, step-by-step TaskPlan.

You MUST follow these rules strictly:
1. Output valid JSON only, adhering to the TaskPlan schema.
2. Select only from the registered tools provided below.
3. Keep the plan focused and minimal (maximum 10 steps).
4. Step IDs must be sequential positive integers starting from 1.
5. If a step depends on previous steps, list their step IDs in "dependencies". Dependencies must precede the step.
6. Provide valid, well-formed arguments matching each tool's parameter schema.

Available Tools:
{tools_spec}

Expected JSON Schema:
{{
  "plan_id": "plan_<id>",
  "goal": "Description of overall goal",
  "steps": [
    {{
      "step_id": 1,
      "description": "Clear explanation of this step",
      "tool_call": {{
        "tool_name": "tool_name_here",
        "arguments": {{ ... }}
      }},
      "dependencies": []
    }}
  ]
}}
"""


class Planner:
    """Generates structured plans using Ollama with self-correction retry."""

    def __init__(
        self,
        ollama_service: OllamaService,
        validator: PlanValidator,
        registry: ToolRegistry,
        settings: Settings,
        guard: InferenceGuard,
    ):
        self.ollama = ollama_service
        self.validator = validator
        self.registry = registry
        self.settings = settings
        self.guard = guard

    def _build_system_prompt(self) -> str:
        tools_spec = json.dumps(self.registry.get_specs(), indent=2)
        return PLANNER_SYSTEM_PROMPT.format(tools_spec=tools_spec)

    async def generate_plan(self, prompt: str) -> TaskPlan:
        """Generate, validate, and return a TaskPlan with up to 1 self-correction retry."""
        system_prompt = self._build_system_prompt()
        messages = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=f"Generate a task plan for this objective: {prompt}"),
        ]

        last_error = ""
        for attempt in range(1, self.settings.MAX_PLANNING_ATTEMPTS + 1):
            logger.info("Generating task plan (attempt %d of %d)", attempt, self.settings.MAX_PLANNING_ATTEMPTS)

            if attempt > 1:
                # Inject corrective feedback
                messages.append(
                    ChatMessage(
                        role="user",
                        content=f"Your previous plan was invalid with error: {last_error}. Please correct the plan and return valid JSON.",
                    )
                )

            # Enforce GPU inference lock
            async with self.guard.acquire():
                chat_resp = await self.ollama.generate_chat(
                    ChatRequest(
                        messages=messages,
                        model=self.settings.OLLAMA_MODEL,
                        temperature=0.2,  # Low temperature for deterministic planning
                    )
                )

            content = chat_resp.message.content.strip()
            # Parse JSON
            try:
                # Strip markdown fences if present
                if content.startswith("```json"):
                    content = content[7:]
                if content.endswith("```"):
                    content = content[:-3]
                raw_json = json.loads(content.strip())
                if "plan_id" not in raw_json:
                    raw_json["plan_id"] = f"plan_{uuid4().hex[:8]}"

                plan = TaskPlan(**raw_json)
                # Run complete Python validation
                validated_plan = self.validator.validate(plan)
                return validated_plan
            except (json.JSONDecodeError, Exception) as exc:
                last_error = str(exc)
                logger.warning("Planning attempt %d failed: %s", attempt, last_error)

        raise PlanValidationException(
            message=f"Failed to generate a valid plan after {self.settings.MAX_PLANNING_ATTEMPTS} attempts: {last_error}",
            details={"prompt": prompt, "last_error": last_error},
        )
