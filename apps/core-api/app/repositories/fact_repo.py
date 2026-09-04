"""Fact data repository for direct database operations."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.fact import Fact


class FactRepo:
    """Repository managing direct SQLAlchemy queries for Fact."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, fact: Fact) -> Fact:
        """Persist a new Fact."""
        self.session.add(fact)
        await self.session.flush()
        return fact

    async def get_by_id(self, fact_id: uuid.UUID) -> Fact | None:
        """Retrieve a fact by its primary key ID."""
        stmt = select(Fact).where(Fact.fact_id == fact_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_by_scenario(
        self, scenario_id: uuid.UUID, entity_id: uuid.UUID | None = None
    ) -> list[Fact]:
        """Retrieve facts belonging to a scenario, optionally scoped to one entity."""
        stmt = select(Fact).where(Fact.scenario_id == scenario_id)
        if entity_id is not None:
            stmt = stmt.where(
                (Fact.subject_entity_id == entity_id)
                | (Fact.object_entity_id == entity_id)
            )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_by_entity_for_scenario(
        self, scenario_id: uuid.UUID
    ) -> dict[uuid.UUID, int]:
        """Count facts referencing each entity (as subject or object) in a scenario."""
        subject_stmt = (
            select(Fact.subject_entity_id, func.count())
            .where(Fact.scenario_id == scenario_id)
            .group_by(Fact.subject_entity_id)
        )
        object_stmt = (
            select(Fact.object_entity_id, func.count())
            .where(
                Fact.scenario_id == scenario_id,
                Fact.object_entity_id.is_not(None),
            )
            .group_by(Fact.object_entity_id)
        )
        counts: dict[uuid.UUID, int] = {}
        for entity_id, count in (await self.session.execute(subject_stmt)).all():
            counts[entity_id] = counts.get(entity_id, 0) + count
        for entity_id, count in (await self.session.execute(object_stmt)).all():
            counts[entity_id] = counts.get(entity_id, 0) + count
        return counts

    async def count_referencing_entity(self, entity_id: uuid.UUID) -> int:
        """Count facts referencing an entity as subject or object (pre-delete check)."""
        stmt = select(Fact).where(
            (Fact.subject_entity_id == entity_id) | (Fact.object_entity_id == entity_id)
        )
        result = await self.session.execute(stmt)
        return len(result.scalars().all())

    async def update(self, fact: Fact) -> Fact:
        """Flush changes to an existing fact."""
        await self.session.flush()
        await self.session.refresh(fact)
        return fact

    async def delete(self, fact: Fact) -> None:
        """Permanently delete a fact."""
        await self.session.delete(fact)
        await self.session.flush()
