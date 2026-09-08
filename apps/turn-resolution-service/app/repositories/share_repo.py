"""PlaythroughShare data repository. Read-only — TRS never writes shares."""

from app.db.models.share import PlaythroughShare
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class ShareRepo:
    """Repository managing read-only SQLAlchemy queries for PlaythroughShare."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_token(self, share_token: str) -> PlaythroughShare | None:
        """Retrieve a share by its unguessable token."""
        stmt = select(PlaythroughShare).where(
            PlaythroughShare.share_token == share_token
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()
