"""MapConnection ORM model."""

import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin


class MapConnection(Base, CreatedAtMixin):
    """A scenario-wide edge between two location entities, independent of
    which map(s) happen to display either endpoint (edges may cross maps).

    entity_id_a/entity_id_b are always stored in sorted-UUID order by the
    service layer — never construct this ORM object directly with an
    unsorted pair.
    """

    __tablename__ = "map_connections"

    __table_args__ = (
        CheckConstraint(
            "entity_id_a < entity_id_b", name="ck_map_connections_sorted_pair"
        ),
        UniqueConstraint(
            "scenario_id", "entity_id_a", "entity_id_b", name="uq_map_connections_pair"
        ),
    )

    connection_id: Mapped[uuid.UUID] = mapped_column(
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
    entity_id_a: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.entity_id", ondelete="CASCADE"),
        nullable=False,
    )
    entity_id_b: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.entity_id", ondelete="CASCADE"),
        nullable=False,
    )
    label: Mapped[str | None] = mapped_column(Text, nullable=True)
