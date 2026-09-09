"""Scenario music data repository for direct database operations."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.scenario_music import ScenarioMusic


class ScenarioMusicRepo:
    """Repository managing direct SQLAlchemy queries for ScenarioMusic."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_scenario(self, scenario_id: uuid.UUID) -> list[ScenarioMusic]:
        """Retrieve all persisted mood-slot rows for a scenario."""
        stmt = select(ScenarioMusic).where(ScenarioMusic.scenario_id == scenario_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_scenario_and_mood(
        self, scenario_id: uuid.UUID, mood: str
    ) -> ScenarioMusic | None:
        """Retrieve a single mood slot's row, if it has been set."""
        stmt = select(ScenarioMusic).where(
            ScenarioMusic.scenario_id == scenario_id, ScenarioMusic.mood == mood
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def upsert(
        self,
        scenario_id: uuid.UUID,
        mood: str,
        source: str,
        track_url: str | None,
        generation_prompt: str | None = None,
        key: str | None = None,
        bpm: int | None = None,
        duration_seconds: float | None = None,
    ) -> ScenarioMusic:
        """Insert or overwrite the mood slot's row for this scenario."""
        existing = await self.get_by_scenario_and_mood(scenario_id, mood)
        if existing is None:
            row = ScenarioMusic(
                scenario_id=scenario_id,
                mood=mood,
                source=source,
                track_url=track_url,
                generation_prompt=generation_prompt,
                key=key,
                bpm=bpm,
                duration_seconds=duration_seconds,
            )
            self.session.add(row)
            await self.session.flush()
            return row

        existing.source = source
        existing.track_url = track_url
        existing.generation_prompt = generation_prompt
        existing.key = key
        existing.bpm = bpm
        existing.duration_seconds = duration_seconds
        await self.session.flush()
        # updated_at is server-computed onupdate -- flush marks it expired,
        # so a later synchronous read (e.g. Pydantic's model_validate)
        # would otherwise trigger a lazy load outside an async context.
        await self.session.refresh(existing)
        return existing
