"""ScenarioCondition data repository for direct database operations."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.scenario_condition import ScenarioCondition


class ConditionRepo:
    """Repository managing direct SQLAlchemy queries for ScenarioCondition."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, condition: ScenarioCondition) -> ScenarioCondition:
        """Persist a new ScenarioCondition."""
        self.session.add(condition)
        await self.session.flush()
        return condition

    async def get_by_id(self, condition_id: uuid.UUID) -> ScenarioCondition | None:
        """Retrieve a condition by its primary key ID."""
        stmt = select(ScenarioCondition).where(
            ScenarioCondition.condition_id == condition_id
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_by_scenario(self, scenario_id: uuid.UUID) -> list[ScenarioCondition]:
        """Retrieve all active conditions belonging to a scenario."""
        stmt = select(ScenarioCondition).where(
            ScenarioCondition.scenario_id == scenario_id
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update(self, condition: ScenarioCondition) -> ScenarioCondition:
        """Flush changes to an existing condition."""
        await self.session.flush()
        await self.session.refresh(condition)
        return condition

    async def delete(self, condition: ScenarioCondition) -> None:
        """Permanently delete a condition."""
        await self.session.delete(condition)
        await self.session.flush()
