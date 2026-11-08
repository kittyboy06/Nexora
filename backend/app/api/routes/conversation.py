"""REST API routes for persistent Chat-First conversations and work-item creation."""

from fastapi import APIRouter, BackgroundTasks, Depends, status

from backend.app.api.dependencies import get_conversation_service
from backend.app.models.conversation import (
    ConversationCreateRequest,
    ConversationListResponse,
    ConversationMessageRequest,
    ConversationMessageResponse,
    ConversationResponse,
)
from backend.app.services.conversation_service import ConversationService

router = APIRouter(prefix="/conversations", tags=["Conversations"])


@router.get("", response_model=ConversationListResponse, summary="List all active conversations")
async def list_conversations(
    service: ConversationService = Depends(get_conversation_service),
) -> ConversationListResponse:
    """Return all non-archived conversations sorted by updated_at descending."""
    convs = await service.list_conversations()
    return ConversationListResponse(conversations=convs, count=len(convs))


@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED, summary="Create new conversation")
async def create_conversation(
    payload: ConversationCreateRequest,
    service: ConversationService = Depends(get_conversation_service),
) -> ConversationResponse:
    """Create a new persistent conversation."""
    conv = await service.create_conversation(title=payload.title)
    return ConversationResponse(conversation=conv)


@router.get("/{conversation_id}", response_model=ConversationResponse, summary="Get conversation transcript and work items")
async def get_conversation(
    conversation_id: str,
    service: ConversationService = Depends(get_conversation_service),
) -> ConversationResponse:
    """Get full message transcript and associated work items for a conversation."""
    conv = await service.get_conversation(conversation_id)
    return ConversationResponse(conversation=conv)


@router.delete("/{conversation_id}", summary="Delete conversation")
async def delete_conversation(
    conversation_id: str,
    service: ConversationService = Depends(get_conversation_service),
) -> dict[str, str]:
    """Delete or archive a conversation."""
    success = await service.delete_conversation(conversation_id)
    return {"status": "ok" if success else "not_found"}


@router.post("/{conversation_id}/messages", response_model=ConversationMessageResponse, summary="Submit message to conversation")
async def post_message(
    conversation_id: str,
    payload: ConversationMessageRequest,
    background_tasks: BackgroundTasks,
    service: ConversationService = Depends(get_conversation_service),
) -> ConversationMessageResponse:
    """
    Process a user message turn within a conversation.
    Classifies intent and either returns a direct conversational response
    or creates and dispatches an operational work item.
    """
    assistant_msg, work_item = await service.process_user_turn(
        conversation_id=conversation_id,
        content=payload.content,
        mode=payload.mode,
        model_override=payload.model_override,
        background_tasks=background_tasks,
    )
    return ConversationMessageResponse(message=assistant_msg, work_item=work_item)
