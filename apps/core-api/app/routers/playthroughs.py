"""FastAPI router for Playthrough endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.connection import get_db_session
from app.db.models.user import User
from app.middleware.auth import get_current_user
from app.models.playthrough import PlaythroughCreate, PlaythroughResponse
from app.repositories.participant_repo import ParticipantRepo
from app.repositories.playthrough_repo import PlaythroughRepo
from app.repositories.scenario_repo import ScenarioRepo
from app.services.playthrough_service import PlaythroughService

router = APIRouter(prefix="/v1/playthroughs", tags=["Playthroughs"])


def get_playthrough_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PlaythroughService:
    """Dependency injector for PlaythroughService."""
    return PlaythroughService(
        playthrough_repo=PlaythroughRepo(session),
        participant_repo=ParticipantRepo(session),
        scenario_repo=ScenarioRepo(session),
    )


@router.post(
    "",
    response_model=PlaythroughResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_playthrough(
    data: PlaythroughCreate,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[PlaythroughService, Depends(get_playthrough_service)],
) -> PlaythroughResponse:
    """Start a new playthrough of a published scenario."""
    return await service.create_playthrough(user_id=user.user_id, data=data)


@router.get(
    "/{playthrough_id}",
    response_model=PlaythroughResponse,
    status_code=status.HTTP_200_OK,
)
async def get_playthrough(
    playthrough_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[PlaythroughService, Depends(get_playthrough_service)],
) -> PlaythroughResponse:
    """Fetch a playthrough by ID. Participant-only access."""
    return await service.get_playthrough(
        playthrough_id=playthrough_id, user_id=user.user_id
    )
