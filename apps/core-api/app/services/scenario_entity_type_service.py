"""Scenario entity type template domain service handling business logic and
scenario-ownership rules."""

import uuid

from app.db.models.scenario_entity_type import ScenarioEntityType
from app.exceptions.scenario_entity_type_exceptions import (
    ScenarioEntityTypeInUseError,
    ScenarioEntityTypeNotFoundError,
    ScenarioEntityTypeValidationError,
)
from app.exceptions.scenario_exceptions import (
    ScenarioAccessDeniedError,
    ScenarioNotFoundError,
)
from app.models.entity import ENTITY_TYPES
from app.models.scenario_entity_type import (
    ScenarioEntityTypeCreate,
    ScenarioEntityTypeResponse,
    ScenarioEntityTypeUpdate,
)
from app.repositories.entity_repo import EntityRepo
from app.repositories.scenario_entity_type_repo import ScenarioEntityTypeRepo
from app.repositories.scenario_repo import ScenarioRepo


class ScenarioEntityTypeService:
    """Service handling custom entity type template authoring for a scenario."""

    def __init__(
        self,
        entity_type_repo: ScenarioEntityTypeRepo,
        entity_repo: EntityRepo,
        scenario_repo: ScenarioRepo,
    ) -> None:
        self.entity_type_repo = entity_type_repo
        self.entity_repo = entity_repo
        self.scenario_repo = scenario_repo

    async def create_entity_type(
        self, scenario_id: uuid.UUID, user_id: uuid.UUID, data: ScenarioEntityTypeCreate
    ) -> ScenarioEntityTypeResponse:
        """Define a new custom entity type template for a scenario."""
        await self._ensure_scenario_owner(scenario_id, user_id)
        self._ensure_key_not_builtin(data.type_key)
        await self._ensure_key_unused(scenario_id, data.type_key)

        entity_type = ScenarioEntityType(
            scenario_id=scenario_id,
            type_key=data.type_key,
            display_label=data.display_label,
            attributes_schema={
                key: field.model_dump() for key, field in data.attributes_schema.items()
            },
        )
        created = await self.entity_type_repo.create(entity_type)
        return ScenarioEntityTypeResponse.model_validate(created)

    async def list_entity_types(
        self, scenario_id: uuid.UUID, user_id: uuid.UUID
    ) -> list[ScenarioEntityTypeResponse]:
        """List all custom entity type templates for a scenario."""
        await self._ensure_scenario_owner(scenario_id, user_id)
        entity_types = await self.entity_type_repo.list_by_scenario(scenario_id)
        return [ScenarioEntityTypeResponse.model_validate(t) for t in entity_types]

    async def update_entity_type(
        self,
        scenario_id: uuid.UUID,
        scenario_entity_type_id: uuid.UUID,
        user_id: uuid.UUID,
        data: ScenarioEntityTypeUpdate,
    ) -> ScenarioEntityTypeResponse:
        """Update a custom entity type template's mutable fields."""
        await self._ensure_scenario_owner(scenario_id, user_id)
        entity_type = await self._get_scoped_entity_type(
            scenario_id, scenario_entity_type_id
        )

        update_dict = data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(entity_type, field, value)

        updated = await self.entity_type_repo.update(entity_type)
        return ScenarioEntityTypeResponse.model_validate(updated)

    async def delete_entity_type(
        self,
        scenario_id: uuid.UUID,
        scenario_entity_type_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        """Delete a custom entity type template, if no entity still uses it."""
        await self._ensure_scenario_owner(scenario_id, user_id)
        entity_type = await self._get_scoped_entity_type(
            scenario_id, scenario_entity_type_id
        )
        entities_in_use = await self.entity_repo.count_by_type(
            scenario_id, entity_type.type_key
        )
        if entities_in_use > 0:
            raise ScenarioEntityTypeInUseError()
        await self.entity_type_repo.delete(entity_type)

    def _ensure_key_not_builtin(self, type_key: str) -> None:
        """Reject a custom type key that collides with a built-in entity type."""
        if type_key in ENTITY_TYPES:
            raise ScenarioEntityTypeValidationError(
                f"'{type_key}' is a built-in entity type and cannot be redefined"
            )

    async def _ensure_key_unused(self, scenario_id: uuid.UUID, type_key: str) -> None:
        """Reject a custom type key already defined for this scenario."""
        existing = await self.entity_type_repo.get_by_type_key(scenario_id, type_key)
        if existing is not None:
            raise ScenarioEntityTypeValidationError(
                f"Entity type '{type_key}' already exists for this scenario"
            )

    async def _get_scoped_entity_type(
        self, scenario_id: uuid.UUID, scenario_entity_type_id: uuid.UUID
    ) -> ScenarioEntityType:
        """Fetch a template, raising 404 if missing or owned by another scenario."""
        entity_type = await self.entity_type_repo.get_by_id(scenario_entity_type_id)
        if entity_type is None or entity_type.scenario_id != scenario_id:
            raise ScenarioEntityTypeNotFoundError()
        return entity_type

    async def _ensure_scenario_owner(
        self, scenario_id: uuid.UUID, user_id: uuid.UUID
    ) -> None:
        """Verify the scenario exists and the requesting user is its creator."""
        scenario = await self.scenario_repo.get_by_id(scenario_id)
        if scenario is None or scenario.status == "archived":
            raise ScenarioNotFoundError()
        if scenario.creator_id != user_id:
            raise ScenarioAccessDeniedError()
