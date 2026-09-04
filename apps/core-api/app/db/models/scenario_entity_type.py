"""ScenarioEntityType ORM model."""

import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class ScenarioEntityType(Base, TimestampMixin):
    """A creator-defined, reusable entity type template scoped to one scenario."""

    __tablename__ = "scenario_entity_types"

    __table_args__ = (
        UniqueConstraint(
            "scenario_id", "type_key", name="uq_scenario_entity_types_type_key"
        ),
    )

    scenario_entity_type_id: Mapped[uuid.UUID] = mapped_column(
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
    type_key: Mapped[str] = mapped_column(String(30), nullable=False)
    display_label: Mapped[str] = mapped_column(String(60), nullable=False)
    attributes_schema: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        server_default=text("'{}'::jsonb"),
        default=dict,
        nullable=False,
    )
