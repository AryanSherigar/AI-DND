"""FastAPI router for Scenario endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.connection import get_db_session, get_session_factory
from app.db.models.user import User
from app.middleware.auth import get_current_user, get_optional_current_user
from app.models.scenario import (
    ScenarioCreate,
    ScenarioListResponse,
    ScenarioResponse,
    ScenarioUpdate,
)
from app.repositories.scenario_repo import ScenarioRepo
from app.services.publish_service import PublishService
from app.services.scenario_service import ScenarioService

router = APIRouter(prefix="/v1/scenarios", tags=["Scenarios"])


def get_scenario_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ScenarioService:
    """Dependency injector for ScenarioService."""
    repo = ScenarioRepo(session)
    return ScenarioService(repo)


def get_publish_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PublishService:
    """Dependency injector for PublishService."""
    repo = ScenarioRepo(session)
    return PublishService(repo)


@router.post(
    "",
    response_model=ScenarioResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_scenario(
    data: ScenarioCreate,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ScenarioService, Depends(get_scenario_service)],
) -> ScenarioResponse:
    """Create a new scenario draft."""
    return await service.create_scenario(user_id=user.user_id, data=data)


@router.post(
    "/{scenario_id}/publish",
    response_model=ScenarioResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def publish_scenario(
    scenario_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[PublishService, Depends(get_publish_service)],
    background_tasks: BackgroundTasks,
    session_factory: Annotated[
        async_sessionmaker[AsyncSession], Depends(get_session_factory)
    ],
) -> ScenarioResponse:
    """Start the async publish flow: content-tag check + authoring-time ingestion."""
    scenario = await service.start_publish(
        scenario_id=scenario_id, user_id=user.user_id
    )
    background_tasks.add_task(
        PublishService.run_publish_job, scenario.scenario_id, session_factory
    )
    return ScenarioResponse.model_validate(scenario)


@router.get(
    "/{scenario_id}",
    response_model=ScenarioResponse,
    status_code=status.HTTP_200_OK,
)
async def get_scenario(
    scenario_id: uuid.UUID,
    user: Annotated[User | None, Depends(get_optional_current_user)],
    service: Annotated[ScenarioService, Depends(get_scenario_service)],
) -> ScenarioResponse:
    """Retrieve full scenario details by ID."""
    current_user_id = user.user_id if user else None
    return await service.get_scenario(
        scenario_id=scenario_id, current_user_id=current_user_id
    )


@router.patch(
    "/{scenario_id}",
    response_model=ScenarioResponse,
    status_code=status.HTTP_200_OK,
)
async def update_scenario(
    scenario_id: uuid.UUID,
    data: ScenarioUpdate,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ScenarioService, Depends(get_scenario_service)],
) -> ScenarioResponse:
    """Update editable scenario fields."""
    return await service.update_scenario(
        scenario_id=scenario_id, user_id=user.user_id, data=data
    )


@router.delete(
    "/{scenario_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_scenario(
    scenario_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ScenarioService, Depends(get_scenario_service)],
) -> Response:
    """Delete draft scenario or soft-archive published scenario."""
    await service.delete_scenario(scenario_id=scenario_id, user_id=user.user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "",
    response_model=ScenarioListResponse,
    status_code=status.HTTP_200_OK,
)
async def list_scenarios(
    user: Annotated[User | None, Depends(get_optional_current_user)],
    service: Annotated[ScenarioService, Depends(get_scenario_service)],
    mine: bool = False,
    genre_tags: Annotated[list[str] | None, Query()] = None,
    complexity_tier: Annotated[str | None, Query()] = None,
    player_count_support: Annotated[str | None, Query()] = None,
    sort: Annotated[str, Query()] = "created_at",
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ScenarioListResponse:
    """List published scenarios for discovery or user's scenarios."""
    current_user_id = user.user_id if user else None
    return await service.list_scenarios(
        current_user_id=current_user_id,
        mine=mine,
        genre_tags=genre_tags,
        complexity_tier=complexity_tier,
        player_count_support=player_count_support,
        sort_by=sort,
        limit=limit,
        offset=offset,
    )
