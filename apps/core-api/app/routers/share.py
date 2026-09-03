"""FastAPI router for playthrough share-link generation."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.connection import get_db_session
from app.db.models.user import User
from app.middleware.auth import get_current_user
from app.models.share import ShareCreate, ShareResponse
from app.repositories.participant_repo import ParticipantRepo
from app.repositories.playthrough_repo import PlaythroughRepo
from app.repositories.share_repo import ShareRepo
from app.services.share_service import ShareService, build_share_url

router = APIRouter(prefix="/v1/playthroughs", tags=["Sharing"])


def get_share_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ShareService:
    """Dependency injector for ShareService."""
    return ShareService(
        share_repo=ShareRepo(session),
        playthrough_repo=PlaythroughRepo(session),
        participant_repo=ParticipantRepo(session),
    )


@router.post(
    "/{playthrough_id}/share",
    response_model=ShareResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_share(
    playthrough_id: uuid.UUID,
    data: ShareCreate,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ShareService, Depends(get_share_service)],
) -> ShareResponse:
    """Generate (or fetch an existing) spectate or join share link. Participant-only."""
    share = await service.create_share(
        playthrough_id=playthrough_id, mode=data.mode, user_id=user.user_id
    )
    return ShareResponse(
        share_id=share.share_id,
        share_token=share.share_token,
        mode=share.mode,
        playthrough_id=share.playthrough_id,
        url=build_share_url(share),
        created_at=share.created_at,
    )
