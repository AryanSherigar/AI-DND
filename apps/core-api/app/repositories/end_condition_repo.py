"""EndCondition data repository for direct database operations."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.end_condition import EndCondition


class EndConditionRepo:
    """Repository managing direct SQLAlchemy queries for EndCondition."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, end_condition: EndCondition) -> EndCondition:
        """Persist a new EndCondition."""
        self.session.add(end_condition)
        await self.session.flush()
        return end_condition

    async def get_by_id(self, end_condition_id: uuid.UUID) -> EndCondition | None:
        """Retrieve an end condition by its primary key ID."""
        stmt = select(EndCondition).where(
            EndCondition.end_condition_id == end_condition_id
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_by_scenario(self, scenario_id: uuid.UUID) -> list[EndCondition]:
        """Retrieve all end conditions for a scenario, ordered by priority ascending."""
        stmt = (
            select(EndCondition)
            .where(EndCondition.scenario_id == scenario_id)
            .order_by(EndCondition.priority.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update(self, end_condition: EndCondition) -> EndCondition:
        """Flush changes to an existing end condition."""
        await self.session.flush()
        await self.session.refresh(end_condition)
        return end_condition

    async def delete(self, end_condition: EndCondition) -> None:
        """Permanently delete an end condition."""
        await self.session.delete(end_condition)
        await self.session.flush()
