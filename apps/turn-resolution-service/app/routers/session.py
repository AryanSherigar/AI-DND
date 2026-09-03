"""FastAPI router for multiplayer notifications and spectator streaming."""

import asyncio
import uuid
from collections.abc import AsyncIterator, Callable
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse, ServerSentEvent

from app.db.connection import get_db_session
from app.middleware.auth import get_current_user
from app.models.auth import CurrentUser
from app.session import access, notification_manager, spectator_manager

router = APIRouter(prefix="/v1/session", tags=["Session"])
logger = structlog.get_logger()

EVENT_SPECTATE_STREAM_OPENED = "spectate_stream_opened"
EVENT_NOTIFICATION_STREAM_OPENED = "notification_stream_opened"


@router.get("/{playthrough_id}/spectate", response_model=None)
async def spectate(
    playthrough_id: uuid.UUID,
    share_token: Annotated[str, Query()],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> EventSourceResponse:
    """Read-only live narration stream, gated on a valid spectate share token."""
    await access.validate_spectate_access(playthrough_id, share_token, session)
    logger.info(EVENT_SPECTATE_STREAM_OPENED, playthrough_id=str(playthrough_id))
    queue = spectator_manager.subscribe(playthrough_id)
    return EventSourceResponse(
        _relay(queue, lambda: spectator_manager.unsubscribe(playthrough_id, queue))
    )


@router.get("/{playthrough_id}/notifications", response_model=None)
async def notifications(
    playthrough_id: uuid.UUID,
    participant_id: Annotated[uuid.UUID, Query()],
    user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> EventSourceResponse:
    """Persistent SSE channel for 'your_turn' notifications in multiplayer play."""
    await access.validate_notification_access(
        playthrough_id, participant_id, user.user_id, session
    )
    logger.info(EVENT_NOTIFICATION_STREAM_OPENED, playthrough_id=str(playthrough_id))
    queue = notification_manager.subscribe(playthrough_id, participant_id)
    return EventSourceResponse(
        _relay(
            queue,
            lambda: notification_manager.unsubscribe(playthrough_id, participant_id),
        )
    )


async def _relay(
    queue: asyncio.Queue, on_disconnect: Callable[[], None]
) -> AsyncIterator[ServerSentEvent]:
    """Drain a subscriber queue as SSE events, unsubscribing on disconnect."""
    try:
        while True:
            event_name, data = await queue.get()
            yield ServerSentEvent(event=event_name, data=data)
    finally:
        on_disconnect()
