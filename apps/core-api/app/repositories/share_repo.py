"""PlaythroughShare data repository for direct database operations."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.share import PlaythroughShare


class ShareRepo:
    """Repository managing direct SQLAlchemy queries for PlaythroughShare entity."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self, playthrough_id: uuid.UUID, mode: str, share_token: str
    ) -> PlaythroughShare:
        """Persist a new PlaythroughShare entity."""
        share = PlaythroughShare(
            playthrough_id=playthrough_id, mode=mode, share_token=share_token
        )
        self.session.add(share)
        await self.session.flush()
        return share

    async def get_by_token(self, share_token: str) -> PlaythroughShare | None:
        """Retrieve a share by its unguessable token."""
        stmt = select(PlaythroughShare).where(
            PlaythroughShare.share_token == share_token
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_playthrough_and_mode(
        self, playthrough_id: uuid.UUID, mode: str
    ) -> PlaythroughShare | None:
        """Retrieve the existing share for a (playthrough, mode) pair, if any."""
        stmt = select(PlaythroughShare).where(
            PlaythroughShare.playthrough_id == playthrough_id,
            PlaythroughShare.mode == mode,
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()
