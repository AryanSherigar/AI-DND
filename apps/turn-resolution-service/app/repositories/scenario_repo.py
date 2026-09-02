"""Scenario data repository, deliberately minimal.

TRS may only ever increment `play_count` on Scenario (CLAUDE.md) — no other
read or write method is defined here, so that constraint is enforced at the
repository boundary itself rather than by convention alone.
"""

import uuid

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.scenario import Scenario


class ScenarioRepo:
    """Repository exposing only the one Scenario mutation TRS is allowed to perform."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def increment_play_count(self, scenario_id: uuid.UUID) -> None:
        """Increment play_count by 1."""
        await self.session.execute(
            update(Scenario)
            .where(Scenario.scenario_id == scenario_id)
            .values(play_count=Scenario.play_count + 1)
        )
