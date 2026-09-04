"""Playthrough data repository for direct database operations."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.playthrough import Playthrough
from app.db.models.scenario import Scenario


class PlaythroughRepo:
    """Repository managing direct SQLAlchemy queries for Playthrough entity."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, playthrough: Playthrough) -> Playthrough:
        """Persist a new Playthrough entity."""
        self.session.add(playthrough)
        await self.session.flush()
        return playthrough

    async def get_by_id(self, playthrough_id: uuid.UUID) -> Playthrough | None:
        """Retrieve a playthrough by its primary key ID."""
        stmt = select(Playthrough).where(Playthrough.playthrough_id == playthrough_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def update(self, playthrough: Playthrough) -> Playthrough:
        """Flush changes to an existing playthrough entity."""
        await self.session.flush()
        await self.session.refresh(playthrough)
        return playthrough

    async def delete(self, playthrough: Playthrough) -> None:
        """Permanently delete a playthrough entity from DB."""
        await self.session.delete(playthrough)
        await self.session.flush()

    async def list_by_scenario(self, scenario_id: uuid.UUID) -> list[Playthrough]:
        """Fetch all playthroughs for a given scenario."""
        stmt = select(Playthrough).where(Playthrough.scenario_id == scenario_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_by_user(self, created_by: uuid.UUID) -> list[Playthrough]:
        """Fetch all playthroughs created by a given user."""
        stmt = select(Playthrough).where(Playthrough.created_by == created_by)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_by_user_with_scenarios(
        self, created_by: uuid.UUID, status: str | None = None
    ) -> list[tuple[Playthrough, Scenario]]:
        """Fetch all non-playtest playthroughs with scenario details for a user."""
        stmt = (
            select(Playthrough, Scenario)
            .join(Scenario, Playthrough.scenario_id == Scenario.scenario_id)
            .where(Playthrough.created_by == created_by)
            .where(Playthrough.is_playtest.is_(False))
        )
        if status:
            stmt = stmt.where(Playthrough.status == status)
        stmt = stmt.order_by(Playthrough.updated_at.desc())
        result = await self.session.execute(stmt)
        return list(result.all())
