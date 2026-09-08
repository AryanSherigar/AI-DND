"""Music generation job data repository for direct database operations."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.music_generation_job import MusicGenerationJob


class MusicGenerationJobRepo:
    """Repository managing direct SQLAlchemy queries for MusicGenerationJob."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        scenario_id: uuid.UUID,
        creator_id: uuid.UUID,
        mood: str,
        prompt: str,
    ) -> MusicGenerationJob:
        """Persist a new pending generation job."""
        job = MusicGenerationJob(
            scenario_id=scenario_id,
            creator_id=creator_id,
            mood=mood,
            prompt=prompt,
            status="pending",
        )
        self.session.add(job)
        await self.session.flush()
        return job

    async def get_by_id(self, job_id: uuid.UUID) -> MusicGenerationJob | None:
        """Retrieve a job by its primary key ID."""
        stmt = select(MusicGenerationJob).where(MusicGenerationJob.job_id == job_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def mark_running(self, job_id: uuid.UUID) -> None:
        """Flip a pending job to running."""
        job = await self.get_by_id(job_id)
        if job is None:
            return
        job.status = "running"
        await self.session.flush()

    async def mark_succeeded(
        self,
        job_id: uuid.UUID,
        preview_url: str,
        key: str,
        bpm: int,
        duration_seconds: float,
    ) -> None:
        """Record a successful generation result on the job."""
        job = await self.get_by_id(job_id)
        if job is None:
            return
        job.status = "succeeded"
        job.preview_url = preview_url
        job.key = key
        job.bpm = bpm
        job.duration_seconds = duration_seconds
        await self.session.flush()

    async def mark_failed(self, job_id: uuid.UUID, error_message: str) -> None:
        """Record a failed generation attempt on the job."""
        job = await self.get_by_id(job_id)
        if job is None:
            return
        job.status = "failed"
        job.error_message = error_message
        await self.session.flush()
