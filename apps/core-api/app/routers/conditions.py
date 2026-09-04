"""FastAPI router for master-mode active Condition endpoints (Effect C)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.connection import get_db_session
from app.db.models.user import User
from app.middleware.auth import get_current_user
from app.models.condition import (
    ConditionCreate,
    ConditionListResponse,
    ConditionResponse,
    ConditionUpdate,
)
from app.repositories.condition_repo import ConditionRepo
from app.repositories.entity_repo import EntityRepo
from app.repositories.scenario_repo import ScenarioRepo
from app.services.condition_service import ConditionService

router = APIRouter(prefix="/v1/scenarios/{scenario_id}/conditions", tags=["Conditions"])


def get_condition_service(
    session: Annotated[AsyncSession, Depends(get_db_session, scope="function")],
) -> ConditionService:
    """Dependency injector for ConditionService."""
    return ConditionService(
        ConditionRepo(session), EntityRepo(session), ScenarioRepo(session)
    )


@router.post("", response_model=ConditionResponse, status_code=status.HTTP_201_CREATED)
async def create_condition(
    scenario_id: uuid.UUID,
    data: ConditionCreate,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ConditionService, Depends(get_condition_service)],
) -> ConditionResponse:
    """Add an active condition to a master-mode scenario."""
    return await service.create_condition(scenario_id, user.user_id, data)


@router.get("", response_model=ConditionListResponse, status_code=status.HTTP_200_OK)
async def list_conditions(
    scenario_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ConditionService, Depends(get_condition_service)],
) -> ConditionListResponse:
    """List all active conditions for a scenario."""
    items = await service.list_conditions(scenario_id, user.user_id)
    return ConditionListResponse(items=items)


@router.get(
    "/{condition_id}", response_model=ConditionResponse, status_code=status.HTTP_200_OK
)
async def get_condition(
    scenario_id: uuid.UUID,
    condition_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ConditionService, Depends(get_condition_service)],
) -> ConditionResponse:
    """Fetch a single active condition."""
    return await service.get_condition(scenario_id, condition_id, user.user_id)


@router.patch(
    "/{condition_id}", response_model=ConditionResponse, status_code=status.HTTP_200_OK
)
async def update_condition(
    scenario_id: uuid.UUID,
    condition_id: uuid.UUID,
    data: ConditionUpdate,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ConditionService, Depends(get_condition_service)],
) -> ConditionResponse:
    """Update an active condition's fields."""
    return await service.update_condition(scenario_id, condition_id, user.user_id, data)


@router.delete("/{condition_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_condition(
    scenario_id: uuid.UUID,
    condition_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ConditionService, Depends(get_condition_service)],
) -> Response:
    """Remove an active condition."""
    await service.delete_condition(scenario_id, condition_id, user.user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
