"""master mode minigames

Revision ID: 008_master_mode_minigames
Revises: 007_master_mode_maps
Create Date: 2026-09-05

Adds scenario_minigames to master-mode scenarios: interstitial trigger
records (dodge or replit_embed) that fire against post-turn state, hand
control to a full-screen experience outside the AI narration loop, and
resolve into a deterministic state mutation plus narrator instruction. See
docs/specs/master-mode-minigames.spec.md.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "008_master_mode_minigames"
down_revision: str | None = "007_master_mode_maps"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    _create_scenario_minigames_table()


def downgrade() -> None:
    op.drop_index("idx_scenario_minigames_scenario_id", table_name="scenario_minigames")
    op.drop_table("scenario_minigames")


def _create_scenario_minigames_table() -> None:
    op.create_table(
        "scenario_minigames",
        sa.Column(
            "minigame_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "scenario_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scenarios.scenario_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("minigame_type", sa.String(length=20), nullable=False),
        sa.Column(
            "trigger_condition_expression",
            postgresql.JSONB(),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("priority", sa.Integer(), server_default="0", nullable=False),
        sa.Column("outcome_mode", sa.String(length=10), nullable=False),
        sa.Column("win_mutation", postgresql.JSONB(), nullable=True),
        sa.Column("lose_mutation", postgresql.JSONB(), nullable=True),
        sa.Column(
            "tiered_outcomes", postgresql.JSONB(), server_default="[]", nullable=False
        ),
        sa.Column("timeout_mutation", postgresql.JSONB(), nullable=True),
        sa.Column("narrator_instruction_template", sa.Text(), nullable=True),
        sa.Column("dodge_config", postgresql.JSONB(), nullable=True),
        sa.Column("replit_embed_url", sa.String(length=1024), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "minigame_type IN ('dodge', 'replit_embed')",
            name="ck_scenario_minigames_type",
        ),
        sa.CheckConstraint(
            "outcome_mode IN ('binary', 'tiered')",
            name="ck_scenario_minigames_outcome_mode",
        ),
        sa.CheckConstraint(
            "(minigame_type = 'dodge' AND replit_embed_url IS NULL) OR "
            "(minigame_type = 'replit_embed' AND dodge_config IS NULL)",
            name="ck_scenario_minigames_type_config_pairing",
        ),
    )
    op.create_index(
        "idx_scenario_minigames_scenario_id", "scenario_minigames", ["scenario_id"]
    )
