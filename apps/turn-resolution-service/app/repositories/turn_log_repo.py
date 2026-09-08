"""TurnLog data repository for direct database operations."""

import uuid

from app.db.models.turn_log import TurnLog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


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
        tool_calls: list[dict[str, object]] | None = None,
        image_url: str | None = None,
        location_id: str | None = None,
        scene_image_prompt: str | None = None,
    ) -> TurnLog:
        """Persist a new append-only TurnLog entity."""
        turn_log = TurnLog(
            playthrough_id=playthrough_id,
            turn_number=turn_number,
            participant_id=participant_id,
            action_text=action_text,
            narration_text=narration_text,
            tool_calls=tool_calls or [],
            image_url=image_url,
            location_id=location_id,
            scene_image_prompt=scene_image_prompt,
        )
        self.session.add(turn_log)
        await self.session.flush()
        return turn_log

    async def find_latest_by_location(
        self, playthrough_id: uuid.UUID, location_id: str
    ) -> TurnLog | None:
        """Find the most recent turn log with a scene image for this location,
        used to keep repeated 'see' actions at the same place visually
        consistent (see docs/plans image-generation grounding notes)."""
        query = (
            select(TurnLog)
            .where(
                TurnLog.playthrough_id == playthrough_id,
                TurnLog.location_id == location_id,
                TurnLog.image_url.is_not(None),
            )
            .order_by(TurnLog.turn_number.desc())
            .limit(1)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
