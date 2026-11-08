"""Unit tests for Phase 15 Conversation and WorkItem data contracts."""

import json
from datetime import datetime, timezone
import pytest

from backend.app.core.security_scrubber import scrub_secrets
from backend.app.models.conversation import (
    AuthorizationState,
    ChatMode,
    Conversation,
    ConversationCreateRequest,
    ConversationEvent,
    ConversationMessage,
    ConversationMessageRequest,
    ConversationMessageResponse,
    ConversationWorkItem,
    WorkItemIntent,
    WorkItemStatus,
)


def test_conversation_work_item_defaults():
    item = ConversationWorkItem(
        conversation_id="conv_123",
        source_message_id="msg_456",
        intent=WorkItemIntent.TASK,
        target_module="tasks",
        summary="Create a new microservice",
    )
    assert item.work_item_id.startswith("work_")
    assert item.status == WorkItemStatus.DRAFT
    assert item.authorization_state == AuthorizationState.NONE
    assert item.evidence_refs == []
    assert isinstance(item.created_at, datetime)
    assert isinstance(item.updated_at, datetime)


def test_conversation_roundtrip_serialization():
    conv = Conversation(title="Planning System Architecture")
    msg1 = ConversationMessage(
        conversation_id=conv.conversation_id,
        role="user",
        content="Deploy calculator app",
        mode=ChatMode.TASK,
    )
    work = ConversationWorkItem(
        conversation_id=conv.conversation_id,
        source_message_id=msg1.message_id,
        intent=WorkItemIntent.TASK,
        target_module="tasks",
        target_id="task_calc_1",
        summary="Launch calculator workflow",
        status=WorkItemStatus.RUNNING,
    )
    msg1.work_item_ids.append(work.work_item_id)
    conv.messages.append(msg1)
    conv.work_items.append(work)

    json_str = conv.model_dump_json()
    data = json.loads(json_str)

    restored = Conversation.model_validate(data)
    assert restored.conversation_id == conv.conversation_id
    assert restored.title == "Planning System Architecture"
    assert len(restored.messages) == 1
    assert restored.messages[0].content == "Deploy calculator app"
    assert restored.messages[0].mode == ChatMode.TASK
    assert len(restored.work_items) == 1
    assert restored.work_items[0].target_id == "task_calc_1"
    assert restored.work_items[0].status == WorkItemStatus.RUNNING


def test_conversation_event_model():
    evt = ConversationEvent(
        conversation_id="conv_100",
        work_item_id="work_200",
        event_type="task_completed",
        payload={"task_id": "task_abc", "steps_succeeded": 3},
    )
    assert evt.event_id.startswith("evt_")
    assert evt.event_type == "task_completed"
    assert evt.payload["steps_succeeded"] == 3


def test_redaction_boundary_scrubs_secrets():
    raw_prompt = "My api key is sk-1234567890abcdef12345678 and token is ghp_12345678901234567890123456789012"
    scrubbed = scrub_secrets(raw_prompt)
    assert "sk-" not in scrubbed
    assert "ghp_" not in scrubbed
    assert "[REDACTED_SECRET]" in scrubbed
