import json
import logging
from typing import Any
from pydantic import BaseModel, Field

from backend.app.core.guard import InferenceGuard
from backend.app.models.agent import AgentTask, PlanStep, StepResult, ToolCall
from backend.app.models.chat import ChatMessage, ChatRequest
from backend.app.services.ollama_service import OllamaService
from backend.app.tools.registry import ToolRegistry

logger = logging.getLogger("nexora.result_evaluator")


class RecoveryDecision(BaseModel):
    can_recover: bool = Field(..., description="Whether execution can be recovered with a revised tool call")
    explanation: str = Field(..., description="Rationale for the recovery decision")
    revised_tool_call: ToolCall | None = Field(default=None, description="Revised tool call if recoverable")


EVALUATOR_PROMPT = """You are NEXORA's Execution Result Evaluator.
A tool execution has failed after retries. Analyze the failure and determine if the step can be recovered with revised arguments, or if the task should abort.

Task Goal: {goal}
Failed Step: {step_description}
Tool Called: {tool_name}
Tool Arguments: {arguments}
Error Message: {error_message}

Available Tools:
{tools_spec}

Respond with valid JSON adhering to this schema:
{{
  "can_recover": true / false,
  "explanation": "Why this can or cannot be recovered",
  "revised_tool_call": {{
    "tool_name": "tool_name",
    "arguments": {{ ... }}
  }}
}}
"""


class ResultEvaluator:
    """Evaluates failed tool execution logs and queries LLM for recovery suggestions."""

    def __init__(
        self,
        ollama_service: OllamaService,
        registry: ToolRegistry,
        guard: InferenceGuard,
    ):
        self.ollama = ollama_service
        self.registry = registry
        self.guard = guard

    async def evaluate_failure(
        self,
        task: AgentTask,
        step: PlanStep,
        result: StepResult,
    ) -> RecoveryDecision:
        """Prompt LLM to evaluate failure trace and recommend recovery action."""
        prompt = EVALUATOR_PROMPT.format(
            goal=task.plan.goal if task.plan else task.prompt,
            step_description=step.description,
            tool_name=step.tool_call.tool_name,
            arguments=json.dumps(step.tool_call.arguments),
            error_message=result.error or "Unknown failure",
            tools_spec=json.dumps(self.registry.get_specs(), indent=2),
        )

        messages = [
            ChatMessage(role="system", content="You are a strict technical evaluator. Output JSON only."),
            ChatMessage(role="user", content=prompt),
        ]

        try:
            async with self.guard.acquire():
                resp = await self.ollama.generate_chat(
                    ChatRequest(messages=messages, temperature=0.1)
                )

            content = resp.message.content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]

            data = json.loads(content.strip())
            return RecoveryDecision(**data)
        except Exception as exc:
            logger.warning("Result evaluator failed to parse LLM recovery response: %s", exc)
            return RecoveryDecision(
                can_recover=False,
                explanation=f"Automatic failure recovery could not be formulated: {exc}",
                revised_tool_call=None,
            )
