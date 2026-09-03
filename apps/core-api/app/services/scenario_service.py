"""Scenario domain service handling business logic, access rules, and versioning."""

import uuid

from app.db.models.scenario import Scenario
from app.exceptions.scenario_exceptions import (
    ScenarioAccessDeniedError,
    ScenarioAlreadyPublishingError,
    ScenarioNotFoundError,
)
from app.models.review import (
    PublicPlaythroughSummary,
    ScenarioReviewCreate,
    ScenarioReviewListResponse,
    ScenarioReviewResponse,
)
from app.models.scenario import (
    ScenarioCreate,
    ScenarioListResponse,
    ScenarioResponse,
    ScenarioSummaryResponse,
    ScenarioUpdate,
)
from app.repositories.scenario_repo import ScenarioRepo

STORY_SCHEMA_FIELDS: set[str] = {
    "narrator_persona",
    "world_data",
    "setup_schema",
    "state_schema",
    "end_conditions",
    "checkpoints",
    "rules",
}


class ScenarioService:
    """Service handling high-level scenario workflow logic."""

    def __init__(self, scenario_repo: ScenarioRepo) -> None:
        self.scenario_repo = scenario_repo

    async def create_scenario(
        self, user_id: uuid.UUID, data: ScenarioCreate
    ) -> ScenarioResponse:
        """Create a new draft scenario owned by user_id."""
        scenario = Scenario(
            creator_id=user_id,
            title=data.title,
            mode=data.mode,
            complexity_tier=data.complexity_tier,
            logline=data.logline,
            player_count_support=data.player_count_support,
            estimated_playtime=data.estimated_playtime,
            cover_image_url=data.cover_image_url,
            content_tag=data.content_tag,
            genre_tags=data.genre_tags,
            narrator_persona=data.narrator_persona,
            world_data=data.world_data,
            setup_schema=data.setup_schema,
            state_schema=data.state_schema,
            end_conditions=data.end_conditions,
            checkpoints=data.checkpoints,
            rules=data.rules,
            status="draft",
            current_version=1,
        )
        created_scenario = await self.scenario_repo.create(scenario)
        return ScenarioResponse.model_validate(created_scenario)

    async def get_scenario(
        self, scenario_id: uuid.UUID, current_user_id: uuid.UUID | None = None
    ) -> ScenarioResponse:
        """Fetch scenario by ID enforcing draft visibility rules."""
        scenario = await self.scenario_repo.get_by_id(scenario_id)
        if not scenario or scenario.status == "archived":
            raise ScenarioNotFoundError()

        if scenario.status == "draft":
            self._ensure_creator_access(scenario, current_user_id, hide_as_404=True)

        creator_name = await self.scenario_repo.get_creator_display_name(
            scenario.creator_id
        )
        is_bookmarked = False
        can_review = False

        if current_user_id:
            is_bookmarked = await self.scenario_repo.is_bookmarked(
                current_user_id, scenario_id
            )
            can_review = await self.scenario_repo.has_user_played_min_turns(
                current_user_id, scenario_id, min_turns=10
            )

        response = ScenarioResponse.model_validate(scenario)
        response.creator_display_name = creator_name or "Anonymous Creator"
        response.is_bookmarked = is_bookmarked
        response.can_review = can_review
        return response

    async def toggle_bookmark(self, user_id: uuid.UUID, scenario_id: uuid.UUID) -> bool:
        """Toggle scenario bookmark for user. Returns new bookmarked state."""
        scenario = await self.scenario_repo.get_by_id(scenario_id)
        if not scenario or scenario.status == "archived":
            raise ScenarioNotFoundError()

        is_currently_bookmarked = await self.scenario_repo.is_bookmarked(
            user_id, scenario_id
        )
        if is_currently_bookmarked:
            await self.scenario_repo.remove_bookmark(user_id, scenario_id)
            return False
        await self.scenario_repo.add_bookmark(user_id, scenario_id)
        return True

    async def list_reviews(
        self, scenario_id: uuid.UUID, limit: int = 20, offset: int = 0
    ) -> ScenarioReviewListResponse:
        """Fetch list of reviews for a scenario."""
        scenario = await self.scenario_repo.get_by_id(scenario_id)
        if not scenario or scenario.status == "archived":
            raise ScenarioNotFoundError()

        items, total_count, avg_rating = await self.scenario_repo.list_reviews(
            scenario_id, limit, offset
        )
        review_responses = [
            ScenarioReviewResponse(
                review_id=rev.review_id,
                scenario_id=rev.scenario_id,
                user_id=rev.user_id,
                user_display_name=display_name,
                rating=rev.rating,
                comment=rev.comment,
                created_at=rev.created_at,
            )
            for rev, display_name in items
        ]
        return ScenarioReviewListResponse(
            items=review_responses,
            total_count=total_count,
            average_rating=avg_rating,
        )

    async def add_review(
        self, user_id: uuid.UUID, scenario_id: uuid.UUID, data: ScenarioReviewCreate
    ) -> ScenarioReviewResponse:
        """Submit a rating and review after validating user has played >= 10 turns."""
        scenario = await self.scenario_repo.get_by_id(scenario_id)
        if not scenario or scenario.status == "archived":
            raise ScenarioNotFoundError()

        has_min_turns = await self.scenario_repo.has_user_played_min_turns(
            user_id, scenario_id, min_turns=10
        )
        if not has_min_turns:
            raise ScenarioAccessDeniedError(
                "You must play at least 10 turns of this scenario before leaving a review."
            )

        review, display_name = await self.scenario_repo.create_or_update_review(
            user_id=user_id,
            scenario_id=scenario_id,
            rating=data.rating,
            comment=data.comment,
        )
        return ScenarioReviewResponse(
            review_id=review.review_id,
            scenario_id=review.scenario_id,
            user_id=review.user_id,
            user_display_name=display_name,
            rating=review.rating,
            comment=review.comment,
            created_at=review.created_at,
        )

    async def list_public_playthroughs(
        self, scenario_id: uuid.UUID, limit: int = 10
    ) -> list[PublicPlaythroughSummary]:
        """Fetch list of active/completed public playthroughs for scenario."""
        scenario = await self.scenario_repo.get_by_id(scenario_id)
        if not scenario or scenario.status == "archived":
            raise ScenarioNotFoundError()

        results = await self.scenario_repo.list_public_playthroughs(scenario_id, limit)
        summaries: list[PublicPlaythroughSummary] = []
        for pt, player_name in results:
            char_name = None
            if isinstance(pt.state, dict) and "character" in pt.state:
                char_data = pt.state["character"]
                if isinstance(char_data, dict):
                    char_name = char_data.get("name")
            summaries.append(
                PublicPlaythroughSummary(
                    playthrough_id=pt.playthrough_id,
                    player_name=player_name,
                    character_name=char_name,
                    turn_count=pt.turn_count,
                    status=pt.status,
                    updated_at=pt.updated_at,
                )
            )
        return summaries

    async def update_scenario(
        self,
        scenario_id: uuid.UUID,
        user_id: uuid.UUID,
        data: ScenarioUpdate,
    ) -> ScenarioResponse:
        """Update scenario fields and selectively increment story version."""
        scenario = await self.scenario_repo.get_by_id(scenario_id)
        if not scenario or scenario.status == "archived":
            raise ScenarioNotFoundError()

        is_draft = scenario.status == "draft"
        self._ensure_creator_access(scenario, user_id, hide_as_404=is_draft)

        if scenario.status == "publishing":
            raise ScenarioAlreadyPublishingError(
                "Cannot edit a scenario while it is being published"
            )

        should_bump_version = False
        update_dict = data.model_dump(exclude_unset=True)

        for field, value in update_dict.items():
            if field in STORY_SCHEMA_FIELDS and getattr(scenario, field) != value:
                should_bump_version = True
            setattr(scenario, field, value)

        if should_bump_version:
            scenario.current_version += 1

        updated_scenario = await self.scenario_repo.update(scenario)
        return ScenarioResponse.model_validate(updated_scenario)

    async def delete_scenario(self, scenario_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Hard delete if 0 playthroughs exist, else soft-delete / archive."""
        scenario = await self.scenario_repo.get_by_id(scenario_id)
        if not scenario or scenario.status == "archived":
            raise ScenarioNotFoundError()

        is_draft = scenario.status == "draft"
        self._ensure_creator_access(scenario, user_id, hide_as_404=is_draft)

        playthrough_count = await self.scenario_repo.count_playthroughs(scenario_id)
        if playthrough_count == 0:
            await self.scenario_repo.delete(scenario)
        else:
            scenario.status = "archived"
            await self.scenario_repo.update(scenario)

    async def list_scenarios(
        self,
        current_user_id: uuid.UUID | None = None,
        mine: bool = False,
        genre_tags: list[str] | None = None,
        complexity_tier: str | None = None,
        player_count_support: str | None = None,
        sort_by: str = "created_at",
        limit: int = 20,
        offset: int = 0,
    ) -> ScenarioListResponse:
        """List published scenarios for discovery or creator's own scenarios."""
        creator_id = current_user_id if mine else None

        if mine and current_user_id is None:
            raise ScenarioAccessDeniedError("Must be logged in to view my scenarios")

        items, total_count = await self.scenario_repo.list_scenarios(
            creator_id=creator_id,
            published_only=not mine,
            genre_tags=genre_tags,
            complexity_tier=complexity_tier,
            player_count_support=player_count_support,
            sort_by=sort_by,
            limit=limit,
            offset=offset,
        )

        summaries = [ScenarioSummaryResponse.model_validate(item) for item in items]
        next_offset = offset + limit if offset + limit < total_count else None
        next_cursor = str(next_offset) if next_offset is not None else None

        return ScenarioListResponse(
            items=summaries, next_cursor=next_cursor, total_count=total_count
        )

    def _ensure_creator_access(
        self,
        scenario: Scenario,
        user_id: uuid.UUID | None,
        hide_as_404: bool = False,
    ) -> None:
        """Verify user is the scenario creator."""
        if user_id is None or scenario.creator_id != user_id:
            if hide_as_404:
                raise ScenarioNotFoundError()
            raise ScenarioAccessDeniedError()
