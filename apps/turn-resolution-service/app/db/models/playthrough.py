"""Playthrough ORM model (mirrors core-api's schema)."""

import uuid

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class Playthrough(Base, TimestampMixin):
    """Playthrough session entity."""

    __tablename__ = "playthroughs"

    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'completed', 'abandoned')",
            name="ck_playthroughs_status",
        ),
        CheckConstraint(
            "ended_outcome_tag IN ('win', 'lose')",
            name="ck_playthroughs_ended_outcome_tag",
        ),
    )

    playthrough_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        default=uuid.uuid4,
    )
    scenario_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scenarios.scenario_id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="RESTRICT"),
        nullable=False,
    )
    state: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        server_default=text("'{}'::jsonb"),
        default=dict,
        nullable=False,
    )
    checkpoint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    turn_count: Mapped[int] = mapped_column(
        server_default="0", default=0, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20),
        server_default="active",
        default="active",
        nullable=False,
    )
    scenario_version: Mapped[int] = mapped_column(nullable=False)
    scenario_snapshot: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        server_default=text("'{}'::jsonb"),
        default=dict,
        nullable=False,
    )
    ended_outcome_tag: Mapped[str | None] = mapped_column(String(10), nullable=True)
    ended_outcome_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ended_outcome_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_playtest: Mapped[bool] = mapped_column(
        Boolean, server_default="false", default=False, nullable=False
    )
