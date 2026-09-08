"""ScenarioMinigame ORM model."""

import uuid

from sqlalchemy import ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class ScenarioMinigame(Base, TimestampMixin):
    """A creator-authored interstitial minigame trigger within a
    master-mode scenario (docs/specs/master-mode-minigames.spec.md).

    outcome_mode/mutation shape pairing (binary requires win+lose,
    tiered requires >=1 tiered_outcomes entry) is enforced in Pydantic,
    not as a DB CHECK constraint — same posture as scenario_conditions'
    state_mutation column.
    """

    __tablename__ = "scenario_minigames"

    __table_args__ = (Index("idx_scenario_minigames_scenario_id", "scenario_id"),)

    minigame_id: Mapped[uuid.UUID] = mapped_column(
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
    minigame_type: Mapped[str] = mapped_column(String(20), nullable=False)
    trigger_condition_expression: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        server_default=text("'{}'::jsonb"),
        default=dict,
        nullable=False,
    )
    priority: Mapped[int] = mapped_column(
        Integer, server_default="0", default=0, nullable=False
    )
    outcome_mode: Mapped[str] = mapped_column(String(10), nullable=False)
    # NOTE: none_as_null=True on every nullable JSONB column below — without
    # it, SQLAlchemy's JSON type binds a Python None to the JSON literal
    # `null` rather than SQL NULL, which silently breaks the
    # ck_scenario_minigames_type_config_pairing CHECK constraint (it tests
    # "dodge_config IS NULL", which is false for a stored JSON null).
    win_mutation: Mapped[dict[str, object] | None] = mapped_column(
        JSONB(none_as_null=True), nullable=True
    )
    lose_mutation: Mapped[dict[str, object] | None] = mapped_column(
        JSONB(none_as_null=True), nullable=True
    )
    tiered_outcomes: Mapped[list[object]] = mapped_column(
        JSONB,
        server_default=text("'[]'::jsonb"),
        default=list,
        nullable=False,
    )
    timeout_mutation: Mapped[dict[str, object] | None] = mapped_column(
        JSONB(none_as_null=True), nullable=True
    )
    narrator_instruction_template: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    dodge_config: Mapped[dict[str, object] | None] = mapped_column(
        JSONB(none_as_null=True), nullable=True
    )
    replit_embed_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
