"""Entity domain service handling business logic and scenario-ownership rules."""

import uuid

from app.db.models.entity import Entity
from app.exceptions.entity_exceptions import EntityNotFoundError
from app.exceptions.scenario_exceptions import (
    ScenarioAccessDeniedError,
    ScenarioNotFoundError,
)
from app.models.entity import EntityCreate, EntityResponse, EntityUpdate
from app.repositories.entity_repo import EntityRepo
from app.repositories.scenario_repo import ScenarioRepo


class EntityService:
    """Service handling entity authoring within a master-mode scenario."""

    def __init__(self, entity_repo: EntityRepo, scenario_repo: ScenarioRepo) -> None:
        self.entity_repo = entity_repo
        self.scenario_repo = scenario_repo

    async def create_entity(
        self, scenario_id: uuid.UUID, user_id: uuid.UUID, data: EntityCreate
    ) -> EntityResponse:
        """Create a new entity owned by the given scenario."""
        await self._ensure_scenario_owner(scenario_id, user_id)

        entity = Entity(
            scenario_id=scenario_id,
            entity_type=data.entity_type,
            canonical_name=data.canonical_name,
            aliases=data.aliases,
            description=data.description,
            obtainable=data.obtainable,
            attributes_schema={
                key: field.model_dump() for key, field in data.attributes_schema.items()
            },
            narrator_instruction=data.narrator_instruction,
        )
        created = await self.entity_repo.create(entity)
        return EntityResponse.model_validate(created)

    async def list_entities(
        self, scenario_id: uuid.UUID, user_id: uuid.UUID
    ) -> list[EntityResponse]:
        """List all entities for a scenario."""
        await self._ensure_scenario_owner(scenario_id, user_id)
        entities = await self.entity_repo.list_by_scenario(scenario_id)
        return [EntityResponse.model_validate(e) for e in entities]

    async def get_entity(
        self, scenario_id: uuid.UUID, entity_id: uuid.UUID, user_id: uuid.UUID
    ) -> EntityResponse:
        """Fetch a single entity, scoped to its owning scenario."""
        await self._ensure_scenario_owner(scenario_id, user_id)
        entity = await self._get_scoped_entity(scenario_id, entity_id)
        return EntityResponse.model_validate(entity)

    async def update_entity(
        self,
        scenario_id: uuid.UUID,
        entity_id: uuid.UUID,
        user_id: uuid.UUID,
        data: EntityUpdate,
    ) -> EntityResponse:
        """Update an entity's mutable fields."""
        await self._ensure_scenario_owner(scenario_id, user_id)
        entity = await self._get_scoped_entity(scenario_id, entity_id)

        # model_dump() recursively dumps nested AttributeFieldSchema models to
        # plain dicts, matching the JSONB column shape — no special-casing needed.
        update_dict = data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(entity, field, value)

        updated = await self.entity_repo.update(entity)
        return EntityResponse.model_validate(updated)

    async def delete_entity(
        self, scenario_id: uuid.UUID, entity_id: uuid.UUID, user_id: uuid.UUID
    ) -> None:
        """Delete an entity. Cascades to referencing facts at the DB level."""
        await self._ensure_scenario_owner(scenario_id, user_id)
        entity = await self._get_scoped_entity(scenario_id, entity_id)
        await self.entity_repo.delete(entity)

    async def _get_scoped_entity(
        self, scenario_id: uuid.UUID, entity_id: uuid.UUID
    ) -> Entity:
        """Fetch an entity, raising 404 if missing or owned by another scenario."""
        entity = await self.entity_repo.get_by_id(entity_id)
        if entity is None or entity.scenario_id != scenario_id:
            raise EntityNotFoundError()
        return entity

    async def _ensure_scenario_owner(
        self, scenario_id: uuid.UUID, user_id: uuid.UUID
    ) -> None:
        """Verify the scenario exists and the requesting user is its creator."""
        scenario = await self.scenario_repo.get_by_id(scenario_id)
        if scenario is None or scenario.status == "archived":
            raise ScenarioNotFoundError()
        if scenario.creator_id != user_id:
            raise ScenarioAccessDeniedError()
