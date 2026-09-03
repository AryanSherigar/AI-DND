"""Active-condition (ScenarioCondition) domain service: business logic,
Effect C state_mutation, and expression field-reference validation."""

import uuid

from app.db.models.scenario import Scenario
from app.db.models.scenario_condition import ScenarioCondition
from app.exceptions.condition_exceptions import (
    ConditionNotFoundError,
    ConditionValidationError,
)
from app.exceptions.scenario_exceptions import (
    ScenarioAccessDeniedError,
    ScenarioNotFoundError,
)
from app.models.condition import ConditionCreate, ConditionResponse, ConditionUpdate
from app.repositories.condition_repo import ConditionRepo
from app.repositories.entity_repo import EntityRepo
from app.repositories.scenario_repo import ScenarioRepo
from app.services.expression_validation import validate_expression_field_references


class ConditionService:
    """Service handling active-condition authoring within a master-mode scenario."""

    def __init__(
        self,
        condition_repo: ConditionRepo,
        entity_repo: EntityRepo,
        scenario_repo: ScenarioRepo,
    ) -> None:
        self.condition_repo = condition_repo
        self.entity_repo = entity_repo
        self.scenario_repo = scenario_repo

    async def create_condition(
        self, scenario_id: uuid.UUID, user_id: uuid.UUID, data: ConditionCreate
    ) -> ConditionResponse:
        """Create a new active condition owned by the given scenario."""
        scenario = await self._ensure_scenario_owner(scenario_id, user_id)
        await self._validate_references(scenario_id, scenario, data)

        condition = ScenarioCondition(
            scenario_id=scenario_id,
            label=data.label,
            condition_expression=data.condition_expression,
            narrator_instruction=data.narrator_instruction,
            metadata_=data.metadata,
            state_mutation=data.state_mutation.model_dump()
            if data.state_mutation
            else None,
        )
        created = await self.condition_repo.create(condition)
        return ConditionResponse.model_validate(created)

    async def list_conditions(
        self, scenario_id: uuid.UUID, user_id: uuid.UUID
    ) -> list[ConditionResponse]:
        """List all active conditions for a scenario."""
        await self._ensure_scenario_owner(scenario_id, user_id)
        conditions = await self.condition_repo.list_by_scenario(scenario_id)
        return [ConditionResponse.model_validate(c) for c in conditions]

    async def get_condition(
        self, scenario_id: uuid.UUID, condition_id: uuid.UUID, user_id: uuid.UUID
    ) -> ConditionResponse:
        """Fetch a single active condition, scoped to its owning scenario."""
        await self._ensure_scenario_owner(scenario_id, user_id)
        condition = await self._get_scoped_condition(scenario_id, condition_id)
        return ConditionResponse.model_validate(condition)

    async def update_condition(
        self,
        scenario_id: uuid.UUID,
        condition_id: uuid.UUID,
        user_id: uuid.UUID,
        data: ConditionUpdate,
    ) -> ConditionResponse:
        """Update an active condition's mutable fields."""
        scenario = await self._ensure_scenario_owner(scenario_id, user_id)
        condition = await self._get_scoped_condition(scenario_id, condition_id)
        await self._validate_references(scenario_id, scenario, data)

        update_dict = data.model_dump(exclude_unset=True)
        if "state_mutation" in update_dict:
            update_dict["state_mutation"] = (
                data.state_mutation.model_dump() if data.state_mutation else None
            )
        if "metadata" in update_dict:
            update_dict["metadata_"] = update_dict.pop("metadata")

        for field, value in update_dict.items():
            setattr(condition, field, value)

        updated = await self.condition_repo.update(condition)
        return ConditionResponse.model_validate(updated)

    async def delete_condition(
        self, scenario_id: uuid.UUID, condition_id: uuid.UUID, user_id: uuid.UUID
    ) -> None:
        """Delete an active condition."""
        await self._ensure_scenario_owner(scenario_id, user_id)
        condition = await self._get_scoped_condition(scenario_id, condition_id)
        await self.condition_repo.delete(condition)

    async def _validate_references(
        self,
        scenario_id: uuid.UUID,
        scenario: Scenario,
        data: ConditionCreate | ConditionUpdate,
    ) -> None:
        """Validate condition_expression and state_mutation field references."""
        if data.condition_expression is None and data.state_mutation is None:
            return
        entities = await self.entity_repo.list_by_scenario(scenario_id)
        entities_by_id = {e.entity_id: e for e in entities}
        state_schema: dict[str, object] = scenario.state_schema

        if data.condition_expression is not None:
            validate_expression_field_references(
                data.condition_expression,
                state_schema,
                entities_by_id,
                ConditionValidationError,
            )
        if data.state_mutation is not None:
            validate_expression_field_references(
                {"field": data.state_mutation.path},
                state_schema,
                entities_by_id,
                ConditionValidationError,
            )

    async def _get_scoped_condition(
        self, scenario_id: uuid.UUID, condition_id: uuid.UUID
    ) -> ScenarioCondition:
        """Fetch a condition, raising 404 if missing or owned by another scenario."""
        condition = await self.condition_repo.get_by_id(condition_id)
        if condition is None or condition.scenario_id != scenario_id:
            raise ConditionNotFoundError()
        return condition

    async def _ensure_scenario_owner(
        self, scenario_id: uuid.UUID, user_id: uuid.UUID
    ) -> Scenario:
        """Verify the scenario exists and the requesting user is its creator."""
        scenario = await self.scenario_repo.get_by_id(scenario_id)
        if scenario is None or scenario.status == "archived":
            raise ScenarioNotFoundError()
        if scenario.creator_id != user_id:
            raise ScenarioAccessDeniedError()
        return scenario
