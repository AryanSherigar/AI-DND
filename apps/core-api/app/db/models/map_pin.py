"""MapPin ORM model."""

import uuid

from sqlalchemy import Boolean, Float, ForeignKey, Index, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin


class MapPin(Base, CreatedAtMixin):
    """A location entity placed at a coordinate on a scenario map."""

    __tablename__ = "map_pins"

    __table_args__ = (
        Index("idx_map_pins_map_id", "map_id"),
        Index(
            "idx_map_pins_one_start_per_scenario",
            "scenario_id",
            unique=True,
            postgresql_where=text("is_start_location"),
        ),
    )

    pin_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        default=uuid.uuid4,
    )
    map_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scenario_maps.map_id", ondelete="CASCADE"),
        nullable=False,
    )
    scenario_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scenarios.scenario_id", ondelete="CASCADE"),
        nullable=False,
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.entity_id", ondelete="CASCADE"),
        nullable=False,
    )
    x: Mapped[float] = mapped_column(Float, nullable=False)
    y: Mapped[float] = mapped_column(Float, nullable=False)
    is_start_location: Mapped[bool] = mapped_column(
        Boolean, server_default="false", default=False, nullable=False
    )
