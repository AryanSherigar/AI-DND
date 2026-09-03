"""Scenario data repository for direct database operations."""

import uuid
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.bookmark import Bookmark
from app.db.models.playthrough import Playthrough
from app.db.models.review import ScenarioReview
from app.db.models.scenario import Scenario
from app.db.models.user import User


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

    async def get_creator_display_name(self, creator_id: uuid.UUID) -> str | None:
        """Fetch creator display name by user_id."""
        stmt = select(User.display_name).where(User.user_id == creator_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def is_bookmarked(self, user_id: uuid.UUID, scenario_id: uuid.UUID) -> bool:
        """Check if user has bookmarked a scenario."""
        stmt = select(Bookmark).where(
            Bookmark.user_id == user_id, Bookmark.scenario_id == scenario_id
        )
        res = await self.session.execute(stmt)
        return res.scalars().first() is not None

    async def add_bookmark(self, user_id: uuid.UUID, scenario_id: uuid.UUID) -> None:
        """Add scenario bookmark for user if not existing."""
        if not await self.is_bookmarked(user_id, scenario_id):
            bm = Bookmark(user_id=user_id, scenario_id=scenario_id)
            self.session.add(bm)
            await self.session.flush()

    async def remove_bookmark(self, user_id: uuid.UUID, scenario_id: uuid.UUID) -> None:
        """Remove scenario bookmark for user."""
        stmt = select(Bookmark).where(
            Bookmark.user_id == user_id, Bookmark.scenario_id == scenario_id
        )
        res = await self.session.execute(stmt)
        bm = res.scalars().first()
        if bm:
            await self.session.delete(bm)
            await self.session.flush()

    async def has_user_played_min_turns(
        self, user_id: uuid.UUID, scenario_id: uuid.UUID, min_turns: int = 10
    ) -> bool:
        """Check if user has a non-playtest playthrough for scenario with at
        least min_turns. Playtest playthroughs are excluded so a creator
        cannot farm their own review eligibility by playtesting a draft.
        """
        stmt = select(Playthrough).where(
            Playthrough.created_by == user_id,
            Playthrough.scenario_id == scenario_id,
            Playthrough.turn_count >= min_turns,
            Playthrough.is_playtest.is_(False),
        )
        res = await self.session.execute(stmt)
        return res.scalars().first() is not None

    async def list_reviews(
        self, scenario_id: uuid.UUID, limit: int = 20, offset: int = 0
    ) -> tuple[list[tuple[ScenarioReview, str]], int, float]:
        """Fetch reviews for a scenario with user display names."""
        stmt = (
            select(ScenarioReview, User.display_name)
            .join(User, ScenarioReview.user_id == User.user_id)
            .where(ScenarioReview.scenario_id == scenario_id)
            .order_by(ScenarioReview.created_at.desc())
        )
        count_stmt = select(func.count()).select_from(
            select(ScenarioReview)
            .where(ScenarioReview.scenario_id == scenario_id)
            .subquery()
        )
        avg_stmt = select(func.avg(ScenarioReview.rating)).where(
            ScenarioReview.scenario_id == scenario_id
        )
        total = (await self.session.execute(count_stmt)).scalar_one() or 0
        avg_val = (await self.session.execute(avg_stmt)).scalar_one() or 0.0

        paginated_stmt = stmt.limit(limit).offset(offset)
        res = await self.session.execute(paginated_stmt)
        return list(res.all()), total, float(avg_val)

    async def create_or_update_review(
        self,
        user_id: uuid.UUID,
        scenario_id: uuid.UUID,
        rating: int,
        comment: str | None,
    ) -> tuple[ScenarioReview, str]:
        """Create or update user review for a scenario and update scenario rating_avg."""
        stmt = select(ScenarioReview).where(
            ScenarioReview.user_id == user_id, ScenarioReview.scenario_id == scenario_id
        )
        res = await self.session.execute(stmt)
        review = res.scalars().first()
        if review:
            review.rating = rating
            review.comment = comment
        else:
            review = ScenarioReview(
                user_id=user_id, scenario_id=scenario_id, rating=rating, comment=comment
            )
            self.session.add(review)
        await self.session.flush()

        avg_stmt = select(func.avg(ScenarioReview.rating)).where(
            ScenarioReview.scenario_id == scenario_id
        )
        new_avg = (await self.session.execute(avg_stmt)).scalar_one() or 0.0
        scenario_stmt = select(Scenario).where(Scenario.scenario_id == scenario_id)
        scen_res = await self.session.execute(scenario_stmt)
        scen = scen_res.scalars().first()
        if scen:
            scen.rating_avg = round(Decimal(str(new_avg)), 2)
            await self.session.flush()

        user_stmt = select(User.display_name).where(User.user_id == user_id)
        user_res = await self.session.execute(user_stmt)
        display_name = user_res.scalar_one_or_none() or "Adventurer"

        return review, display_name

    async def list_public_playthroughs(
        self, scenario_id: uuid.UUID, limit: int = 10
    ) -> list[tuple[Playthrough, str]]:
        """List active or completed playthroughs with player display names."""
        stmt = (
            select(Playthrough, User.display_name)
            .join(User, Playthrough.created_by == User.user_id)
            .where(Playthrough.scenario_id == scenario_id)
            .where(Playthrough.is_playtest.is_(False))
            .order_by(Playthrough.updated_at.desc())
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        return list(res.all())
