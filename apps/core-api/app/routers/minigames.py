"""FastAPI router for master-mode Minigame endpoints."""

import uuid
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.connection import get_db_session
from app.db.models.user import User
from app.middleware.auth import get_current_user
from app.models.minigame import (
    MinigameCreate,
    MinigameListResponse,
    MinigameReorderRequest,
    MinigameResponse,
    MinigameUpdate,
)
from app.repositories.entity_repo import EntityRepo
from app.repositories.minigame_repo import MinigameRepo
from app.repositories.scenario_repo import ScenarioRepo
from app.services.minigame_service import MinigameService

router = APIRouter(prefix="/v1/scenarios/{scenario_id}/minigames", tags=["Minigames"])


def get_http_client() -> httpx.AsyncClient:
    """Dependency provider for the outbound HTTP client used by the
    replit_embed reachability check.

    NOTE: constructed per-request rather than as an app-wide singleton —
    Core API has no existing shared outbound-HTTP-client convention to
    reuse, and per-request instantiation keeps this dependency trivially
    overridable in tests via app.dependency_overrides.
    """
    return httpx.AsyncClient()


def get_minigame_service(
    session: Annotated[AsyncSession, Depends(get_db_session, scope="function")],
    http_client: Annotated[httpx.AsyncClient, Depends(get_http_client)],
) -> MinigameService:
    """Dependency injector for MinigameService."""
    return MinigameService(
        MinigameRepo(session), EntityRepo(session), ScenarioRepo(session), http_client
    )


@router.post("", response_model=MinigameResponse, status_code=status.HTTP_201_CREATED)
async def create_minigame(
    scenario_id: uuid.UUID,
    data: MinigameCreate,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[MinigameService, Depends(get_minigame_service)],
) -> MinigameResponse:
    """Add an interstitial minigame trigger to a master-mode scenario."""
    return await service.create_minigame(scenario_id, user.user_id, data)


@router.get("", response_model=MinigameListResponse, status_code=status.HTTP_200_OK)
async def list_minigames(
    scenario_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[MinigameService, Depends(get_minigame_service)],
) -> MinigameListResponse:
    """List all minigames for a scenario, priority-ordered."""
    items = await service.list_minigames(scenario_id, user.user_id)
    return MinigameListResponse(items=items)


@router.post(
    "/reorder", response_model=MinigameListResponse, status_code=status.HTTP_200_OK
)
async def reorder_minigames(
    scenario_id: uuid.UUID,
    data: MinigameReorderRequest,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[MinigameService, Depends(get_minigame_service)],
) -> MinigameListResponse:
    """Reassign priority to match the creator's chosen order."""
    items = await service.reorder_minigames(
        scenario_id, user.user_id, data.ordered_minigame_ids
    )
    return MinigameListResponse(items=items)


@router.get(
    "/{minigame_id}", response_model=MinigameResponse, status_code=status.HTTP_200_OK
)
async def get_minigame(
    scenario_id: uuid.UUID,
    minigame_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[MinigameService, Depends(get_minigame_service)],
) -> MinigameResponse:
    """Fetch a single minigame."""
    return await service.get_minigame(scenario_id, minigame_id, user.user_id)


@router.patch(
    "/{minigame_id}", response_model=MinigameResponse, status_code=status.HTTP_200_OK
)
async def update_minigame(
    scenario_id: uuid.UUID,
    minigame_id: uuid.UUID,
    data: MinigameUpdate,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[MinigameService, Depends(get_minigame_service)],
) -> MinigameResponse:
    """Update a minigame's fields."""
    return await service.update_minigame(scenario_id, minigame_id, user.user_id, data)


@router.delete("/{minigame_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_minigame(
    scenario_id: uuid.UUID,
    minigame_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[MinigameService, Depends(get_minigame_service)],
) -> Response:
    """Remove a minigame."""
    await service.delete_minigame(scenario_id, minigame_id, user.user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
