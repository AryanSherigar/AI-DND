"""Scenario domain service handling business logic, access rules, and versioning."""

import uuid

from app.db.models.end_condition import EndCondition
from app.db.models.entity import Entity
from app.db.models.fact import Fact
from app.db.models.rule_invariant import RuleInvariant
from app.db.models.scenario import Scenario
from app.db.models.scenario_condition import ScenarioCondition
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
from app.repositories.condition_repo import ConditionRepo
from app.repositories.end_condition_repo import EndConditionRepo
from app.repositories.entity_repo import EntityRepo
from app.repositories.fact_repo import FactRepo
from app.repositories.invariant_repo import InvariantRepo
from app.repositories.scenario_repo import ScenarioRepo

STORY_SCHEMA_FIELDS: set[str] = {
    "narrator_persona",
    "world_data",
    "setup_schema",
    "state_schema",
    "end_conditions",
    "checkpoints",
    "rules",
    "opening_scene",
    "narration_font",
    "action_chips",
    "setup_archetypes",
}


class ScenarioService:
    """Service handling high-level scenario workflow logic."""

    def __init__(
        self,
        scenario_repo: ScenarioRepo,
        entity_repo: EntityRepo | None = None,
        fact_repo: FactRepo | None = None,
        condition_repo: ConditionRepo | None = None,
        end_condition_repo: EndConditionRepo | None = None,
        invariant_repo: InvariantRepo | None = None,
    ) -> None:
        self.scenario_repo = scenario_repo
        # Sub-resource repos are optional constructor args (rather than
        # required) so every existing call site that only ever needed
        # scenario CRUD (most of the codebase and its tests) is unaffected;
        # they're only exercised by duplicate_scenario. Built from the same
        # session scenario_repo already holds, per the "repositories are the
        # only place that opens SQL" layering rule.
        session = scenario_repo.session
        self.entity_repo = entity_repo or EntityRepo(session)
        self.fact_repo = fact_repo or FactRepo(session)
        self.condition_repo = condition_repo or ConditionRepo(session)
        self.end_condition_repo = end_condition_repo or EndConditionRepo(session)
        self.invariant_repo = invariant_repo or InvariantRepo(session)

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
            opening_scene=data.opening_scene,
            narration_font=data.narration_font,
            action_chips=data.action_chips,
            setup_archetypes=data.setup_archetypes,
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

    async def duplicate_scenario(
        self, scenario_id: uuid.UUID, user_id: uuid.UUID
    ) -> ScenarioResponse:
        """Deep-copy a scenario and its master-mode sub-resources as a new
        draft owned by the caller. Only the source scenario's owner may
        duplicate it (same ownership rule as update_scenario/delete_scenario).

        Note: entity references inside condition_expression/
        invariant_expression/state_mutation JSON are creator-facing dot-paths
        (e.g. "the_warden.health"), not entity UUIDs, so those JSON blobs are
        copied verbatim with no ID remap. Only Fact.subject_entity_id/
        object_entity_id (real FK columns) need remapping to the copied
        entities' new IDs.
        """
        source = await self.scenario_repo.get_by_id(scenario_id)
        if not source or source.status == "archived":
            raise ScenarioNotFoundError()
        self._ensure_creator_access(source, user_id)

        new_scenario = await self.scenario_repo.create(
            _build_scenario_copy(source, user_id)
        )
        if source.mode == "master":
            entity_id_map = await self._copy_entities(
                source.scenario_id, new_scenario.scenario_id
            )
            await self._copy_facts(
                source.scenario_id, new_scenario.scenario_id, entity_id_map
            )
            await self._copy_conditions(source.scenario_id, new_scenario.scenario_id)
            await self._copy_end_conditions(
                source.scenario_id, new_scenario.scenario_id
            )
            await self._copy_invariants(source.scenario_id, new_scenario.scenario_id)

        return ScenarioResponse.model_validate(new_scenario)

    async def _copy_entities(
        self, source_scenario_id: uuid.UUID, new_scenario_id: uuid.UUID
    ) -> dict[uuid.UUID, uuid.UUID]:
        """Deep-copy every entity for a scenario. Returns old->new entity ID map."""
        source_entities = await self.entity_repo.list_by_scenario(source_scenario_id)
        id_map: dict[uuid.UUID, uuid.UUID] = {}
        for entity in source_entities:
            copy = _build_entity_copy(entity, new_scenario_id)
            id_map[entity.entity_id] = copy.entity_id
            await self.entity_repo.create(copy)
        return id_map

    async def _copy_facts(
        self,
        source_scenario_id: uuid.UUID,
        new_scenario_id: uuid.UUID,
        entity_id_map: dict[uuid.UUID, uuid.UUID],
    ) -> None:
        """Deep-copy facts, remapping entity FKs immediately and superseded-
        fact FKs in a second pass once every fact's new ID is known."""
        source_facts = await self.fact_repo.list_by_scenario(source_scenario_id)
        fact_id_map: dict[uuid.UUID, uuid.UUID] = {}
        new_facts: list[Fact] = []
        for fact in source_facts:
            copy = _build_fact_copy(fact, new_scenario_id, entity_id_map)
            fact_id_map[fact.fact_id] = copy.fact_id
            new_facts.append(await self.fact_repo.create(copy))
        await self._relink_superseded_facts(source_facts, new_facts, fact_id_map)

    async def _relink_superseded_facts(
        self,
        source_facts: list[Fact],
        new_facts: list[Fact],
        fact_id_map: dict[uuid.UUID, uuid.UUID],
    ) -> None:
        """Point each copied fact's superseded_fact_id at its copied sibling."""
        for source_fact, new_fact in zip(source_facts, new_facts, strict=True):
            if source_fact.superseded_fact_id is None:
                continue
            new_fact.superseded_fact_id = fact_id_map.get(
                source_fact.superseded_fact_id
            )
            await self.fact_repo.update(new_fact)

    async def _copy_conditions(
        self, source_scenario_id: uuid.UUID, new_scenario_id: uuid.UUID
    ) -> None:
        """Deep-copy active conditions verbatim (no entity-ID remap needed)."""
        source_conditions = await self.condition_repo.list_by_scenario(
            source_scenario_id
        )
        for condition in source_conditions:
            await self.condition_repo.create(
                _build_condition_copy(condition, new_scenario_id)
            )

    async def _copy_end_conditions(
        self, source_scenario_id: uuid.UUID, new_scenario_id: uuid.UUID
    ) -> None:
        """Deep-copy end conditions verbatim, preserving priority order."""
        source_end_conditions = await self.end_condition_repo.list_by_scenario(
            source_scenario_id
        )
        for end_condition in source_end_conditions:
            await self.end_condition_repo.create(
                _build_end_condition_copy(end_condition, new_scenario_id)
            )

    async def _copy_invariants(
        self, source_scenario_id: uuid.UUID, new_scenario_id: uuid.UUID
    ) -> None:
        """Deep-copy rule invariants verbatim (no entity-ID remap needed)."""
        source_invariants = await self.invariant_repo.list_by_scenario(
            source_scenario_id
        )
        for invariant in source_invariants:
            await self.invariant_repo.create(
                _build_invariant_copy(invariant, new_scenario_id)
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


def _build_scenario_copy(source: Scenario, user_id: uuid.UUID) -> Scenario:
    """Build the new draft Scenario row for a duplicate, forcing status=draft
    and resetting publish/discovery-derived fields."""
    return Scenario(
        creator_id=user_id,
        title=f"{source.title} (Copy)",
        logline=source.logline,
        mode=source.mode,
        world_data=source.world_data,
        status="draft",
        genre_tags=list(source.genre_tags),
        complexity_tier=source.complexity_tier,
        player_count_support=source.player_count_support,
        estimated_playtime=source.estimated_playtime,
        cover_image_url=source.cover_image_url,
        content_tag=source.content_tag,
        narrator_persona=source.narrator_persona,
        setup_schema=source.setup_schema,
        state_schema=source.state_schema,
        end_conditions=source.end_conditions,
        checkpoints=source.checkpoints,
        rules=source.rules,
        opening_scene=source.opening_scene,
        narration_font=source.narration_font,
        action_chips=list(source.action_chips),
        setup_archetypes=source.setup_archetypes,
        current_version=1,
    )


def _build_entity_copy(entity: Entity, new_scenario_id: uuid.UUID) -> Entity:
    """Build a copied Entity row with a new ID under new_scenario_id."""
    return Entity(
        entity_id=uuid.uuid4(),
        scenario_id=new_scenario_id,
        entity_type=entity.entity_type,
        canonical_name=entity.canonical_name,
        aliases=list(entity.aliases),
        description=entity.description,
        obtainable=entity.obtainable,
        attributes_schema=entity.attributes_schema,
        narrator_instruction=entity.narrator_instruction,
    )


def _build_fact_copy(
    fact: Fact,
    new_scenario_id: uuid.UUID,
    entity_id_map: dict[uuid.UUID, uuid.UUID],
) -> Fact:
    """Build a copied Fact row, remapping subject/object entity FKs to their
    copied entities. superseded_fact_id is relinked by the caller once every
    fact in the batch has a new ID."""
    return Fact(
        fact_id=uuid.uuid4(),
        scenario_id=new_scenario_id,
        subject_entity_id=entity_id_map[fact.subject_entity_id],
        predicate=fact.predicate,
        object_entity_id=(
            entity_id_map.get(fact.object_entity_id) if fact.object_entity_id else None
        ),
        object_literal=fact.object_literal,
        valid_from=fact.valid_from,
        when_active=fact.when_active,
        hidden=fact.hidden,
        metadata_=fact.metadata_,
    )


def _build_condition_copy(
    condition: ScenarioCondition, new_scenario_id: uuid.UUID
) -> ScenarioCondition:
    """Build a copied ScenarioCondition row (expression fields are dot-path
    strings, not entity IDs, so they're copied verbatim)."""
    return ScenarioCondition(
        condition_id=uuid.uuid4(),
        scenario_id=new_scenario_id,
        label=condition.label,
        condition_expression=condition.condition_expression,
        condition_version=condition.condition_version,
        narrator_instruction=condition.narrator_instruction,
        metadata_=condition.metadata_,
        state_mutation=condition.state_mutation,
    )


def _build_end_condition_copy(
    end_condition: EndCondition, new_scenario_id: uuid.UUID
) -> EndCondition:
    """Build a copied EndCondition row, preserving its priority."""
    return EndCondition(
        end_condition_id=uuid.uuid4(),
        scenario_id=new_scenario_id,
        condition_expression=end_condition.condition_expression,
        outcome_tag=end_condition.outcome_tag,
        outcome_title=end_condition.outcome_title,
        outcome_text=end_condition.outcome_text,
        is_secret=end_condition.is_secret,
        priority=end_condition.priority,
    )


def _build_invariant_copy(
    invariant: RuleInvariant, new_scenario_id: uuid.UUID
) -> RuleInvariant:
    """Build a copied RuleInvariant row (expression fields are dot-path
    strings, not entity IDs, so they're copied verbatim)."""
    return RuleInvariant(
        invariant_id=uuid.uuid4(),
        scenario_id=new_scenario_id,
        label=invariant.label,
        invariant_expression=invariant.invariant_expression,
        applies_to=invariant.applies_to,
        narrator_text=invariant.narrator_text,
    )
