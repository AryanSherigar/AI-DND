"""ScenarioMusic ORM model."""

import uuid

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin

MOOD_SLOTS = ("peaceful", "mystery", "tension", "combat", "melancholy", "triumph")
MUSIC_SOURCES = ("upload", "generated", "default")


class ScenarioMusic(Base, TimestampMixin):
    """A creator-assigned track for one mood slot of a scenario."""

    __tablename__ = "scenario_music"

    __table_args__ = (
        CheckConstraint(
            "mood IN ('peaceful','mystery','tension','combat','melancholy','triumph')",
            name="ck_scenario_music_mood",
        ),
        CheckConstraint(
            "source IN ('upload','generated','default')",
            name="ck_scenario_music_source",
        ),
        UniqueConstraint(
            "scenario_id", "mood", name="uq_scenario_music_scenario_id_mood"
        ),
    )

    scenario_music_id: Mapped[uuid.UUID] = mapped_column(
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
    mood: Mapped[str] = mapped_column(String(20), nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    track_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    generation_prompt: Mapped[str | None] = mapped_column(String(500), nullable=True)
    key: Mapped[str | None] = mapped_column(String(20), nullable=True)
    bpm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
