"""RuleInvariant domain service: business logic and expression field-reference
validation for mechanically-enforced master-mode world rules."""

import uuid

from app.db.models.entity import Entity
from app.db.models.rule_invariant import RuleInvariant
from app.db.models.scenario import Scenario
from app.exceptions.invariant_exceptions import (
    InvariantNotFoundError,
    InvariantValidationError,
)
from app.exceptions.scenario_exceptions import (
    ScenarioAccessDeniedError,
    ScenarioNotFoundError,
)
from app.models.invariant import InvariantCreate, InvariantResponse, InvariantUpdate
from app.repositories.entity_repo import EntityRepo
from app.repositories.invariant_repo import InvariantRepo
from app.repositories.scenario_repo import ScenarioRepo
from app.services.expression_validation import validate_expression_field_references

_RESERVED_APPLIES_TO = ("global", "player")


class InvariantService:
    """Service handling rule-invariant authoring for a master-mode scenario."""

    def __init__(
        self,
        invariant_repo: InvariantRepo,
        entity_repo: EntityRepo,
        scenario_repo: ScenarioRepo,
    ) -> None:
        self.invariant_repo = invariant_repo
        self.entity_repo = entity_repo
        self.scenario_repo = scenario_repo

    async def create_invariant(
        self, scenario_id: uuid.UUID, user_id: uuid.UUID, data: InvariantCreate
    ) -> InvariantResponse:
        """Create a new rule invariant owned by the given scenario."""
        entities_by_id = await self._validate(scenario_id, user_id, data)
        self._ensure_valid_applies_to(data.applies_to, entities_by_id)

        invariant = RuleInvariant(
            scenario_id=scenario_id,
            label=data.label,
            invariant_expression=data.invariant_expression,
            applies_to=data.applies_to,
            narrator_text=data.narrator_text,
        )
        created = await self.invariant_repo.create(invariant)
        return InvariantResponse.model_validate(created)

    async def list_invariants(
        self, scenario_id: uuid.UUID, user_id: uuid.UUID
    ) -> list[InvariantResponse]:
        """List all rule invariants for a scenario."""
        await self._ensure_scenario_owner(scenario_id, user_id)
        items = await self.invariant_repo.list_by_scenario(scenario_id)
        return [InvariantResponse.model_validate(i) for i in items]

    async def get_invariant(
        self, scenario_id: uuid.UUID, invariant_id: uuid.UUID, user_id: uuid.UUID
    ) -> InvariantResponse:
        """Fetch a single rule invariant, scoped to its owning scenario."""
        await self._ensure_scenario_owner(scenario_id, user_id)
        invariant = await self._get_scoped(scenario_id, invariant_id)
        return InvariantResponse.model_validate(invariant)

    async def update_invariant(
        self,
        scenario_id: uuid.UUID,
        invariant_id: uuid.UUID,
        user_id: uuid.UUID,
        data: InvariantUpdate,
    ) -> InvariantResponse:
        """Update a rule invariant's mutable fields."""
        entities_by_id = await self._validate(scenario_id, user_id, data)
        if data.applies_to is not None:
            self._ensure_valid_applies_to(data.applies_to, entities_by_id)
        invariant = await self._get_scoped(scenario_id, invariant_id)

        update_dict = data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(invariant, field, value)

        updated = await self.invariant_repo.update(invariant)
        return InvariantResponse.model_validate(updated)

    async def delete_invariant(
        self, scenario_id: uuid.UUID, invariant_id: uuid.UUID, user_id: uuid.UUID
    ) -> None:
        """Delete a rule invariant."""
        await self._ensure_scenario_owner(scenario_id, user_id)
        invariant = await self._get_scoped(scenario_id, invariant_id)
        await self.invariant_repo.delete(invariant)

    def _ensure_valid_applies_to(
        self, applies_to: str, entities_by_id: dict[uuid.UUID, Entity]
    ) -> None:
        """applies_to must be 'global', 'player', or a known entity ID."""
        if applies_to in _RESERVED_APPLIES_TO:
            return
        try:
            is_known_entity = uuid.UUID(applies_to) in entities_by_id
        except ValueError:
            is_known_entity = False
        if not is_known_entity:
            raise InvariantValidationError(
                f"applies_to must be 'global', 'player', or a known entity ID, "
                f"got {applies_to!r}"
            )

    async def _validate(
        self,
        scenario_id: uuid.UUID,
        user_id: uuid.UUID,
        data: InvariantCreate | InvariantUpdate,
    ) -> dict[uuid.UUID, Entity]:
        """Verify ownership, then validate invariant_expression field references."""
        scenario = await self._ensure_scenario_owner(scenario_id, user_id)
        entities = await self.entity_repo.list_by_scenario(scenario_id)
        entities_by_id = {e.entity_id: e for e in entities}
        if data.invariant_expression is not None:
            validate_expression_field_references(
                data.invariant_expression,
                scenario.state_schema,
                entities_by_id,
                InvariantValidationError,
            )
        return entities_by_id

    async def _get_scoped(
        self, scenario_id: uuid.UUID, invariant_id: uuid.UUID
    ) -> RuleInvariant:
        """Fetch an invariant, raising 404 if missing or owned by another scenario."""
        invariant = await self.invariant_repo.get_by_id(invariant_id)
        if invariant is None or invariant.scenario_id != scenario_id:
            raise InvariantNotFoundError()
        return invariant

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
