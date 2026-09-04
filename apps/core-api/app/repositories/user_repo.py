"""User repository for database operations."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.playthrough import Playthrough
from app.db.models.review import ScenarioReview
from app.db.models.scenario import Scenario
from app.db.models.user import User


class UserRepo:
    """Repository handling database queries for User entities and profile stats."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_auth_provider_id(self, auth_provider_id: str) -> User | None:
        """Fetch user by external auth provider ID."""
        stmt = select(User).where(User.auth_provider_id == auth_provider_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        """Fetch user by unique user UUID."""
        stmt = select(User).where(User.user_id == user_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def create(self, auth_provider_id: str, display_name: str) -> User:
        """Persist a newly registered user account."""
        user = User(
            auth_provider_id=auth_provider_id,
            display_name=display_name,
        )
        self.session.add(user)
        await self.session.flush()
        return user

    async def update_profile(
        self,
        user: User,
        display_name: str | None = None,
        bio: str | None = None,
        avatar_url: str | None = None,
        banner_url: str | None = None,
    ) -> User:
        """Update editable profile fields for a user."""
        if display_name is not None:
            user.display_name = display_name
        if bio is not None:
            user.bio = bio
        if avatar_url is not None:
            user.avatar_url = avatar_url
        if banner_url is not None:
            user.banner_url = banner_url
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def get_player_stats(self, user_id: uuid.UUID) -> tuple[int, int, int]:
        """Aggregate campaigns played, victories won, and total turns taken."""
        base_filter = (
            Playthrough.created_by == user_id,
            Playthrough.is_playtest.is_(False),
        )
        camp_stmt = select(func.count(Playthrough.playthrough_id)).where(*base_filter)
        vic_stmt = select(func.count(Playthrough.playthrough_id)).where(
            *base_filter, Playthrough.ended_outcome_tag == "win"
        )
        turn_stmt = select(func.coalesce(func.sum(Playthrough.turn_count), 0)).where(
            *base_filter
        )
        c_count = (await self.session.execute(camp_stmt)).scalar() or 0
        v_count = (await self.session.execute(vic_stmt)).scalar() or 0
        t_count = (await self.session.execute(turn_stmt)).scalar() or 0
        return int(c_count), int(v_count), int(t_count)

    async def get_creator_stats(self, user_id: uuid.UUID) -> tuple[int, int]:
        """Aggregate published scenarios authored and total plays received."""
        base_filter = (
            Scenario.creator_id == user_id,
            Scenario.status == "published",
        )
        scen_stmt = select(func.count(Scenario.scenario_id)).where(*base_filter)
        play_stmt = select(func.coalesce(func.sum(Scenario.play_count), 0)).where(
            *base_filter
        )
        s_count = (await self.session.execute(scen_stmt)).scalar() or 0
        p_count = (await self.session.execute(play_stmt)).scalar() or 0
        return int(s_count), int(p_count)

    async def get_user_stats(self, user_id: uuid.UUID) -> dict[str, int]:
        """Fetch combined player and creator statistics."""
        c_count, v_count, t_count = await self.get_player_stats(user_id)
        s_count, p_count = await self.get_creator_stats(user_id)
        return {
            "campaigns_played_count": c_count,
            "victories_count": v_count,
            "total_turns_taken": t_count,
            "scenarios_authored_count": s_count,
            "total_plays_received": p_count,
        }

    async def list_user_reviews(
        self, user_id: uuid.UUID, limit: int = 20, offset: int = 0
    ) -> list[tuple[ScenarioReview, Scenario]]:
        """Fetch scenario reviews authored by user along with scenario metadata."""
        stmt = (
            select(ScenarioReview, Scenario)
            .join(Scenario, ScenarioReview.scenario_id == Scenario.scenario_id)
            .where(ScenarioReview.user_id == user_id)
            .order_by(ScenarioReview.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.all())
