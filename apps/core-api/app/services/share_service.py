"""Playthrough sharing domain service: token issuance and validation."""

import secrets
import uuid

from app.config import settings
from app.db.models.share import PlaythroughShare
from app.exceptions.playthrough_exceptions import (
    InvalidShareTokenError,
    PlaythroughAccessDeniedError,
    PlaythroughNotFoundError,
)
from app.models.share import ShareMode
from app.repositories.participant_repo import ParticipantRepo
from app.repositories.playthrough_repo import PlaythroughRepo
from app.repositories.share_repo import ShareRepo

_TOKEN_BYTES = 32


class ShareService:
    """Service orchestrating share token creation and validation."""

    def __init__(
        self,
        share_repo: ShareRepo,
        playthrough_repo: PlaythroughRepo,
        participant_repo: ParticipantRepo,
    ) -> None:
        self.share_repo = share_repo
        self.playthrough_repo = playthrough_repo
        self.participant_repo = participant_repo

    async def create_share(
        self, playthrough_id: uuid.UUID, mode: ShareMode, user_id: uuid.UUID
    ) -> PlaythroughShare:
        """Generate (or fetch an existing) share link. Participant-only."""
        await self._require_participant(playthrough_id, user_id)
        existing = await self.share_repo.get_by_playthrough_and_mode(
            playthrough_id, mode
        )
        if existing:
            return existing
        token = secrets.token_urlsafe(_TOKEN_BYTES)
        return await self.share_repo.create(
            playthrough_id=playthrough_id, mode=mode, share_token=token
        )

    async def validate_token(
        self, share_token: str, required_mode: ShareMode | None = None
    ) -> PlaythroughShare:
        """Look up a token, raising InvalidShareTokenError if invalid for the mode."""
        share = await self.share_repo.get_by_token(share_token)
        if share is None or (required_mode and share.mode != required_mode):
            raise InvalidShareTokenError()
        return share

    async def _require_participant(
        self, playthrough_id: uuid.UUID, user_id: uuid.UUID
    ) -> None:
        playthrough = await self.playthrough_repo.get_by_id(playthrough_id)
        if playthrough is None:
            raise PlaythroughNotFoundError()
        participant = await self.participant_repo.get_by_playthrough_and_user(
            playthrough_id, user_id
        )
        if participant is None:
            raise PlaythroughAccessDeniedError()


def build_share_url(share: PlaythroughShare) -> str:
    """Build the frontend-facing shareable URL for a share token."""
    if share.mode == "spectate":
        return (
            f"{settings.frontend_base_url}/spectate/{share.playthrough_id}"
            f"?token={share.share_token}"
        )
    return f"{settings.frontend_base_url}/join?token={share.share_token}"
