"""MusicGenerationJob ORM model.

Job state is persisted, not held in a process-local dict, because core-api
instances are stateless request/response — the frontend polls a status
endpoint that may be served by a different instance than the one that
started the job.
"""

import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin

JOB_STATUSES = ("pending", "running", "succeeded", "failed")


class MusicGenerationJob(Base, TimestampMixin):
    """A single Lyria generation attempt, from submission to preview."""

    __tablename__ = "music_generation_jobs"

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','running','succeeded','failed')",
            name="ck_music_generation_jobs_status",
        ),
    )

    job_id: Mapped[uuid.UUID] = mapped_column(
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
    mood: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="pending", default="pending"
    )
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    preview_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    key: Mapped[str | None] = mapped_column(String(20), nullable=True)
    bpm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
