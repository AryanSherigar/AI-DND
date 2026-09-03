"""FastAPI router for master-mode Rule Invariant endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.connection import get_db_session
from app.db.models.user import User
from app.middleware.auth import get_current_user
from app.models.invariant import (
    InvariantCreate,
    InvariantListResponse,
    InvariantResponse,
    InvariantUpdate,
)
from app.repositories.entity_repo import EntityRepo
from app.repositories.invariant_repo import InvariantRepo
from app.repositories.scenario_repo import ScenarioRepo
from app.services.invariant_service import InvariantService

router = APIRouter(prefix="/v1/scenarios/{scenario_id}/invariants", tags=["Invariants"])


def get_invariant_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> InvariantService:
    """Dependency injector for InvariantService."""
    return InvariantService(
        InvariantRepo(session), EntityRepo(session), ScenarioRepo(session)
    )


@router.post("", response_model=InvariantResponse, status_code=status.HTTP_201_CREATED)
async def create_invariant(
    scenario_id: uuid.UUID,
    data: InvariantCreate,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[InvariantService, Depends(get_invariant_service)],
) -> InvariantResponse:
    """Add a mechanically-enforced world-rule invariant to a master-mode scenario."""
    return await service.create_invariant(scenario_id, user.user_id, data)


@router.get("", response_model=InvariantListResponse, status_code=status.HTTP_200_OK)
async def list_invariants(
    scenario_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[InvariantService, Depends(get_invariant_service)],
) -> InvariantListResponse:
    """List all rule invariants for a scenario."""
    items = await service.list_invariants(scenario_id, user.user_id)
    return InvariantListResponse(items=items)


@router.get(
    "/{invariant_id}", response_model=InvariantResponse, status_code=status.HTTP_200_OK
)
async def get_invariant(
    scenario_id: uuid.UUID,
    invariant_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[InvariantService, Depends(get_invariant_service)],
) -> InvariantResponse:
    """Fetch a single rule invariant."""
    return await service.get_invariant(scenario_id, invariant_id, user.user_id)


@router.patch(
    "/{invariant_id}", response_model=InvariantResponse, status_code=status.HTTP_200_OK
)
async def update_invariant(
    scenario_id: uuid.UUID,
    invariant_id: uuid.UUID,
    data: InvariantUpdate,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[InvariantService, Depends(get_invariant_service)],
) -> InvariantResponse:
    """Update a rule invariant's fields."""
    return await service.update_invariant(scenario_id, invariant_id, user.user_id, data)


@router.delete("/{invariant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_invariant(
    scenario_id: uuid.UUID,
    invariant_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[InvariantService, Depends(get_invariant_service)],
) -> Response:
    """Remove a rule invariant."""
    await service.delete_invariant(scenario_id, invariant_id, user.user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
