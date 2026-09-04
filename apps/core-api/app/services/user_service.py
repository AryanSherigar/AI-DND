"""User domain service managing profile queries, updates, campaigns, and reviews."""

import uuid

import structlog

from app.exceptions.user_exceptions import UserNotFoundError
from app.models.user import (
    UserPlaythroughSummary,
    UserProfileResponse,
    UserProfileUpdate,
    UserPublicProfileResponse,
    UserReviewSummary,
    UserStatsResponse,
)
from app.repositories.playthrough_repo import PlaythroughRepo
from app.repositories.user_repo import UserRepo

logger = structlog.get_logger()


def _extract_character_info(state: dict[str, object]) -> tuple[str | None, str | None]:
    """Extract character name and archetype from playthrough state setup dictionary."""
    setup = state.get("setup")
    if not isinstance(setup, dict):
        return None, None
    name = setup.get("character_name") or setup.get("name")
    archetype = setup.get("archetype") or setup.get("class") or setup.get("role")
    name_str = str(name) if name is not None else None
    archetype_str = str(archetype) if archetype is not None else None
    return name_str, archetype_str


class UserService:
    """Domain service for user profile data and activity summaries."""

    def __init__(self, user_repo: UserRepo, playthrough_repo: PlaythroughRepo) -> None:
        self.user_repo = user_repo
        self.playthrough_repo = playthrough_repo

    async def get_my_profile(self, user_id: uuid.UUID) -> UserProfileResponse:
        """Retrieve full profile including auth provider ID for current user."""
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise UserNotFoundError()
        stats_dict = await self.user_repo.get_user_stats(user_id)
        stats = UserStatsResponse(**stats_dict)
        return UserProfileResponse(
            user_id=user.user_id,
            display_name=user.display_name,
            bio=user.bio,
            avatar_url=user.avatar_url,
            banner_url=user.banner_url,
            created_at=user.created_at,
            auth_provider_id=user.auth_provider_id,
            stats=stats,
        )

    async def get_public_profile(self, user_id: uuid.UUID) -> UserPublicProfileResponse:
        """Retrieve publicly visible profile and statistics for any user."""
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise UserNotFoundError()
        stats_dict = await self.user_repo.get_user_stats(user_id)
        stats = UserStatsResponse(**stats_dict)
        return UserPublicProfileResponse(
            user_id=user.user_id,
            display_name=user.display_name,
            bio=user.bio,
            avatar_url=user.avatar_url,
            banner_url=user.banner_url,
            created_at=user.created_at,
            stats=stats,
        )

    async def update_profile(
        self, user_id: uuid.UUID, data: UserProfileUpdate
    ) -> UserProfileResponse:
        """Update profile fields and return updated profile."""
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise UserNotFoundError()
        updated_user = await self.user_repo.update_profile(
            user=user,
            display_name=data.display_name,
            bio=data.bio,
            avatar_url=data.avatar_url,
            banner_url=data.banner_url,
        )
        stats_dict = await self.user_repo.get_user_stats(user_id)
        stats = UserStatsResponse(**stats_dict)
        logger.info("user_profile_updated", user_id=str(user_id))
        return UserProfileResponse(
            user_id=updated_user.user_id,
            display_name=updated_user.display_name,
            bio=updated_user.bio,
            avatar_url=updated_user.avatar_url,
            banner_url=updated_user.banner_url,
            created_at=updated_user.created_at,
            auth_provider_id=updated_user.auth_provider_id,
            stats=stats,
        )

    async def list_user_playthroughs(
        self, user_id: uuid.UUID, status: str | None = None
    ) -> list[UserPlaythroughSummary]:
        """Fetch all playthroughs for a user with scenario details and character info."""
        records = await self.playthrough_repo.list_by_user_with_scenarios(
            created_by=user_id, status=status
        )
        summaries: list[UserPlaythroughSummary] = []
        for pt, scen in records:
            char_name, char_archetype = _extract_character_info(pt.state)
            summaries.append(
                UserPlaythroughSummary(
                    playthrough_id=pt.playthrough_id,
                    scenario_id=scen.scenario_id,
                    scenario_title=scen.title,
                    scenario_mode=scen.mode,
                    cover_image_url=scen.cover_image_url,
                    turn_count=pt.turn_count,
                    status=pt.status,
                    ended_outcome_tag=pt.ended_outcome_tag,
                    ended_outcome_title=pt.ended_outcome_title,
                    ended_outcome_text=pt.ended_outcome_text,
                    character_name=char_name,
                    character_archetype=char_archetype,
                    created_at=pt.created_at,
                    updated_at=pt.updated_at,
                )
            )
        return summaries

    async def list_user_reviews(
        self, user_id: uuid.UUID, limit: int = 20, offset: int = 0
    ) -> list[UserReviewSummary]:
        """List reviews written by a user along with scenario titles."""
        reviews = await self.user_repo.list_user_reviews(
            user_id=user_id, limit=limit, offset=offset
        )
        return [
            UserReviewSummary(
                review_id=rev.review_id,
                scenario_id=scen.scenario_id,
                scenario_title=scen.title,
                rating=rev.rating,
                review_text=rev.comment,
                created_at=rev.created_at,
            )
            for rev, scen in reviews
        ]
