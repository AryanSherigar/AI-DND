"""Participant data repository for direct database operations."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.participant import Participant


class ParticipantRepo:
    """Repository managing direct SQLAlchemy queries for Participant entity."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, participant_id: uuid.UUID) -> Participant | None:
        """Retrieve a participant by its primary key ID."""
        stmt = select(Participant).where(Participant.participant_id == participant_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_by_playthrough(self, playthrough_id: uuid.UUID) -> list[Participant]:
        """Fetch all participants of a given playthrough."""
        stmt = select(Participant).where(Participant.playthrough_id == playthrough_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
