"""Playthrough data repository for direct database operations."""

import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.playthrough import Playthrough


class PlaythroughRepo:
    """Repository managing direct SQLAlchemy queries for Playthrough entity."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, playthrough_id: uuid.UUID) -> Playthrough | None:
        """Retrieve a playthrough by its primary key ID."""
        stmt = select(Playthrough).where(Playthrough.playthrough_id == playthrough_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def update_state(
        self,
        playthrough_id: uuid.UUID,
        state: dict[str, object],
        turn_count: int,
    ) -> None:
        """Update a playthrough's narrative state and turn count."""
        await self.session.execute(
            update(Playthrough)
            .where(Playthrough.playthrough_id == playthrough_id)
            .values(state=state, turn_count=turn_count)
        )
