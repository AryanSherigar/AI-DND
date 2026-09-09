"""Scenario music domain service: uploads, defaults, and Lyria generation jobs."""

from __future__ import annotations

import asyncio
import io
import uuid
from datetime import UTC, datetime, timedelta

import structlog
from mutagen import MutagenError
from mutagen._file import File as MutagenFile
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models.scenario_music import MOOD_SLOTS, ScenarioMusic
from app.exceptions.music_exceptions import (
    MusicGenerationQuotaExceededError,
    MusicJobNotFoundError,
    MusicValidationError,
)
from app.integrations import music_gen_client, storage_client
from app.models.music import (
    MusicGenerationJobResponse,
    MusicGenerationRequest,
    QuotaStatusResponse,
    ScenarioMusicListResponse,
    ScenarioMusicResponse,
)
from app.repositories.music_generation_job_repo import MusicGenerationJobRepo
from app.repositories.music_generation_log_repo import MusicGenerationLogRepo
from app.repositories.scenario_music_repo import ScenarioMusicRepo
from app.services import default_music

logger = structlog.get_logger()

MAX_AUDIO_UPLOAD_BYTES = 15 * 1024 * 1024
MIN_TRACK_DURATION_SECONDS = 30
MAX_GENERATIONS_PER_SCENARIO = 20
MAX_GENERATIONS_PER_CREATOR_PER_DAY = 10

ALLOWED_AUDIO_CONTENT_TYPES: dict[str, str] = {
    "audio/mpeg": ".mp3",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/ogg": ".ogg",
}

_SCENARIO_MUSIC_PREFIX = "scenario-music"
_MUSIC_PREVIEW_PREFIX = "music-previews"
_GENERATED_TRACK_CONTENT_TYPE = "audio/wav"

EVENT_MUSIC_GENERATION_JOB_SUCCEEDED = "music_generation_job_succeeded"
EVENT_MUSIC_GENERATION_JOB_FAILED = "music_generation_job_failed"


