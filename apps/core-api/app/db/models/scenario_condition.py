"""ScenarioCondition ORM model."""

import uuid

from sqlalchemy import ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin


class ScenarioCondition(Base, CreatedAtMixin):
    """Persistent active condition defined by creator for master mode."""

    __tablename__ = "scenario_conditions"

    condition_id: Mapped[uuid.UUID] = mapped_column(
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
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    condition_expression: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        server_default=text("'{}'::jsonb"),
        default=dict,
        nullable=False,
    )
    condition_version: Mapped[str] = mapped_column(
        String(50),
        server_default="1.0",
        default="1.0",
        nullable=False,
    )
    narrator_instruction: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_: Mapped[dict[str, object]] = mapped_column(
        "metadata",
        JSONB,
        server_default=text("'{}'::jsonb"),
        default=dict,
        nullable=False,
    )
