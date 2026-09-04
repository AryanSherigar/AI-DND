"""Scenario entity type template data repository for direct database operations."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.scenario_entity_type import ScenarioEntityType


class ScenarioEntityTypeRepo:
    """Repository managing direct SQLAlchemy queries for ScenarioEntityType."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, entity_type: ScenarioEntityType) -> ScenarioEntityType:
        """Persist a new custom entity type template."""
        self.session.add(entity_type)
        await self.session.flush()
        return entity_type

    async def get_by_id(
        self, scenario_entity_type_id: uuid.UUID
    ) -> ScenarioEntityType | None:
        """Retrieve a custom entity type template by its primary key ID."""
        stmt = select(ScenarioEntityType).where(
            ScenarioEntityType.scenario_entity_type_id == scenario_entity_type_id
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_type_key(
        self, scenario_id: uuid.UUID, type_key: str
    ) -> ScenarioEntityType | None:
        """Retrieve a custom entity type template by its scenario-scoped key."""
        stmt = select(ScenarioEntityType).where(
            ScenarioEntityType.scenario_id == scenario_id,
            ScenarioEntityType.type_key == type_key,
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_by_scenario(
        self, scenario_id: uuid.UUID
    ) -> list[ScenarioEntityType]:
        """Retrieve all custom entity type templates belonging to a scenario."""
        stmt = select(ScenarioEntityType).where(
            ScenarioEntityType.scenario_id == scenario_id
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update(self, entity_type: ScenarioEntityType) -> ScenarioEntityType:
        """Flush changes to an existing custom entity type template."""
        await self.session.flush()
        await self.session.refresh(entity_type)
        return entity_type

    async def delete(self, entity_type: ScenarioEntityType) -> None:
        """Permanently delete a custom entity type template."""
        await self.session.delete(entity_type)
        await self.session.flush()
