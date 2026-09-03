"""RuleInvariant data repository for direct database operations."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.rule_invariant import RuleInvariant


class InvariantRepo:
    """Repository managing direct SQLAlchemy queries for RuleInvariant."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, invariant: RuleInvariant) -> RuleInvariant:
        """Persist a new RuleInvariant."""
        self.session.add(invariant)
        await self.session.flush()
        return invariant

    async def get_by_id(self, invariant_id: uuid.UUID) -> RuleInvariant | None:
        """Retrieve an invariant by its primary key ID."""
        stmt = select(RuleInvariant).where(RuleInvariant.invariant_id == invariant_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_by_scenario(self, scenario_id: uuid.UUID) -> list[RuleInvariant]:
        """Retrieve all rule invariants belonging to a scenario."""
        stmt = select(RuleInvariant).where(RuleInvariant.scenario_id == scenario_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update(self, invariant: RuleInvariant) -> RuleInvariant:
        """Flush changes to an existing invariant."""
        await self.session.flush()
        await self.session.refresh(invariant)
        return invariant

    async def delete(self, invariant: RuleInvariant) -> None:
        """Permanently delete a rule invariant."""
        await self.session.delete(invariant)
        await self.session.flush()
