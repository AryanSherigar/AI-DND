"""Scenario ORM model."""

import uuid
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Index, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class Scenario(Base, TimestampMixin):
    """Scenario authoring and discovery entity."""

    __tablename__ = "scenarios"

    __table_args__ = (
        CheckConstraint("mode IN ('newbie', 'master')", name="ck_scenarios_mode"),
        CheckConstraint("status IN ('draft', 'published')", name="ck_scenarios_status"),
        CheckConstraint(
            "complexity_tier IN ('newbie', 'intermediate', 'master')",
            name="ck_scenarios_complexity_tier",
        ),
        CheckConstraint(
            "player_count_support IN ('solo', 'multiplayer', 'both')",
            name="ck_scenarios_player_count_support",
        ),
        Index("idx_scenarios_genre_tags", "genre_tags", postgresql_using="gin"),
    )

    scenario_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        default=uuid.uuid4,
    )
    creator_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="RESTRICT"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    world_data: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        server_default=text("'{}'::jsonb"),
        default=dict,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        server_default="draft",
        default="draft",
        nullable=False,
    )
    genre_tags: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        server_default=text("'{}'::text[]"),
        default=list,
        nullable=False,
    )
    complexity_tier: Mapped[str] = mapped_column(String(20), nullable=False)
    player_count_support: Mapped[str] = mapped_column(String(20), nullable=False)
    estimated_playtime: Mapped[str | None] = mapped_column(String(50), nullable=True)
    cover_image_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    content_tag: Mapped[str | None] = mapped_column(String(100), nullable=True)
    play_count: Mapped[int] = mapped_column(
        server_default="0", default=0, nullable=False
    )
    rating_avg: Mapped[Decimal] = mapped_column(
        Numeric(3, 2), server_default="0.00", default=Decimal("0.00"), nullable=False
    )
    narrator_persona: Mapped[str | None] = mapped_column(Text, nullable=True)
    setup_schema: Mapped[list[object]] = mapped_column(
        JSONB,
        server_default=text("'[]'::jsonb"),
        default=list,
        nullable=False,
    )
    state_schema: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        server_default=text("'{}'::jsonb"),
        default=dict,
        nullable=False,
    )
    end_conditions: Mapped[list[object]] = mapped_column(
        JSONB,
        server_default=text("'[]'::jsonb"),
        default=list,
        nullable=False,
    )
    checkpoints: Mapped[list[object]] = mapped_column(
        JSONB,
        server_default=text("'[]'::jsonb"),
        default=list,
        nullable=False,
    )
    rules: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        server_default=text("'{}'::jsonb"),
        default=dict,
        nullable=False,
    )
    current_version: Mapped[int] = mapped_column(
        server_default="1", default=1, nullable=False
    )
