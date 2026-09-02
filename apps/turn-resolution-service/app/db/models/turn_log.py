"""TurnLog ORM model (mirrors core-api's schema)."""

import uuid

from sqlalchemy import ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin


class TurnLog(Base, CreatedAtMixin):
    """Append-only turn execution record entity."""

    __tablename__ = "turn_logs"

    __table_args__ = (
        Index("idx_turn_logs_playthrough_turn", "playthrough_id", "turn_number"),
    )

    turn_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        default=uuid.uuid4,
    )
    playthrough_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("playthroughs.playthrough_id", ondelete="RESTRICT"),
        nullable=False,
    )
    turn_number: Mapped[int] = mapped_column(nullable=False)
    participant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("participants.participant_id", ondelete="RESTRICT"),
        nullable=True,
    )
    action_text: Mapped[str] = mapped_column(Text, nullable=False)
    narration_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    tool_calls: Mapped[list[object]] = mapped_column(
        JSONB,
        server_default=text("'[]'::jsonb"),
        default=list,
        nullable=False,
    )
