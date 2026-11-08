"""Data models for Phase 15 Chat-First Experience and Conversation Handoffs."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
import re
from typing import Any
from uuid import uuid4
from pydantic import BaseModel, Field, field_validator


class ChatMode(str, Enum):
    AUTO = "auto"
    ANSWER_ONLY = "answer_only"
    TASK = "task"
    RESEARCH = "research"
    DESKTOP_VISION = "desktop_vision"
    SCHEDULE = "schedule"


class WorkItemIntent(str, Enum):
    ANSWER = "answer"
    TASK = "task"
    RESEARCH = "research"
    SKILL_IMPORT = "skill_import"
    MCP_ONBOARD = "mcp_onboard"
    DESKTOP_VISION = "desktop_vision"
    SCHEDULE = "schedule"


class WorkItemStatus(str, Enum):
    DRAFT = "draft"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AuthorizationState(str, Enum):
    NONE = "none"
    CONFIRMATION_NEEDED = "confirmation_needed"
    APPROVAL_PENDING = "approval_pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ConversationWorkItem(BaseModel):
    """Binds a conversation turn to a specific background operational module."""
    work_item_id: str = Field(default_factory=lambda: f"work_{uuid4().hex[:12]}")
    conversation_id: str
    source_message_id: str
    intent: WorkItemIntent
    target_module: str = Field(..., description="Destination module: tasks, skills, mcp, research, vision, scheduler")
    target_id: str | None = Field(None, description="Created entity ID: task_id, server_id, session_id, etc.")
    status: WorkItemStatus = Field(default=WorkItemStatus.DRAFT)
    summary: str = Field(..., description="Plain-language description shown on the work card")
    routing: dict[str, Any] | None = Field(None, description="Routing metadata (model, profile, reason, escalation)")
    authorization_state: AuthorizationState = Field(default=AuthorizationState.NONE)
    evidence_refs: list[str] = Field(default_factory=list, description="IDs of evidence/screenshots/audits created")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ConversationMessage(BaseModel):
    """An individual message turn within a persistent conversation."""
    message_id: str = Field(default_factory=lambda: f"msg_{uuid4().hex[:12]}")
    conversation_id: str
    role: str = Field(..., description="Role: user, assistant, system")
    content: str = Field(..., description="Message text (Markdown sanitized)")
    mode: ChatMode = Field(default=ChatMode.AUTO)
    model: str | None = None
    routing: dict[str, Any] | None = None
    work_item_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("mode", mode="before")
    @classmethod
    def normalize_mode(cls, v: Any) -> Any:
        if isinstance(v, str):
            s = re.sub(r"(?<!^)(?=[A-Z])", "_", v).lower()
            return s
        return v


class ConversationEvent(BaseModel):
    """Lifecycle event emitted by an operational module back into a conversation."""
    event_id: str = Field(default_factory=lambda: f"evt_{uuid4().hex[:12]}")
    conversation_id: str
    work_item_id: str | None = None
    event_type: str = Field(..., description="Event type: task_updated, approval_required, task_completed, etc.")
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Conversation(BaseModel):
    """Persistent chat conversation container."""
    conversation_id: str = Field(default_factory=lambda: f"conv_{uuid4().hex[:12]}")
    title: str = "New Conversation"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    archived: bool = False
    messages: list[ConversationMessage] = Field(default_factory=list)
    work_items: list[ConversationWorkItem] = Field(default_factory=list)


# --- API Request & Response DTOs ---

class ConversationCreateRequest(BaseModel):
    title: str | None = None


class ConversationMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, description="Message prompt content")
    mode: ChatMode = Field(default=ChatMode.AUTO)
    model_override: str | None = None

    @field_validator("mode", mode="before")
    @classmethod
    def normalize_mode(cls, v: Any) -> Any:
        if isinstance(v, str):
            s = re.sub(r"(?<!^)(?=[A-Z])", "_", v).lower()
            return s
        return v


class ConversationResponse(BaseModel):
    conversation: Conversation


class ConversationListResponse(BaseModel):
    conversations: list[Conversation]
    count: int


class ConversationMessageResponse(BaseModel):
    message: ConversationMessage
    work_item: ConversationWorkItem | None = None
