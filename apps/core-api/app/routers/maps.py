"""FastAPI router for master-mode Map/MapPin/MapConnection endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.connection import get_db_session
from app.db.models.user import User
from app.middleware.auth import get_current_user
from app.models.map import (
    MapConnectionCreate,
    MapConnectionListResponse,
    MapConnectionResponse,
    MapCreate,
    MapListResponse,
    MapPinCreate,
    MapPinListResponse,
    MapPinResponse,
    MapPinUpdate,
    MapResponse,
    MapUpdate,
)
from app.repositories.entity_repo import EntityRepo
from app.repositories.map_repo import MapRepo
from app.repositories.scenario_repo import ScenarioRepo
from app.services.map_service import MapService

router = APIRouter(prefix="/v1/scenarios/{scenario_id}", tags=["Maps"])


def get_map_service(
    session: Annotated[AsyncSession, Depends(get_db_session, scope="function")],
) -> MapService:
    """Dependency injector for MapService."""
    return MapService(MapRepo(session), ScenarioRepo(session), EntityRepo(session))


@router.post("/maps", response_model=MapResponse, status_code=status.HTTP_201_CREATED)
async def create_map(
    scenario_id: uuid.UUID,
    data: MapCreate,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[MapService, Depends(get_map_service)],
) -> MapResponse:
    """Create a new map within a master-mode scenario."""
    return await service.create_map(scenario_id, user.user_id, data)


@router.get("/maps", response_model=MapListResponse, status_code=status.HTTP_200_OK)
async def list_maps(
    scenario_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[MapService, Depends(get_map_service)],
) -> MapListResponse:
    """List all maps for a scenario."""
    items = await service.list_maps(scenario_id, user.user_id)
    return MapListResponse(items=items)


@router.patch(
    "/maps/{map_id}", response_model=MapResponse, status_code=status.HTTP_200_OK
)
async def update_map(
    scenario_id: uuid.UUID,
    map_id: uuid.UUID,
    data: MapUpdate,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[MapService, Depends(get_map_service)],
) -> MapResponse:
    """Update a map's fields."""
    return await service.update_map(scenario_id, map_id, user.user_id, data)


@router.delete("/maps/{map_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_map(
    scenario_id: uuid.UUID,
    map_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[MapService, Depends(get_map_service)],
) -> Response:
    """Delete a map and its pins."""
    await service.delete_map(scenario_id, map_id, user.user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/maps/{map_id}/pins",
    response_model=MapPinResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_pin(
    scenario_id: uuid.UUID,
    map_id: uuid.UUID,
    data: MapPinCreate,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[MapService, Depends(get_map_service)],
) -> MapPinResponse:
    """Place a location entity's pin on a map."""
    return await service.create_pin(scenario_id, map_id, user.user_id, data)


@router.get(
    "/maps/{map_id}/pins",
    response_model=MapPinListResponse,
    status_code=status.HTTP_200_OK,
)
async def list_pins(
    scenario_id: uuid.UUID,
    map_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[MapService, Depends(get_map_service)],
) -> MapPinListResponse:
    """List all pins placed on a map."""
    items = await service.list_pins(scenario_id, map_id, user.user_id)
    return MapPinListResponse(items=items)


@router.patch(
    "/maps/{map_id}/pins/{pin_id}",
    response_model=MapPinResponse,
    status_code=status.HTTP_200_OK,
)
async def update_pin(
    scenario_id: uuid.UUID,
    map_id: uuid.UUID,
    pin_id: uuid.UUID,
    data: MapPinUpdate,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[MapService, Depends(get_map_service)],
) -> MapPinResponse:
    """Update a pin's position or start-location flag."""
    return await service.update_pin(scenario_id, map_id, pin_id, user.user_id, data)


@router.delete("/maps/{map_id}/pins/{pin_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pin(
    scenario_id: uuid.UUID,
    map_id: uuid.UUID,
    pin_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[MapService, Depends(get_map_service)],
) -> Response:
    """Remove a pin from a map."""
    await service.delete_pin(scenario_id, map_id, pin_id, user.user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/map-connections",
    response_model=MapConnectionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_connection(
    scenario_id: uuid.UUID,
    data: MapConnectionCreate,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[MapService, Depends(get_map_service)],
) -> MapConnectionResponse:
    """Connect two location entities in the scenario-wide graph. Connections
    aren't nested under one map, since an edge may cross maps."""
    return await service.create_connection(scenario_id, user.user_id, data)


@router.get(
    "/map-connections",
    response_model=MapConnectionListResponse,
    status_code=status.HTTP_200_OK,
)
async def list_connections(
    scenario_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[MapService, Depends(get_map_service)],
) -> MapConnectionListResponse:
    """List all connections for a scenario."""
    items = await service.list_connections(scenario_id, user.user_id)
    return MapConnectionListResponse(items=items)


@router.delete(
    "/map-connections/{connection_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_connection(
    scenario_id: uuid.UUID,
    connection_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[MapService, Depends(get_map_service)],
) -> Response:
    """Remove a connection."""
    await service.delete_connection(scenario_id, connection_id, user.user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
