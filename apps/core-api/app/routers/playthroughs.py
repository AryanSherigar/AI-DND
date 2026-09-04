"""FastAPI router for Playthrough endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.connection import get_db_session
from app.db.models.user import User
from app.middleware.auth import get_current_user, get_optional_current_user
from app.models.playthrough import (
    PlaythroughCharacterUpdate,
    PlaythroughCreate,
    PlaythroughResponse,
)
from app.models.share import JoinRequest
from app.models.turn_log import TurnLogListResponse
from app.repositories.condition_repo import ConditionRepo
from app.repositories.end_condition_repo import EndConditionRepo
from app.repositories.entity_repo import EntityRepo
from app.repositories.invariant_repo import InvariantRepo
from app.repositories.map_repo import MapRepo
from app.repositories.participant_repo import ParticipantRepo
from app.repositories.playthrough_repo import PlaythroughRepo
from app.repositories.scenario_repo import ScenarioRepo
from app.repositories.share_repo import ShareRepo
from app.repositories.turn_log_repo import TurnLogRepo
from app.services.playthrough_service import PlaythroughService

router = APIRouter(prefix="/v1/playthroughs", tags=["Playthroughs"])


def get_playthrough_service(
    session: Annotated[AsyncSession, Depends(get_db_session, scope="function")],
) -> PlaythroughService:
    """Dependency injector for PlaythroughService."""
    return PlaythroughService(
        playthrough_repo=PlaythroughRepo(session),
        participant_repo=ParticipantRepo(session),
        scenario_repo=ScenarioRepo(session),
        share_repo=ShareRepo(session),
        turn_log_repo=TurnLogRepo(session),
        entity_repo=EntityRepo(session),
        condition_repo=ConditionRepo(session),
        invariant_repo=InvariantRepo(session),
        end_condition_repo=EndConditionRepo(session),
        map_repo=MapRepo(session),
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


@router.post(
    "/join",
    response_model=PlaythroughResponse,
    status_code=status.HTTP_200_OK,
)
async def join_playthrough(
    data: JoinRequest,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[PlaythroughService, Depends(get_playthrough_service)],
) -> PlaythroughResponse:
    """Join a playthrough as a multiplayer participant via a join-mode share token."""
    return await service.join_playthrough(
        share_token=data.share_token, user_id=user.user_id
    )


@router.patch(
    "/{playthrough_id}/character",
    response_model=PlaythroughResponse,
    status_code=status.HTTP_200_OK,
)
async def update_character_fields(
    playthrough_id: uuid.UUID,
    data: PlaythroughCharacterUpdate,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[PlaythroughService, Depends(get_playthrough_service)],
) -> PlaythroughResponse:
    """Edit character setup values (name, custom fields) on an active playthrough."""
    return await service.update_character_fields(
        playthrough_id=playthrough_id, user_id=user.user_id, data=data
    )


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


@router.post(
    "/{playthrough_id}/abandon",
    response_model=PlaythroughResponse,
    status_code=status.HTTP_200_OK,
)
async def abandon_playthrough(
    playthrough_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[PlaythroughService, Depends(get_playthrough_service)],
) -> PlaythroughResponse:
    """Mark an active playthrough as abandoned."""
    return await service.abandon_playthrough(
        playthrough_id=playthrough_id, user_id=user.user_id
    )


@router.get(
    "/{playthrough_id}/turns",
    response_model=TurnLogListResponse,
    status_code=status.HTTP_200_OK,
)
async def list_turns(
    playthrough_id: uuid.UUID,
    user: Annotated[User | None, Depends(get_optional_current_user)],
    service: Annotated[PlaythroughService, Depends(get_playthrough_service)],
    share_token: Annotated[str | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    from_turn: Annotated[int | None, Query(ge=1)] = None,
) -> TurnLogListResponse:
    """Fetch paginated turn history. Participants and valid share-token holders only."""
    return await service.list_turns(
        playthrough_id=playthrough_id,
        user_id=user.user_id if user else None,
        share_token=share_token,
        page=page,
        page_size=page_size,
        from_turn=from_turn,
    )
