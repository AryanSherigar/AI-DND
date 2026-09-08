"""FastAPI router for scenario mood-music endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.connection import get_db_session, get_session_factory
from app.db.models.user import User
from app.exceptions.music_exceptions import MusicValidationError
from app.exceptions.scenario_exceptions import (
    ScenarioAccessDeniedError,
    ScenarioNotFoundError,
)
from app.middleware.auth import get_current_user
from app.models.music import (
    MoodSlot,
    MusicGenerationJobResponse,
    MusicGenerationRequest,
    QuotaStatusResponse,
    ScenarioMusicListResponse,
    ScenarioMusicResponse,
)
from app.repositories.music_generation_job_repo import MusicGenerationJobRepo
from app.repositories.music_generation_log_repo import MusicGenerationLogRepo
from app.repositories.scenario_music_repo import ScenarioMusicRepo
from app.repositories.scenario_repo import ScenarioRepo
from app.services.music_service import MAX_AUDIO_UPLOAD_BYTES, MusicService

router = APIRouter(prefix="/v1/scenarios/{scenario_id}/music", tags=["Scenario Music"])


def get_music_service(
    session: Annotated[AsyncSession, Depends(get_db_session, scope="function")],
) -> MusicService:
    """Dependency injector for MusicService."""
    return MusicService(
        scenario_music_repo=ScenarioMusicRepo(session),
        job_repo=MusicGenerationJobRepo(session),
        log_repo=MusicGenerationLogRepo(session),
    )


def get_scenario_repo(
    session: Annotated[AsyncSession, Depends(get_db_session, scope="function")],
) -> ScenarioRepo:
    """Dependency injector for ScenarioRepo, used for the ownership check."""
    return ScenarioRepo(session)


async def _require_scenario_ownership(
    scenario_id: uuid.UUID, user: User, scenario_repo: ScenarioRepo
) -> None:
    """Every music endpoint operates on a scenario the caller must own."""
    scenario = await scenario_repo.get_by_id(scenario_id)
    if scenario is None:
        raise ScenarioNotFoundError()
    if scenario.creator_id != user.user_id:
        raise ScenarioAccessDeniedError()


async def _read_capped(file: UploadFile, max_bytes: int) -> bytes:
    """Read an upload's body, rejecting it as soon as it exceeds max_bytes."""
    chunks: list[bytes] = []
    total = 0
    while chunk := await file.read(64 * 1024):
        total += len(chunk)
        if total > max_bytes:
            raise MusicValidationError("Audio file exceeds the 15MB size limit.")
        chunks.append(chunk)
    return b"".join(chunks)


@router.get("", response_model=ScenarioMusicListResponse)
async def list_scenario_music(
    scenario_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[MusicService, Depends(get_music_service)],
    scenario_repo: Annotated[ScenarioRepo, Depends(get_scenario_repo)],
) -> ScenarioMusicListResponse:
    """List all 6 mood slots for a scenario."""
    await _require_scenario_ownership(scenario_id, user, scenario_repo)
    return await service.list_scenario_music(scenario_id)


@router.post("/{mood}/upload", response_model=ScenarioMusicResponse)
async def upload_music_track(
    scenario_id: uuid.UUID,
    mood: MoodSlot,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[MusicService, Depends(get_music_service)],
    scenario_repo: Annotated[ScenarioRepo, Depends(get_scenario_repo)],
    file: Annotated[UploadFile, File()],
) -> ScenarioMusicResponse:
    """Upload a creator-supplied track for one mood slot."""
    await _require_scenario_ownership(scenario_id, user, scenario_repo)
    content = await _read_capped(file, MAX_AUDIO_UPLOAD_BYTES)
    return await service.upload_track(
        scenario_id, mood.value, content, file.content_type or ""
    )


@router.post("/{mood}/default", response_model=ScenarioMusicResponse)
async def set_default_track(
    scenario_id: uuid.UUID,
    mood: MoodSlot,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[MusicService, Depends(get_music_service)],
    scenario_repo: Annotated[ScenarioRepo, Depends(get_scenario_repo)],
) -> ScenarioMusicResponse:
    """Explicitly select the built-in default track for a mood slot."""
    await _require_scenario_ownership(scenario_id, user, scenario_repo)
    return await service.set_default_track(scenario_id, mood.value)


@router.post(
    "/generate",
    response_model=MusicGenerationJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def generate_music_track(
    scenario_id: uuid.UUID,
    body: MusicGenerationRequest,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[MusicService, Depends(get_music_service)],
    scenario_repo: Annotated[ScenarioRepo, Depends(get_scenario_repo)],
    background_tasks: BackgroundTasks,
    session_factory: Annotated[
        async_sessionmaker[AsyncSession], Depends(get_session_factory)
    ],
) -> MusicGenerationJobResponse:
    """Submit a Lyria generation job for one mood slot; poll for its result."""
    await _require_scenario_ownership(scenario_id, user, scenario_repo)
    job = await service.request_generation(scenario_id, user.user_id, body)
    background_tasks.add_task(
        MusicService.run_generation_job,
        job.job_id,
        body.duration_seconds,
        session_factory,
    )
    return job


@router.get("/jobs/{job_id}", response_model=MusicGenerationJobResponse)
async def get_generation_job(
    scenario_id: uuid.UUID,
    job_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[MusicService, Depends(get_music_service)],
    scenario_repo: Annotated[ScenarioRepo, Depends(get_scenario_repo)],
) -> MusicGenerationJobResponse:
    """Poll a submitted generation job's status."""
    await _require_scenario_ownership(scenario_id, user, scenario_repo)
    return await service.get_job_status(job_id, user.user_id)


@router.post("/jobs/{job_id}/confirm", response_model=ScenarioMusicResponse)
async def confirm_generated_track(
    scenario_id: uuid.UUID,
    job_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[MusicService, Depends(get_music_service)],
    scenario_repo: Annotated[ScenarioRepo, Depends(get_scenario_repo)],
) -> ScenarioMusicResponse:
    """Commit a succeeded generation job's track to its mood slot."""
    await _require_scenario_ownership(scenario_id, user, scenario_repo)
    return await service.confirm_generated_track(scenario_id, job_id, user.user_id)


@router.delete("/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def discard_generation_job(
    scenario_id: uuid.UUID,
    job_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[MusicService, Depends(get_music_service)],
    scenario_repo: Annotated[ScenarioRepo, Depends(get_scenario_repo)],
) -> None:
    """Discard a generation job without assigning it to a mood slot."""
    await _require_scenario_ownership(scenario_id, user, scenario_repo)
    await service.discard_job(job_id, user.user_id)


@router.get("/quota", response_model=QuotaStatusResponse)
async def get_music_quota(
    scenario_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[MusicService, Depends(get_music_service)],
    scenario_repo: Annotated[ScenarioRepo, Depends(get_scenario_repo)],
) -> QuotaStatusResponse:
    """Report current music-generation quota usage."""
    await _require_scenario_ownership(scenario_id, user, scenario_repo)
    return await service.get_quota_status(scenario_id, user.user_id)
