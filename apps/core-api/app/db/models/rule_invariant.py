"""RuleInvariant ORM model."""

import uuid

from sqlalchemy import ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin


class RuleInvariant(Base, CreatedAtMixin):
    """A creator-authored hard world rule, mechanically enforced by TRS's
    state_validator on every state mutation (master mode)."""

    __tablename__ = "rule_invariants"

    invariant_id: Mapped[uuid.UUID] = mapped_column(
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
    invariant_expression: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        server_default=text("'{}'::jsonb"),
        default=dict,
        nullable=False,
    )
    applies_to: Mapped[str] = mapped_column(String(255), nullable=False)
    narrator_text: Mapped[str] = mapped_column(Text, nullable=False)
