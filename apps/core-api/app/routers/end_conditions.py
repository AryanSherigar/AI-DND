"""FastAPI router for master-mode End Condition endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.connection import get_db_session
from app.db.models.user import User
from app.middleware.auth import get_current_user
from app.models.end_condition import (
    EndConditionCreate,
    EndConditionListResponse,
    EndConditionReorderRequest,
    EndConditionResponse,
    EndConditionUpdate,
)
from app.repositories.end_condition_repo import EndConditionRepo
from app.repositories.entity_repo import EntityRepo
from app.repositories.scenario_repo import ScenarioRepo
from app.services.end_condition_service import EndConditionService

router = APIRouter(
    prefix="/v1/scenarios/{scenario_id}/end_conditions", tags=["End Conditions"]
)


def get_end_condition_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> EndConditionService:
    """Dependency injector for EndConditionService."""
    return EndConditionService(
        EndConditionRepo(session), EntityRepo(session), ScenarioRepo(session)
    )


@router.post(
    "", response_model=EndConditionResponse, status_code=status.HTTP_201_CREATED
)
async def create_end_condition(
    scenario_id: uuid.UUID,
    data: EndConditionCreate,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[EndConditionService, Depends(get_end_condition_service)],
) -> EndConditionResponse:
    """Add a win/lose end condition to a master-mode scenario."""
    return await service.create_end_condition(scenario_id, user.user_id, data)


@router.get("", response_model=EndConditionListResponse, status_code=status.HTTP_200_OK)
async def list_end_conditions(
    scenario_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[EndConditionService, Depends(get_end_condition_service)],
) -> EndConditionListResponse:
    """List all end conditions for a scenario, priority-ordered."""
    items = await service.list_end_conditions(scenario_id, user.user_id)
    return EndConditionListResponse(items=items)


@router.post(
    "/reorder", response_model=EndConditionListResponse, status_code=status.HTTP_200_OK
)
async def reorder_end_conditions(
    scenario_id: uuid.UUID,
    data: EndConditionReorderRequest,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[EndConditionService, Depends(get_end_condition_service)],
) -> EndConditionListResponse:
    """Reassign priority to match the creator's chosen order."""
    items = await service.reorder_end_conditions(
        scenario_id, user.user_id, data.ordered_end_condition_ids
    )
    return EndConditionListResponse(items=items)


@router.get(
    "/{end_condition_id}",
    response_model=EndConditionResponse,
    status_code=status.HTTP_200_OK,
)
async def get_end_condition(
    scenario_id: uuid.UUID,
    end_condition_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[EndConditionService, Depends(get_end_condition_service)],
) -> EndConditionResponse:
    """Fetch a single end condition."""
    return await service.get_end_condition(scenario_id, end_condition_id, user.user_id)


@router.patch(
    "/{end_condition_id}",
    response_model=EndConditionResponse,
    status_code=status.HTTP_200_OK,
)
async def update_end_condition(
    scenario_id: uuid.UUID,
    end_condition_id: uuid.UUID,
    data: EndConditionUpdate,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[EndConditionService, Depends(get_end_condition_service)],
) -> EndConditionResponse:
    """Update an end condition's fields."""
    return await service.update_end_condition(
        scenario_id, end_condition_id, user.user_id, data
    )


@router.delete("/{end_condition_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_end_condition(
    scenario_id: uuid.UUID,
    end_condition_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[EndConditionService, Depends(get_end_condition_service)],
) -> Response:
    """Remove an end condition."""
    await service.delete_end_condition(scenario_id, end_condition_id, user.user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
