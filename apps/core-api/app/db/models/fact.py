"""Fact ORM model."""

import uuid

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin


class Fact(Base, CreatedAtMixin):
    """A creator-authored master-mode fact connecting a subject entity to an
    object (another entity or a typed literal) via a predicate."""

    __tablename__ = "facts"

    __table_args__ = (
        CheckConstraint(
            "(object_entity_id IS NOT NULL) != (object_literal IS NOT NULL)",
            name="ck_facts_object_exclusive",
        ),
    )

    fact_id: Mapped[uuid.UUID] = mapped_column(
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
    subject_entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.entity_id", ondelete="CASCADE"),
        nullable=False,
    )
    predicate: Mapped[str] = mapped_column(String(100), nullable=False)
    object_entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.entity_id", ondelete="CASCADE"),
        nullable=True,
    )
    object_literal: Mapped[str | None] = mapped_column(Text, nullable=True)
    valid_from: Mapped[str | None] = mapped_column(String(100), nullable=True)
    when_active: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    hidden: Mapped[bool] = mapped_column(
        Boolean, server_default="false", default=False, nullable=False
    )
    superseded_fact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("facts.fact_id", ondelete="SET NULL"),
        nullable=True,
    )
    metadata_: Mapped[dict[str, object]] = mapped_column(
        "metadata",
        JSONB,
        server_default=text("'{}'::jsonb"),
        default=dict,
        nullable=False,
    )