class MusicService:
    """Service handling scenario music slot assignment and Lyria job orchestration."""

    def __init__(
        self,
        scenario_music_repo: ScenarioMusicRepo,
        job_repo: MusicGenerationJobRepo,
        log_repo: MusicGenerationLogRepo,
    ) -> None:
        self.scenario_music_repo = scenario_music_repo
        self.job_repo = job_repo
        self.log_repo = log_repo

    async def list_scenario_music(
        self, scenario_id: uuid.UUID
    ) -> ScenarioMusicListResponse:
        """Return all 6 mood slots, synthesizing 'default' for unset ones."""
        rows = await self.scenario_music_repo.get_by_scenario(scenario_id)
        rows_by_mood = {row.mood: row for row in rows}
        items = [
            _to_response(rows_by_mood[mood])
            if mood in rows_by_mood
            else _synthesize_default(scenario_id, mood)
            for mood in MOOD_SLOTS
        ]
        return ScenarioMusicListResponse(items=items)

    async def upload_track(
        self,
        scenario_id: uuid.UUID,
        mood: str,
        content: bytes,
        content_type: str,
    ) -> ScenarioMusicResponse:
        """Validate and upload a creator-supplied track, assigning it to a mood slot."""
        extension = ALLOWED_AUDIO_CONTENT_TYPES.get(content_type)
        if extension is None:
            raise MusicValidationError(
                "Unsupported audio format. Allowed: MP3, WAV, OGG."
            )
        if len(content) > MAX_AUDIO_UPLOAD_BYTES:
            raise MusicValidationError("Audio file exceeds the 15MB size limit.")

        duration_seconds = await _probe_duration(content)
        if duration_seconds < MIN_TRACK_DURATION_SECONDS:
            raise MusicValidationError(
                f"Track duration must be at least {MIN_TRACK_DURATION_SECONDS} "
                f"seconds, got {duration_seconds:.1f}."
            )

        object_key = f"{_SCENARIO_MUSIC_PREFIX}/{uuid.uuid4()}{extension}"
        track_url = await storage_client.upload_image(content, content_type, object_key)

        row = await self.scenario_music_repo.upsert(
            scenario_id=scenario_id,
            mood=mood,
            source="upload",
            track_url=track_url,
            duration_seconds=duration_seconds,
        )
        return ScenarioMusicResponse.model_validate(row)

    async def set_default_track(
        self, scenario_id: uuid.UUID, mood: str
    ) -> ScenarioMusicResponse:
        """Explicitly select the built-in default track for a mood slot."""
        row = await self.scenario_music_repo.upsert(
            scenario_id=scenario_id, mood=mood, source="default", track_url=None
        )
        return _to_response(row)

    async def request_generation(
        self,
        scenario_id: uuid.UUID,
        creator_id: uuid.UUID,
        request: MusicGenerationRequest,
    ) -> MusicGenerationJobResponse:
        """Check quota, log the attempt, and create a pending generation job."""
        await self._check_quota(scenario_id, creator_id)
        await self.log_repo.create(scenario_id, creator_id)
        job = await self.job_repo.create(
            scenario_id=scenario_id,
            creator_id=creator_id,
            mood=request.mood.value,
            prompt=request.prompt,
        )
        return MusicGenerationJobResponse.model_validate(job)

    @staticmethod
    async def run_generation_job(
        job_id: uuid.UUID,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """Run the Lyria call in the background against its own DB session."""
        async with session_factory() as session:
            job_repo = MusicGenerationJobRepo(session)
            job = await job_repo.get_by_id(job_id)
            if job is None:
                return

            await job_repo.mark_running(job_id)
            try:
                audio_bytes, metadata = await music_gen_client.generate_music(
                    prompt=job.prompt,
                    mood=job.mood,
                    timeout_seconds=60,
                )
                actual_duration_seconds = await _probe_duration(audio_bytes)
                object_key = f"{_MUSIC_PREVIEW_PREFIX}/{uuid.uuid4()}.wav"
                preview_url = await storage_client.upload_image(
                    audio_bytes, _GENERATED_TRACK_CONTENT_TYPE, object_key
                )
            except Exception as exc:  # noqa: BLE001 - captured as job error_message
                await job_repo.mark_failed(job_id, str(exc))
                logger.warning(
                    EVENT_MUSIC_GENERATION_JOB_FAILED,
                    job_id=str(job_id),
                    error=str(exc),
                )
                await session.commit()
                return

            await job_repo.mark_succeeded(
                job_id,
                preview_url=preview_url,
                key=metadata.key,
                bpm=metadata.bpm,
                duration_seconds=actual_duration_seconds,
            )
            logger.info(EVENT_MUSIC_GENERATION_JOB_SUCCEEDED, job_id=str(job_id))
            await session.commit()

    async def get_job_status(
        self, job_id: uuid.UUID, creator_id: uuid.UUID
    ) -> MusicGenerationJobResponse:
        """Poll a generation job's status, scoped to its owning creator."""
        job = await self.job_repo.get_by_id(job_id)
        if job is None or job.creator_id != creator_id:
            raise MusicJobNotFoundError()
        return MusicGenerationJobResponse.model_validate(job)

    async def confirm_generated_track(
        self, scenario_id: uuid.UUID, job_id: uuid.UUID, creator_id: uuid.UUID
    ) -> ScenarioMusicResponse:
        """Commit a succeeded job's preview track to its mood slot."""
        job = await self.job_repo.get_by_id(job_id)
        if (
            job is None
            or job.creator_id != creator_id
            or job.scenario_id != scenario_id
            or job.status != "succeeded"
        ):
            raise MusicJobNotFoundError()

        row = await self.scenario_music_repo.upsert(
            scenario_id=scenario_id,
            mood=job.mood,
            source="generated",
            track_url=job.preview_url,
            generation_prompt=job.prompt,
            key=job.key,
            bpm=job.bpm,
            duration_seconds=job.duration_seconds,
        )
        return ScenarioMusicResponse.model_validate(row)

    async def discard_job(self, job_id: uuid.UUID, creator_id: uuid.UUID) -> None:
        """Discard a generation job without assigning it to any slot.

        No-op on scenario_music: the attempt was already counted against
        quota at request_generation time, so discarding gives no free re-roll.
        """
        job = await self.job_repo.get_by_id(job_id)
        if job is None or job.creator_id != creator_id:
            raise MusicJobNotFoundError()

    async def get_quota_status(
        self, scenario_id: uuid.UUID, creator_id: uuid.UUID
    ) -> QuotaStatusResponse:
        """Report current generation-quota usage."""
        scenario_used = await self.log_repo.count_by_scenario(scenario_id)
        since = datetime.now(UTC) - timedelta(days=1)
        creator_used_today = await self.log_repo.count_by_creator_since(
            creator_id, since
        )
        return QuotaStatusResponse(
            scenario_generations_used=scenario_used,
            scenario_generations_limit=MAX_GENERATIONS_PER_SCENARIO,
            creator_generations_used_today=creator_used_today,
            creator_generations_limit_per_day=MAX_GENERATIONS_PER_CREATOR_PER_DAY,
        )

    async def _check_quota(self, scenario_id: uuid.UUID, creator_id: uuid.UUID) -> None:
        quota = await self.get_quota_status(scenario_id, creator_id)
        if quota.scenario_generations_used >= quota.scenario_generations_limit:
            raise MusicGenerationQuotaExceededError(
                "This scenario has reached its music generation limit."
            )
        if (
            quota.creator_generations_used_today
            >= quota.creator_generations_limit_per_day
        ):
            raise MusicGenerationQuotaExceededError(
                "You've reached today's music generation limit."
            )


def _to_response(row: ScenarioMusic) -> ScenarioMusicResponse:
    """Build a response for a persisted row, resolving the real playable
    default-track URL for 'default'-source rows (DB keeps track_url=NULL for
    those, so a future default-asset swap needs no per-scenario migration)."""
    response = ScenarioMusicResponse.model_validate(row)
    if response.source == "default":
        response = response.model_copy(
            update={"track_url": default_music.default_track_url(row.mood)}
        )
    return response


def _synthesize_default(scenario_id: uuid.UUID, mood: str) -> ScenarioMusicResponse:
    """Build an unpersisted 'default' response for a mood slot with no row."""
    now = datetime.now(UTC)
    return ScenarioMusicResponse(
        scenario_music_id=uuid.uuid4(),
        scenario_id=scenario_id,
        mood=mood,
        source="default",
        track_url=default_music.default_track_url(mood),
        created_at=now,
        updated_at=now,
    )


async def _probe_duration(content: bytes) -> float:
    """Read an audio file's duration from its header, without full decoding."""
    loop = asyncio.get_running_loop()
    try:
        return await loop.run_in_executor(None, _probe_duration_sync, content)
    except MutagenError as exc:
        raise MusicValidationError(f"Could not read audio file: {exc}") from exc


def _probe_duration_sync(content: bytes) -> float:
    audio = MutagenFile(io.BytesIO(content))
    if audio is None or audio.info is None or audio.info.length <= 0:
        raise MusicValidationError("Could not determine audio track duration.")
    return float(audio.info.length)
