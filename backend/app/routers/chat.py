import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.routers.dependencies import AuthContext, RequireViewer
from app.schemas.chat import (
    ConversationDetailOut,
    ConversationOut,
    CreateConversationRequest,
    MessageOut,
    SendMessageRequest,
    UpdateConversationRequest,
)
from app.schemas.common import MessageResponse, PaginatedResponse
from app.services.rag.rag_service import RAGService

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("/conversations", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    request: CreateConversationRequest = CreateConversationRequest(),
    context: AuthContext = Depends(RequireViewer),
    db: AsyncSession = Depends(get_db),
):
    """Create a new chat conversation for the authenticated organization and user."""
    return await RAGService.create_conversation(
        db=db,
        org_id=context.organization_id,
        user_id=context.user.id,
        title=request.title,
    )


@router.get("/conversations", response_model=PaginatedResponse[ConversationOut])
async def list_conversations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    context: AuthContext = Depends(RequireViewer),
    db: AsyncSession = Depends(get_db),
):
    """List recent conversations for the current user in the active organization."""
    return await RAGService.list_conversations(
        db=db,
        org_id=context.organization_id,
        user_id=context.user.id,
        page=page,
        page_size=page_size,
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationDetailOut)
async def get_conversation(
    conversation_id: uuid.UUID,
    context: AuthContext = Depends(RequireViewer),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve full conversation details with ordered messages and citations."""
    return await RAGService.get_conversation(
        db=db,
        org_id=context.organization_id,
        conversation_id=conversation_id,
    )


@router.patch("/conversations/{conversation_id}", response_model=ConversationOut)
async def update_conversation(
    conversation_id: uuid.UUID,
    request: UpdateConversationRequest,
    context: AuthContext = Depends(RequireViewer),
    db: AsyncSession = Depends(get_db),
):
    """Update conversation title."""
    return await RAGService.update_conversation_title(
        db=db,
        org_id=context.organization_id,
        conversation_id=conversation_id,
        title=request.title,
    )


@router.delete("/conversations/{conversation_id}", response_model=MessageResponse)
async def delete_conversation(
    conversation_id: uuid.UUID,
    context: AuthContext = Depends(RequireViewer),
    db: AsyncSession = Depends(get_db),
):
    """Delete a conversation and all its messages."""
    await RAGService.delete_conversation(
        db=db,
        org_id=context.organization_id,
        conversation_id=conversation_id,
    )
    return MessageResponse(message="Conversation deleted successfully.")


@router.post("/conversations/{conversation_id}/messages", response_model=MessageOut)
async def send_message(
    conversation_id: uuid.UUID,
    request: SendMessageRequest,
    context: AuthContext = Depends(RequireViewer),
    db: AsyncSession = Depends(get_db),
):
    """
    Send a user message, retrieve grounded document context, and generate a cited response (synchronous).
    """
    return await RAGService.send_message(
        db=db,
        org_id=context.organization_id,
        user_id=context.user.id,
        conversation_id=conversation_id,
        request=request,
    )


@router.post("/conversations/{conversation_id}/messages/stream")
async def stream_message(
    conversation_id: uuid.UUID,
    request: SendMessageRequest,
    context: AuthContext = Depends(RequireViewer),
    db: AsyncSession = Depends(get_db),
):
    """
    Stream assistant response token-by-token using Server-Sent Events (SSE).
    Emits events: retrieval_status, sources, delta, done, error.
    """
    return StreamingResponse(
        RAGService.stream_message(
            db=db,
            org_id=context.organization_id,
            user_id=context.user.id,
            conversation_id=conversation_id,
            request=request,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
