"""PlaythroughShare ORM model."""

import uuid

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin


class PlaythroughShare(Base, CreatedAtMixin):
    """Share token entity for spectate or join access."""

    __tablename__ = "playthrough_shares"

    __table_args__ = (
        CheckConstraint(
            "mode IN ('spectate', 'join')",
            name="ck_playthrough_shares_mode",
        ),
        UniqueConstraint("share_token", name="uq_playthrough_shares_token"),
        Index("ix_playthrough_shares_token", "share_token"),
    )

    share_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        default=uuid.uuid4,
    )
    share_token: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    playthrough_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("playthroughs.playthrough_id", ondelete="RESTRICT"),
        nullable=False,
    )
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
