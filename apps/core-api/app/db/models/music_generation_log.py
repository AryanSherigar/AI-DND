"""MusicGenerationLog ORM model.

Append-only: one row per Lyria call attempt, written before the call is
made. Quota checks are COUNT(*) queries over this table rather than mutable
counter columns, so concurrent requests can't race an increment/decrement.
"""

import uuid

from sqlalchemy import ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin


class MusicGenerationLog(Base, CreatedAtMixin):
    """One logged Lyria generation attempt, for quota accounting."""

    __tablename__ = "music_generation_log"

    log_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        default=uuid.uuid4,
    )
    scenario_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scenarios.scenario_id", ondelete="CASCADE"),
        nullable=False,
    )
    creator_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="RESTRICT"),
        nullable=False,
    )
