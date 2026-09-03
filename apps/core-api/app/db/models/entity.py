"""Entity ORM model."""

import uuid

from sqlalchemy import Boolean, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin

ENTITY_TYPES = ("character", "location", "item", "faction", "organization")


class Entity(Base, TimestampMixin):
    """A creator-authored master-mode world entity (character, location, item, ...)."""

    __tablename__ = "entities"

    entity_id: Mapped[uuid.UUID] = mapped_column(
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
    entity_type: Mapped[str] = mapped_column(String(30), nullable=False)
    canonical_name: Mapped[str] = mapped_column(String(255), nullable=False)
    aliases: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        server_default=text("'{}'::text[]"),
        default=list,
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    obtainable: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    attributes_schema: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        server_default=text("'{}'::jsonb"),
        default=dict,
        nullable=False,
    )
    narrator_instruction: Mapped[str | None] = mapped_column(Text, nullable=True)
