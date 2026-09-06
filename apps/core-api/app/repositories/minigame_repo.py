"""ScenarioMinigame data repository for direct database operations."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.scenario_minigame import ScenarioMinigame


class MinigameRepo:
    """Repository managing direct SQLAlchemy queries for ScenarioMinigame."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, minigame: ScenarioMinigame) -> ScenarioMinigame:
        """Persist a new minigame."""
        self.session.add(minigame)
        await self.session.flush()
        return minigame

    async def get_by_id(self, minigame_id: uuid.UUID) -> ScenarioMinigame | None:
        """Retrieve a minigame by its primary key ID."""
        stmt = select(ScenarioMinigame).where(
            ScenarioMinigame.minigame_id == minigame_id
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_by_scenario(self, scenario_id: uuid.UUID) -> list[ScenarioMinigame]:
        """Retrieve all minigames for a scenario, ordered by priority ascending."""
        stmt = (
            select(ScenarioMinigame)
            .where(ScenarioMinigame.scenario_id == scenario_id)
            .order_by(ScenarioMinigame.priority.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update(self, minigame: ScenarioMinigame) -> ScenarioMinigame:
        """Flush changes to an existing minigame."""
        await self.session.flush()
        await self.session.refresh(minigame)
        return minigame

    async def delete(self, minigame: ScenarioMinigame) -> None:
        """Permanently delete a minigame."""
        await self.session.delete(minigame)
        await self.session.flush()
