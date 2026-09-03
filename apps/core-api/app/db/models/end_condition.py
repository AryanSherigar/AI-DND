"""EndCondition ORM model."""

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin


class EndCondition(Base, CreatedAtMixin):
    """A creator-authored win/lose condition with a named outcome (master mode).

    priority determines "first match wins" evaluation order in TRS
    (master-mode-end-conditions.spec.md) — explicit and creator-reorderable,
    not implicit creation order.
    """

    __tablename__ = "end_conditions"

    end_condition_id: Mapped[uuid.UUID] = mapped_column(
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
    condition_expression: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        server_default=text("'{}'::jsonb"),
        default=dict,
        nullable=False,
    )
    outcome_tag: Mapped[str] = mapped_column(String(10), nullable=False)
    outcome_title: Mapped[str] = mapped_column(String(255), nullable=False)
    outcome_text: Mapped[str] = mapped_column(Text, nullable=False)
    is_secret: Mapped[bool] = mapped_column(
        Boolean, server_default="false", default=False, nullable=False
    )
    priority: Mapped[int] = mapped_column(
        Integer, server_default="0", default=0, nullable=False
    )
