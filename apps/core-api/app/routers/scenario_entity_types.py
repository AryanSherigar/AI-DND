"""FastAPI router for scenario-scoped custom entity type template endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.connection import get_db_session
from app.db.models.user import User
from app.middleware.auth import get_current_user
from app.models.scenario_entity_type import (
    ScenarioEntityTypeCreate,
    ScenarioEntityTypeListResponse,
    ScenarioEntityTypeResponse,
    ScenarioEntityTypeUpdate,
)
from app.repositories.entity_repo import EntityRepo
from app.repositories.scenario_entity_type_repo import ScenarioEntityTypeRepo
from app.repositories.scenario_repo import ScenarioRepo
from app.services.scenario_entity_type_service import ScenarioEntityTypeService

router = APIRouter(
    prefix="/v1/scenarios/{scenario_id}/entity-types", tags=["Entity Types"]
)


def get_scenario_entity_type_service(
    session: Annotated[AsyncSession, Depends(get_db_session, scope="function")],
) -> ScenarioEntityTypeService:
    """Dependency injector for ScenarioEntityTypeService."""
    return ScenarioEntityTypeService(
        ScenarioEntityTypeRepo(session), EntityRepo(session), ScenarioRepo(session)
    )


@router.post(
    "", response_model=ScenarioEntityTypeResponse, status_code=status.HTTP_201_CREATED
)
async def create_entity_type(
    scenario_id: uuid.UUID,
    data: ScenarioEntityTypeCreate,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[
        ScenarioEntityTypeService, Depends(get_scenario_entity_type_service)
    ],
) -> ScenarioEntityTypeResponse:
    """Define a new custom entity type template for a scenario."""
    return await service.create_entity_type(scenario_id, user.user_id, data)


@router.get(
    "",
    response_model=ScenarioEntityTypeListResponse,
    status_code=status.HTTP_200_OK,
)
async def list_entity_types(
    scenario_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[
        ScenarioEntityTypeService, Depends(get_scenario_entity_type_service)
    ],
) -> ScenarioEntityTypeListResponse:
    """List all custom entity type templates for a scenario."""
    items = await service.list_entity_types(scenario_id, user.user_id)
    return ScenarioEntityTypeListResponse(items=items)


@router.patch(
    "/{scenario_entity_type_id}",
    response_model=ScenarioEntityTypeResponse,
    status_code=status.HTTP_200_OK,
)
async def update_entity_type(
    scenario_id: uuid.UUID,
    scenario_entity_type_id: uuid.UUID,
    data: ScenarioEntityTypeUpdate,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[
        ScenarioEntityTypeService, Depends(get_scenario_entity_type_service)
    ],
) -> ScenarioEntityTypeResponse:
    """Update a custom entity type template's fields."""
    return await service.update_entity_type(
        scenario_id, scenario_entity_type_id, user.user_id, data
    )


@router.delete("/{scenario_entity_type_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_entity_type(
    scenario_id: uuid.UUID,
    scenario_entity_type_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[
        ScenarioEntityTypeService, Depends(get_scenario_entity_type_service)
    ],
) -> Response:
    """Remove a custom entity type template, if unused by any entity."""
    await service.delete_entity_type(scenario_id, scenario_entity_type_id, user.user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
