"""PlaythroughShare ORM model (mirrors core-api's schema, read-only in TRS).

TRS never writes to this table — share link creation is exclusively a Core
API concern. This mirror exists only so TRS can validate a spectate token
without a cross-service HTTP call, per the existing mirror pattern for
Participant/Playthrough/Scenario/TurnLog.
"""

import uuid

from sqlalchemy import CheckConstraint, ForeignKey, String, text
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
    )

    share_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        default=uuid.uuid4,
    )
    share_token: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    playthrough_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("playthroughs.playthrough_id", ondelete="RESTRICT"),
        nullable=False,
    )
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
