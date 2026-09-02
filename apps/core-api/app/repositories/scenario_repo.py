"""Scenario data repository for direct database operations."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.playthrough import Playthrough
from app.db.models.scenario import Scenario


class ScenarioRepo:
    """Repository managing direct SQLAlchemy queries for Scenario entity."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, scenario: Scenario) -> Scenario:
        """Persist a new Scenario entity."""
        self.session.add(scenario)
        await self.session.flush()
        return scenario

    async def get_by_id(self, scenario_id: uuid.UUID) -> Scenario | None:
        """Retrieve a scenario by its primary key ID."""
        stmt = select(Scenario).where(Scenario.scenario_id == scenario_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def update(self, scenario: Scenario) -> Scenario:
        """Flush changes to an existing scenario entity."""
        await self.session.flush()
        await self.session.refresh(scenario)
        return scenario

    async def delete(self, scenario: Scenario) -> None:
        """Permanently delete a scenario entity from DB."""
        await self.session.delete(scenario)
        await self.session.flush()

    async def count_playthroughs(self, scenario_id: uuid.UUID) -> int:
        """Count total playthroughs associated with a scenario ID."""
        stmt = (
            select(func.count())
            .select_from(Playthrough)
            .where(Playthrough.scenario_id == scenario_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one() or 0

    async def list_scenarios(
        self,
        creator_id: uuid.UUID | None = None,
        published_only: bool = False,
        genre_tags: list[str] | None = None,
        complexity_tier: str | None = None,
        player_count_support: str | None = None,
        sort_by: str = "created_at",
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Scenario], int]:
        """Fetch scenarios matching discovery or creator dashboard filters."""
        stmt = select(Scenario)
        stmt = self._apply_filters(
            stmt,
            creator_id,
            published_only,
            genre_tags,
            complexity_tier,
            player_count_support,
        )

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.execute(count_stmt)
        total_count = total_result.scalar_one() or 0

        stmt = self._apply_sorting(stmt, sort_by).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())

        return items, total_count

    def _apply_filters(
        self,
        stmt: select,
        creator_id: uuid.UUID | None,
        published_only: bool,
        genre_tags: list[str] | None,
        complexity_tier: str | None,
        player_count_support: str | None,
    ) -> select:
        """Apply query conditions for scenario filtering."""
        if creator_id is not None:
            stmt = stmt.where(Scenario.creator_id == creator_id)
        if published_only:
            # published_at (not status) is the discovery-visibility signal: a
            # re-publish attempt can transiently move status away from
            # 'published' without the scenario leaving the live feed.
            stmt = stmt.where(Scenario.published_at.is_not(None))
        if complexity_tier is not None:
            stmt = stmt.where(Scenario.complexity_tier == complexity_tier)
        if player_count_support is not None:
            stmt = stmt.where(Scenario.player_count_support == player_count_support)
        if genre_tags:
            stmt = stmt.where(Scenario.genre_tags.overlap(genre_tags))
        return stmt

    def _apply_sorting(self, stmt: select, sort_by: str) -> select:
        """Apply sort order to scenario list query."""
        if sort_by == "play_count":
            return stmt.order_by(Scenario.play_count.desc())
        if sort_by == "rating_avg":
            return stmt.order_by(Scenario.rating_avg.desc())
        return stmt.order_by(Scenario.created_at.desc())
