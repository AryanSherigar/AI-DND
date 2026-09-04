"""FastAPI router for the Studio AI Assistant chat endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse

from app.middleware.auth import get_current_user
from app.models.assistant import AssistantChatRequest
from app.models.auth import CurrentUser
from app.services.assistant_service import stream_assistant_chat

router = APIRouter(prefix="/v1/studio", tags=["Studio Assistant"])


@router.post("/assistant", response_model=None)
async def chat_with_assistant(
    request: AssistantChatRequest,
    _user: Annotated[CurrentUser, Depends(get_current_user)],
) -> EventSourceResponse:
    """Stream studio world-building assistant guidance over SSE."""
    return EventSourceResponse(stream_assistant_chat(request))
