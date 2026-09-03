"""TurnLog data repository for direct database operations."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.turn_log import TurnLog


class TurnLogRepo:
    """Repository managing direct SQLAlchemy queries for TurnLog entity."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_by_playthrough(
        self,
        playthrough_id: uuid.UUID,
        limit: int = 20,
        offset: int = 0,
        from_turn: int | None = None,
    ) -> tuple[list[TurnLog], int]:
        """Fetch a page of turn history, oldest first, optionally from a turn number."""
        stmt = select(TurnLog).where(TurnLog.playthrough_id == playthrough_id)
        if from_turn is not None:
            stmt = stmt.where(TurnLog.turn_number >= from_turn)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar_one() or 0

        stmt = stmt.order_by(TurnLog.turn_number.asc()).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total
