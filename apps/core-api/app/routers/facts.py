"""FastAPI router for master-mode Fact endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.connection import get_db_session
from app.db.models.user import User
from app.middleware.auth import get_current_user
from app.models.fact import FactCreate, FactListResponse, FactResponse, FactUpdate
from app.repositories.entity_repo import EntityRepo
from app.repositories.fact_repo import FactRepo
from app.repositories.scenario_repo import ScenarioRepo
from app.services.fact_service import FactService

router = APIRouter(prefix="/v1/scenarios/{scenario_id}/facts", tags=["Facts"])


def get_fact_service(
    session: Annotated[AsyncSession, Depends(get_db_session, scope="function")],
) -> FactService:
    """Dependency injector for FactService."""
    return FactService(FactRepo(session), EntityRepo(session), ScenarioRepo(session))


@router.post("", response_model=FactResponse, status_code=status.HTTP_201_CREATED)
async def create_fact(
    scenario_id: uuid.UUID,
    data: FactCreate,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[FactService, Depends(get_fact_service)],
) -> FactResponse:
    """Add a fact to a master-mode scenario."""
    return await service.create_fact(scenario_id, user.user_id, data)


@router.get("", response_model=FactListResponse, status_code=status.HTTP_200_OK)
async def list_facts(
    scenario_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[FactService, Depends(get_fact_service)],
    entity_id: Annotated[uuid.UUID | None, Query()] = None,
) -> FactListResponse:
    """List facts for a scenario, optionally filtered to those referencing one entity."""
    items = await service.list_facts(scenario_id, user.user_id, entity_id)
    return FactListResponse(items=items)


@router.get("/{fact_id}", response_model=FactResponse, status_code=status.HTTP_200_OK)
async def get_fact(
    scenario_id: uuid.UUID,
    fact_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[FactService, Depends(get_fact_service)],
) -> FactResponse:
    """Fetch a single fact."""
    return await service.get_fact(scenario_id, fact_id, user.user_id)


@router.patch("/{fact_id}", response_model=FactResponse, status_code=status.HTTP_200_OK)
async def update_fact(
    scenario_id: uuid.UUID,
    fact_id: uuid.UUID,
    data: FactUpdate,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[FactService, Depends(get_fact_service)],
) -> FactResponse:
    """Update a fact's fields."""
    return await service.update_fact(scenario_id, fact_id, user.user_id, data)


@router.delete("/{fact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_fact(
    scenario_id: uuid.UUID,
    fact_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[FactService, Depends(get_fact_service)],
) -> Response:
    """Remove a fact."""
    await service.delete_fact(scenario_id, fact_id, user.user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
