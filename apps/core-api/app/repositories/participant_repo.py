"""Participant data repository for direct database operations."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.participant import Participant


class ParticipantRepo:
    """Repository managing direct SQLAlchemy queries for Participant entity."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, participant: Participant) -> Participant:
        """Persist a new Participant entity."""
        self.session.add(participant)
        await self.session.flush()
        return participant

    async def get_by_id(self, participant_id: uuid.UUID) -> Participant | None:
        """Retrieve a participant by its primary key ID."""
        stmt = select(Participant).where(Participant.participant_id == participant_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def update(self, participant: Participant) -> Participant:
        """Flush changes to an existing participant entity."""
        await self.session.flush()
        await self.session.refresh(participant)
        return participant

    async def delete(self, participant: Participant) -> None:
        """Permanently delete a participant entity from DB."""
        await self.session.delete(participant)
        await self.session.flush()

    async def list_by_playthrough(self, playthrough_id: uuid.UUID) -> list[Participant]:
        """Fetch all participants of a given playthrough."""
        stmt = select(Participant).where(Participant.playthrough_id == playthrough_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_playthrough_and_user(
        self, playthrough_id: uuid.UUID, user_id: uuid.UUID
    ) -> Participant | None:
        """Retrieve a participant row for a specific user in a playthrough."""
        stmt = select(Participant).where(
            Participant.playthrough_id == playthrough_id,
            Participant.user_id == user_id,
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()
