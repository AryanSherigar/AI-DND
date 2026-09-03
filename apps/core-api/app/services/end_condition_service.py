"""EndCondition domain service: business logic, priority reordering, and
expression field-reference validation."""

import uuid

from app.db.models.end_condition import EndCondition
from app.db.models.scenario import Scenario
from app.exceptions.end_condition_exceptions import (
    EndConditionNotFoundError,
    EndConditionValidationError,
)
from app.exceptions.scenario_exceptions import (
    ScenarioAccessDeniedError,
    ScenarioNotFoundError,
)
from app.models.end_condition import (
    EndConditionCreate,
    EndConditionResponse,
    EndConditionUpdate,
)
from app.repositories.end_condition_repo import EndConditionRepo
from app.repositories.entity_repo import EntityRepo
from app.repositories.scenario_repo import ScenarioRepo
from app.services.expression_validation import validate_expression_field_references


class EndConditionService:
    """Service handling win/lose end-condition authoring for a master-mode scenario."""

    def __init__(
        self,
        end_condition_repo: EndConditionRepo,
        entity_repo: EntityRepo,
        scenario_repo: ScenarioRepo,
    ) -> None:
        self.end_condition_repo = end_condition_repo
        self.entity_repo = entity_repo
        self.scenario_repo = scenario_repo

    async def create_end_condition(
        self, scenario_id: uuid.UUID, user_id: uuid.UUID, data: EndConditionCreate
    ) -> EndConditionResponse:
        """Create a new end condition owned by the given scenario."""
        await self._ensure_scenario_owner_and_validate(scenario_id, user_id, data)

        end_condition = EndCondition(
            scenario_id=scenario_id,
            condition_expression=data.condition_expression,
            outcome_tag=data.outcome_tag,
            outcome_title=data.outcome_title,
            outcome_text=data.outcome_text,
            is_secret=data.is_secret,
            priority=data.priority,
        )
        created = await self.end_condition_repo.create(end_condition)
        return EndConditionResponse.model_validate(created)

    async def list_end_conditions(
        self, scenario_id: uuid.UUID, user_id: uuid.UUID
    ) -> list[EndConditionResponse]:
        """List all end conditions for a scenario, priority-ordered."""
        await self._ensure_scenario_owner(scenario_id, user_id)
        items = await self.end_condition_repo.list_by_scenario(scenario_id)
        return [EndConditionResponse.model_validate(i) for i in items]

    async def get_end_condition(
        self, scenario_id: uuid.UUID, end_condition_id: uuid.UUID, user_id: uuid.UUID
    ) -> EndConditionResponse:
        """Fetch a single end condition, scoped to its owning scenario."""
        await self._ensure_scenario_owner(scenario_id, user_id)
        end_condition = await self._get_scoped(scenario_id, end_condition_id)
        return EndConditionResponse.model_validate(end_condition)

    async def update_end_condition(
        self,
        scenario_id: uuid.UUID,
        end_condition_id: uuid.UUID,
        user_id: uuid.UUID,
        data: EndConditionUpdate,
    ) -> EndConditionResponse:
        """Update an end condition's mutable fields."""
        await self._ensure_scenario_owner_and_validate(scenario_id, user_id, data)
        end_condition = await self._get_scoped(scenario_id, end_condition_id)

        update_dict = data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(end_condition, field, value)

        updated = await self.end_condition_repo.update(end_condition)
        return EndConditionResponse.model_validate(updated)

    async def delete_end_condition(
        self, scenario_id: uuid.UUID, end_condition_id: uuid.UUID, user_id: uuid.UUID
    ) -> None:
        """Delete an end condition."""
        await self._ensure_scenario_owner(scenario_id, user_id)
        end_condition = await self._get_scoped(scenario_id, end_condition_id)
        await self.end_condition_repo.delete(end_condition)

    async def reorder_end_conditions(
        self,
        scenario_id: uuid.UUID,
        user_id: uuid.UUID,
        ordered_end_condition_ids: list[uuid.UUID],
    ) -> list[EndConditionResponse]:
        """Reassign priority (0..N-1) to match the given creator-chosen order."""
        await self._ensure_scenario_owner(scenario_id, user_id)
        for priority, end_condition_id in enumerate(ordered_end_condition_ids):
            end_condition = await self._get_scoped(scenario_id, end_condition_id)
            end_condition.priority = priority
            await self.end_condition_repo.update(end_condition)
        return await self.list_end_conditions(scenario_id, user_id)

    async def _get_scoped(
        self, scenario_id: uuid.UUID, end_condition_id: uuid.UUID
    ) -> EndCondition:
        """Fetch an end condition, raising 404 if missing or owned by another scenario."""
        end_condition = await self.end_condition_repo.get_by_id(end_condition_id)
        if end_condition is None or end_condition.scenario_id != scenario_id:
            raise EndConditionNotFoundError()
        return end_condition

    async def _ensure_scenario_owner_and_validate(
        self,
        scenario_id: uuid.UUID,
        user_id: uuid.UUID,
        data: EndConditionCreate | EndConditionUpdate,
    ) -> None:
        """Verify ownership, then validate condition_expression field references."""
        scenario = await self._ensure_scenario_owner(scenario_id, user_id)
        if data.condition_expression is None:
            return
        entities = await self.entity_repo.list_by_scenario(scenario_id)
        entities_by_id = {e.entity_id: e for e in entities}
        validate_expression_field_references(
            data.condition_expression,
            scenario.state_schema,
            entities_by_id,
            EndConditionValidationError,
        )

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
