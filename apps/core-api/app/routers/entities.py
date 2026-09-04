"""FastAPI router for master-mode Entity endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.connection import get_db_session
from app.db.models.user import User
from app.middleware.auth import get_current_user
from app.models.entity import (
    EntityCreate,
    EntityListResponse,
    EntityResponse,
    EntityTypeChangePreviewRequest,
    EntityTypeChangePreviewResponse,
    EntityUpdate,
)
from app.repositories.entity_repo import EntityRepo
from app.repositories.fact_repo import FactRepo
from app.repositories.scenario_entity_type_repo import ScenarioEntityTypeRepo
from app.repositories.scenario_repo import ScenarioRepo
from app.services.entity_service import EntityService

router = APIRouter(prefix="/v1/scenarios/{scenario_id}/entities", tags=["Entities"])


def get_entity_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> EntityService:
    """Dependency injector for EntityService."""
    return EntityService(
        EntityRepo(session),
        ScenarioRepo(session),
        FactRepo(session),
        ScenarioEntityTypeRepo(session),
    )


@router.post("", response_model=EntityResponse, status_code=status.HTTP_201_CREATED)
async def create_entity(
    scenario_id: uuid.UUID,
    data: EntityCreate,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[EntityService, Depends(get_entity_service)],
) -> EntityResponse:
    """Add an entity to a master-mode scenario."""
    return await service.create_entity(scenario_id, user.user_id, data)


@router.get("", response_model=EntityListResponse, status_code=status.HTTP_200_OK)
async def list_entities(
    scenario_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[EntityService, Depends(get_entity_service)],
) -> EntityListResponse:
    """List all entities for a scenario."""
    items = await service.list_entities(scenario_id, user.user_id)
    return EntityListResponse(items=items)


@router.get(
    "/{entity_id}", response_model=EntityResponse, status_code=status.HTTP_200_OK
)
async def get_entity(
    scenario_id: uuid.UUID,
    entity_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[EntityService, Depends(get_entity_service)],
) -> EntityResponse:
    """Fetch a single entity."""
    return await service.get_entity(scenario_id, entity_id, user.user_id)


@router.patch(
    "/{entity_id}", response_model=EntityResponse, status_code=status.HTTP_200_OK
)
async def update_entity(
    scenario_id: uuid.UUID,
    entity_id: uuid.UUID,
    data: EntityUpdate,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[EntityService, Depends(get_entity_service)],
) -> EntityResponse:
    """Update an entity's fields."""
    return await service.update_entity(scenario_id, entity_id, user.user_id, data)


@router.post(
    "/{entity_id}/type-change-preview",
    response_model=EntityTypeChangePreviewResponse,
    status_code=status.HTTP_200_OK,
)
async def preview_entity_type_change(
    scenario_id: uuid.UUID,
    entity_id: uuid.UUID,
    data: EntityTypeChangePreviewRequest,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[EntityService, Depends(get_entity_service)],
) -> EntityTypeChangePreviewResponse:
    """Preview how changing an entity's type would compare against the new
    type's attribute template, without committing the change."""
    return await service.preview_type_change(
        scenario_id, entity_id, user.user_id, data.new_entity_type
    )


@router.delete("/{entity_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_entity(
    scenario_id: uuid.UUID,
    entity_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[EntityService, Depends(get_entity_service)],
) -> Response:
    """Remove an entity and any facts that reference it."""
    await service.delete_entity(scenario_id, entity_id, user.user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
