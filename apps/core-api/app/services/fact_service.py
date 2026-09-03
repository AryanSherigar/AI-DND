"""Fact domain service handling business logic, reference validation, and
scenario-ownership rules."""

import uuid

from app.db.models.fact import Fact
from app.exceptions.fact_exceptions import (
    FactInvalidReferenceError,
    FactNotFoundError,
    FactValidationError,
)
from app.exceptions.scenario_exceptions import (
    ScenarioAccessDeniedError,
    ScenarioNotFoundError,
)
from app.models.fact import FactCreate, FactResponse, FactUpdate
from app.repositories.entity_repo import EntityRepo
from app.repositories.fact_repo import FactRepo
from app.repositories.scenario_repo import ScenarioRepo


class FactService:
    """Service handling fact authoring within a master-mode scenario."""

    def __init__(
        self, fact_repo: FactRepo, entity_repo: EntityRepo, scenario_repo: ScenarioRepo
    ) -> None:
        self.fact_repo = fact_repo
        self.entity_repo = entity_repo
        self.scenario_repo = scenario_repo

    async def create_fact(
        self, scenario_id: uuid.UUID, user_id: uuid.UUID, data: FactCreate
    ) -> FactResponse:
        """Create a new fact owned by the given scenario."""
        await self._ensure_scenario_owner(scenario_id, user_id)
        self._ensure_object_exclusive(data.object_entity_id, data.object_literal)
        await self._ensure_entity_in_scenario(scenario_id, data.subject_entity_id)
        if data.object_entity_id is not None:
            await self._ensure_entity_in_scenario(scenario_id, data.object_entity_id)
        if data.superseded_fact_id is not None:
            await self._ensure_fact_in_scenario(scenario_id, data.superseded_fact_id)

        fact = Fact(
            scenario_id=scenario_id,
            subject_entity_id=data.subject_entity_id,
            predicate=data.predicate,
            object_entity_id=data.object_entity_id,
            object_literal=data.object_literal,
            valid_from=data.valid_from,
            when_active=data.when_active,
            hidden=data.hidden,
            superseded_fact_id=data.superseded_fact_id,
        )
        created = await self.fact_repo.create(fact)
        return FactResponse.model_validate(created)

    async def list_facts(
        self, scenario_id: uuid.UUID, user_id: uuid.UUID
    ) -> list[FactResponse]:
        """List all facts for a scenario."""
        await self._ensure_scenario_owner(scenario_id, user_id)
        facts = await self.fact_repo.list_by_scenario(scenario_id)
        return [FactResponse.model_validate(f) for f in facts]

    async def get_fact(
        self, scenario_id: uuid.UUID, fact_id: uuid.UUID, user_id: uuid.UUID
    ) -> FactResponse:
        """Fetch a single fact, scoped to its owning scenario."""
        await self._ensure_scenario_owner(scenario_id, user_id)
        fact = await self._get_scoped_fact(scenario_id, fact_id)
        return FactResponse.model_validate(fact)

    async def update_fact(
        self,
        scenario_id: uuid.UUID,
        fact_id: uuid.UUID,
        user_id: uuid.UUID,
        data: FactUpdate,
    ) -> FactResponse:
        """Update a fact's mutable fields."""
        await self._ensure_scenario_owner(scenario_id, user_id)
        fact = await self._get_scoped_fact(scenario_id, fact_id)

        update_dict = data.model_dump(exclude_unset=True)
        next_object_entity_id = update_dict.get(
            "object_entity_id", fact.object_entity_id
        )
        next_object_literal = update_dict.get("object_literal", fact.object_literal)
        self._ensure_object_exclusive(next_object_entity_id, next_object_literal)

        if "object_entity_id" in update_dict and next_object_entity_id is not None:
            await self._ensure_entity_in_scenario(scenario_id, next_object_entity_id)
        if "superseded_fact_id" in update_dict:
            self._ensure_no_self_supersession(
                fact_id, update_dict["superseded_fact_id"]
            )
            if update_dict["superseded_fact_id"] is not None:
                await self._ensure_fact_in_scenario(
                    scenario_id, update_dict["superseded_fact_id"]
                )

        for field, value in update_dict.items():
            setattr(fact, field, value)

        updated = await self.fact_repo.update(fact)
        return FactResponse.model_validate(updated)

    async def delete_fact(
        self, scenario_id: uuid.UUID, fact_id: uuid.UUID, user_id: uuid.UUID
    ) -> None:
        """Delete a fact."""
        await self._ensure_scenario_owner(scenario_id, user_id)
        fact = await self._get_scoped_fact(scenario_id, fact_id)
        await self.fact_repo.delete(fact)

    def _ensure_object_exclusive(
        self, object_entity_id: uuid.UUID | None, object_literal: str | None
    ) -> None:
        """Reject a fact whose object is neither or both of entity/literal."""
        has_entity = object_entity_id is not None
        has_literal = object_literal is not None
        if has_entity == has_literal:
            raise FactValidationError(
                "Exactly one of object_entity_id or object_literal must be set"
            )

    def _ensure_no_self_supersession(
        self, fact_id: uuid.UUID, superseded_fact_id: uuid.UUID | None
    ) -> None:
        """Reject a fact update that would make it supersede itself."""
        if superseded_fact_id == fact_id:
            raise FactValidationError("A fact cannot supersede itself")

    async def _ensure_entity_in_scenario(
        self, scenario_id: uuid.UUID, entity_id: uuid.UUID
    ) -> None:
        """Verify an entity exists and belongs to this scenario."""
        entity = await self.entity_repo.get_by_id(entity_id)
        if entity is None or entity.scenario_id != scenario_id:
            raise FactInvalidReferenceError(
                f"Entity {entity_id} does not belong to this scenario"
            )

    async def _ensure_fact_in_scenario(
        self, scenario_id: uuid.UUID, fact_id: uuid.UUID
    ) -> None:
        """Verify a (superseded) fact exists and belongs to this scenario."""
        fact = await self.fact_repo.get_by_id(fact_id)
        if fact is None or fact.scenario_id != scenario_id:
            raise FactInvalidReferenceError(
                f"Fact {fact_id} does not belong to this scenario"
            )

    async def _get_scoped_fact(
        self, scenario_id: uuid.UUID, fact_id: uuid.UUID
    ) -> Fact:
        """Fetch a fact, raising 404 if missing or owned by another scenario."""
        fact = await self.fact_repo.get_by_id(fact_id)
        if fact is None or fact.scenario_id != scenario_id:
            raise FactNotFoundError()
        return fact

    async def _ensure_scenario_owner(
        self, scenario_id: uuid.UUID, user_id: uuid.UUID
    ) -> None:
        """Verify the scenario exists and the requesting user is its creator."""
        scenario = await self.scenario_repo.get_by_id(scenario_id)
        if scenario is None or scenario.status == "archived":
            raise ScenarioNotFoundError()
        if scenario.creator_id != user_id:
            raise ScenarioAccessDeniedError()
