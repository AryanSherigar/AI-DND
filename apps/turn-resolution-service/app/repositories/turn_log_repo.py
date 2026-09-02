"""TurnLog data repository for direct database operations."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.turn_log import TurnLog


class TurnLogRepo:
    """Repository managing direct SQLAlchemy queries for TurnLog entity."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        playthrough_id: uuid.UUID,
        turn_number: int,
        participant_id: uuid.UUID | None,
        action_text: str,
        narration_text: str | None,
    ) -> TurnLog:
        """Persist a new append-only TurnLog entity."""
        turn_log = TurnLog(
            playthrough_id=playthrough_id,
            turn_number=turn_number,
            participant_id=participant_id,
            action_text=action_text,
            narration_text=narration_text,
        )
        self.session.add(turn_log)
        await self.session.flush()
        return turn_log
