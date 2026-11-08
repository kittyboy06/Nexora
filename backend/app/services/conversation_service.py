"""Durable conversation management, streaming replies, and intent handoffs."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any
from fastapi import BackgroundTasks

from backend.app.conversation.intent_classifier import IntentClassifier
from backend.app.core.config import Settings
from backend.app.core.exceptions import ConversationNotFoundException
from backend.app.core.guard import InferenceGuard
from backend.app.core.security_scrubber import scrub_secrets
from backend.app.models.chat import ChatMessage, ChatRequest
from backend.app.models.conversation import (
    AuthorizationState,
    ChatMode,
    Conversation,
    ConversationEvent,
    ConversationMessage,
    ConversationWorkItem,
    WorkItemIntent,
    WorkItemStatus,
)
from backend.app.services.ollama_service import OllamaService

logger = logging.getLogger("nexora.conversation.service")

DEFAULT_CHAT_SYSTEM_INSTRUCTION = (
    "You are NEXORA, a privacy-first autonomous local AI assistant. "
    "Provide helpful, direct, and conversational responses. "
    "Do not invent task commands or format output as task plans unless explicitly instructed."
)


class ConversationService:
    """Manages persistent conversations, messages, and work-item creation."""

    def __init__(
        self,
        settings: Settings,
        ollama: OllamaService,
        guard: InferenceGuard,
        intent_classifier: IntentClassifier,
        task_manager: Any = None,
    ):
        self.settings = settings
        self.ollama = ollama
        self.guard = guard
        self.intent_classifier = intent_classifier
        self.task_manager = task_manager
        self.data_dir = settings.get_conversation_data_dir()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._conversations: dict[str, Conversation] = {}
        self._lock = asyncio.Lock()
        self._active_tasks: dict[str, asyncio.Task] = {}

    def _persist_atomic(self, conv: Conversation) -> None:
        """Write conversation state atomically to disk."""
        conv_file = self.data_dir / f"{conv.conversation_id}.json"
        tmp_file = self.data_dir / f"{conv.conversation_id}.json.tmp"
        try:
            tmp_file.write_text(conv.model_dump_json(indent=2), encoding="utf-8")
            tmp_file.replace(conv_file)
        except Exception as exc:
            logger.error("Failed to persist conversation %s: %s", conv.conversation_id, exc)
            if tmp_file.exists():
                tmp_file.unlink(missing_ok=True)
            raise

    async def _load_from_disk(self, conversation_id: str) -> Conversation:
        """Load conversation from disk if not present in memory."""
        conv_file = self.data_dir / f"{conversation_id}.json"
        if not conv_file.exists():
            raise ConversationNotFoundException(conversation_id)
        try:
            data = json.loads(conv_file.read_text(encoding="utf-8"))
            conv = Conversation.model_validate(data)
            self._conversations[conversation_id] = conv
            return conv
        except Exception as exc:
            logger.error("Failed reading conversation file %s: %s", conv_file, exc)
            raise ConversationNotFoundException(conversation_id, details={"error": str(exc)})

    async def list_conversations(self) -> list[Conversation]:
        """List all non-archived conversations sorted by updated_at descending."""
        async with self._lock:
            # Discover any files on disk not yet loaded
            for f in self.data_dir.glob("conv_*.json"):
                cid = f.stem
                if cid not in self._conversations:
                    try:
                        await self._load_from_disk(cid)
                    except Exception:
                        pass

            active = [c for c in self._conversations.values() if not c.archived]
            active.sort(key=lambda c: c.updated_at, reverse=True)
            return active

    async def get_conversation(self, conversation_id: str) -> Conversation:
        """Retrieve a conversation by ID."""
        async with self._lock:
            if conversation_id in self._conversations:
                return self._conversations[conversation_id]
            return await self._load_from_disk(conversation_id)

    async def create_conversation(self, title: str | None = None) -> Conversation:
        """Create and persist a new conversation."""
        async with self._lock:
            conv = Conversation(title=title or "New Conversation")
            self._conversations[conv.conversation_id] = conv
            self._persist_atomic(conv)
            logger.info("Created conversation %s", conv.conversation_id)
            return conv

    async def delete_conversation(self, conversation_id: str) -> bool:
        """Archive and delete a conversation from active memory."""
        async with self._lock:
            conv = self._conversations.get(conversation_id)
            if not conv:
                try:
                    conv = await self._load_from_disk(conversation_id)
                except ConversationNotFoundException:
                    return False
            conv.archived = True
            self._persist_atomic(conv)
            self._conversations.pop(conversation_id, None)
            conv_file = self.data_dir / f"{conversation_id}.json"
            if conv_file.exists():
                conv_file.unlink(missing_ok=True)
            logger.info("Deleted conversation %s", conversation_id)
            return True

    async def process_user_turn(
        self,
        conversation_id: str,
        content: str,
        mode: ChatMode = ChatMode.AUTO,
        model_override: str | None = None,
        background_tasks: BackgroundTasks | None = None,
    ) -> tuple[ConversationMessage, ConversationWorkItem | None]:
        """Record user message, classify intent, execute action or reply, and record turn."""
        conv = await self.get_conversation(conversation_id)

        scrubbed_content = scrub_secrets(content.strip())
        user_msg = ConversationMessage(
            conversation_id=conversation_id,
            role="user",
            content=scrubbed_content,
            mode=mode,
            model=model_override,
        )

        async with self._lock:
            conv.messages.append(user_msg)
            # Update title from first user message if still default
            if conv.title == "New Conversation":
                words = scrubbed_content.split()[:5]
                conv.title = " ".join(words) if words else "Conversation"
            conv.updated_at = user_msg.created_at
            self._persist_atomic(conv)

        # 1. Classify Intent
        classification = await self.intent_classifier.classify(
            scrubbed_content, mode=mode, model=model_override
        )
        logger.info(
            "Classified intent for %s: %s (confidence: %.2f)",
            conversation_id, classification.intent.value, classification.confidence
        )

        assistant_msg: ConversationMessage
        created_work_item: ConversationWorkItem | None = None

        target_model = model_override or await self.ollama.resolve_active_model()

        # 2. Handle Intent
        if classification.intent == WorkItemIntent.ANSWER:
            # Conversational Response
            messages_payload = [ChatMessage(role="system", content=DEFAULT_CHAT_SYSTEM_INSTRUCTION)]
            # Include last 6 turns for context
            for m in conv.messages[-6:]:
                messages_payload.append(ChatMessage(role=m.role, content=m.content))

            async with self.guard.acquire():
                resp = await self.ollama.generate_chat(
                    ChatRequest(
                        model=target_model,
                        temperature=0.7,
                        messages=messages_payload,
                    )
                )

            reply_text = scrub_secrets(resp.message.content)
            assistant_msg = ConversationMessage(
                conversation_id=conversation_id,
                role="assistant",
                content=reply_text,
                mode=mode,
                model=target_model,
            )

        elif classification.intent == WorkItemIntent.TASK:
            # Actionable Task
            created_work_item = ConversationWorkItem(
                conversation_id=conversation_id,
                source_message_id=user_msg.message_id,
                intent=WorkItemIntent.TASK,
                target_module="tasks",
                summary=classification.summary,
                status=WorkItemStatus.RUNNING,
                authorization_state=AuthorizationState.NONE,
            )

            task_id = "pending_task"
            if self.task_manager and background_tasks is not None:
                try:
                    agent_task = await self.task_manager.create_and_start_task(
                        scrubbed_content,
                        background_tasks=background_tasks,
                        model_profile_id=model_override,
                    )
                    task_id = agent_task.task_id
                    created_work_item.target_id = task_id
                except Exception as exc:
                    logger.warning("Failed to start background task for work item: %s", exc)
                    created_work_item.status = WorkItemStatus.FAILED
                    created_work_item.summary += f" (Creation failed: {exc})"

            reply_text = (
                f"I've initiated an operational task (**{task_id}**): {classification.summary}.\n\n"
                "You can monitor its plan and step approvals directly in the work card below or on the Tasks page."
            )
            assistant_msg = ConversationMessage(
                conversation_id=conversation_id,
                role="assistant",
                content=reply_text,
                mode=mode,
                model=target_model,
                work_item_ids=[created_work_item.work_item_id],
            )

        else:
            # Other Modules (Research, Skill Import, MCP Onboarding, Desktop Vision, Scheduler)
            module_map = {
                WorkItemIntent.RESEARCH: "research",
                WorkItemIntent.SKILL_IMPORT: "skills",
                WorkItemIntent.MCP_ONBOARD: "mcp",
                WorkItemIntent.DESKTOP_VISION: "vision",
                WorkItemIntent.SCHEDULE: "scheduler",
            }
            target_module = module_map.get(classification.intent, "tasks")

            created_work_item = ConversationWorkItem(
                conversation_id=conversation_id,
                source_message_id=user_msg.message_id,
                intent=classification.intent,
                target_module=target_module,
                summary=classification.summary,
                status=WorkItemStatus.DRAFT,
                authorization_state=AuthorizationState.CONFIRMATION_NEEDED,
            )

            reply_text = (
                f"I've created a {target_module.upper()} work item: **{classification.summary}**.\n\n"
                f"Review the configuration and required authorizations in the card below to proceed."
            )
            assistant_msg = ConversationMessage(
                conversation_id=conversation_id,
                role="assistant",
                content=reply_text,
                mode=mode,
                model=target_model,
                work_item_ids=[created_work_item.work_item_id],
            )

        # 3. Persist Turn and Work Item
        async with self._lock:
            if created_work_item:
                conv.work_items.append(created_work_item)
            conv.messages.append(assistant_msg)
            conv.updated_at = assistant_msg.created_at
            self._persist_atomic(conv)

        return assistant_msg, created_work_item

    async def record_event(self, event: ConversationEvent) -> None:
        """Record an operational lifecycle event and update work item if linked."""
        async with self._lock:
            conv = self._conversations.get(event.conversation_id)
            if not conv:
                try:
                    conv = await self._load_from_disk(event.conversation_id)
                except ConversationNotFoundException:
                    return

            if event.work_item_id:
                item = next((w for w in conv.work_items if w.work_item_id == event.work_item_id), None)
                if item:
                    # Sync work item status based on event
                    if event.event_type == "task_completed":
                        item.status = WorkItemStatus.COMPLETED
                    elif event.event_type == "task_failed":
                        item.status = WorkItemStatus.FAILED
                    elif event.event_type == "task_cancelled":
                        item.status = WorkItemStatus.CANCELLED
                    elif event.event_type == "approval_required":
                        item.status = WorkItemStatus.WAITING_APPROVAL
                        item.authorization_state = AuthorizationState.APPROVAL_PENDING
                    elif event.event_type == "task_approved":
                        item.authorization_state = AuthorizationState.APPROVED

            self._persist_atomic(conv)
