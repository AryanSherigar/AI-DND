"""FastAPI router for User Profile and activity endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.connection import get_db_session
from app.db.models.user import User
from app.middleware.auth import get_current_user
from app.models.user import (
    UserPlaythroughSummary,
    UserProfileResponse,
    UserProfileUpdate,
    UserPublicProfileResponse,
    UserReviewSummary,
)
from app.repositories.playthrough_repo import PlaythroughRepo
from app.repositories.user_repo import UserRepo
from app.services.user_service import UserService

router = APIRouter(prefix="/v1/users", tags=["Users"])


def get_user_service(
    session: Annotated[AsyncSession, Depends(get_db_session, scope="function")],
) -> UserService:
    """Dependency injector for UserService."""
    return UserService(
        user_repo=UserRepo(session),
        playthrough_repo=PlaythroughRepo(session),
    )


@router.get(
    "/me",
    response_model=UserProfileResponse,
    status_code=status.HTTP_200_OK,
)
async def get_my_profile(
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[UserService, Depends(get_user_service)],
) -> UserProfileResponse:
    """Retrieve full profile including stats for the currently authenticated user."""
    return await service.get_my_profile(user.user_id)


@router.patch(
    "/me",
    response_model=UserProfileResponse,
    status_code=status.HTTP_200_OK,
)
async def update_my_profile(
    data: UserProfileUpdate,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[UserService, Depends(get_user_service)],
) -> UserProfileResponse:
    """Update profile attributes (display name, bio, avatar, banner) for current user."""
    return await service.update_profile(user.user_id, data)


@router.get(
    "/me/playthroughs",
    response_model=list[UserPlaythroughSummary],
    status_code=status.HTTP_200_OK,
)
async def list_my_playthroughs(
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[UserService, Depends(get_user_service)],
    status: Annotated[str | None, Query()] = None,
) -> list[UserPlaythroughSummary]:
    """List playthrough campaigns belonging to current user."""
    return await service.list_user_playthroughs(user.user_id, status=status)


@router.get(
    "/{user_id}",
    response_model=UserPublicProfileResponse,
    status_code=status.HTTP_200_OK,
)
async def get_public_profile(
    user_id: uuid.UUID,
    service: Annotated[UserService, Depends(get_user_service)],
) -> UserPublicProfileResponse:
    """Retrieve publicly visible profile details and stats for a user."""
    return await service.get_public_profile(user_id)


@router.get(
    "/{user_id}/reviews",
    response_model=list[UserReviewSummary],
    status_code=status.HTTP_200_OK,
)
async def list_user_reviews(
    user_id: uuid.UUID,
    service: Annotated[UserService, Depends(get_user_service)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[UserReviewSummary]:
    """List scenario reviews authored by a user."""
    return await service.list_user_reviews(user_id, limit=limit, offset=offset)
