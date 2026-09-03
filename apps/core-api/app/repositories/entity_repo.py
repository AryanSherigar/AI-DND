"""Entity data repository for direct database operations."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.entity import Entity


class EntityRepo:
    """Repository managing direct SQLAlchemy queries for Entity."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, entity: Entity) -> Entity:
        """Persist a new Entity."""
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def get_by_id(self, entity_id: uuid.UUID) -> Entity | None:
        """Retrieve an entity by its primary key ID."""
        stmt = select(Entity).where(Entity.entity_id == entity_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_by_scenario(self, scenario_id: uuid.UUID) -> list[Entity]:
        """Retrieve all entities belonging to a scenario."""
        stmt = select(Entity).where(Entity.scenario_id == scenario_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update(self, entity: Entity) -> Entity:
        """Flush changes to an existing entity."""
        await self.session.flush()
        await self.session.refresh(entity)
        return entity

    async def delete(self, entity: Entity) -> None:
        """Permanently delete an entity. Cascades to referencing facts (DB-level)."""
        await self.session.delete(entity)
        await self.session.flush()
