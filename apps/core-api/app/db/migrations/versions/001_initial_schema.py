"""initial schema

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-08-27
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001_initial_schema"
down_revision: str | None = None
branch_labels: list[str] | None = None
depends_on: list[str] | None = None


def _create_users_table() -> None:
    op.create_table(
        "users",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("auth_provider_id", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.UniqueConstraint("auth_provider_id", name="uq_users_auth_provider_id"),
    )
    op.create_index("ix_users_auth_provider_id", "users", ["auth_provider_id"])


def _get_scenarios_columns() -> list[sa.Column]:
    return [
        sa.Column(
            "scenario_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "creator_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.user_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column(
            "mode",
            sa.String(length=20),
            sa.CheckConstraint("mode IN ('newbie', 'master')"),
            nullable=False,
        ),
        sa.Column(
            "world_data",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            sa.CheckConstraint("status IN ('draft', 'published')"),
            server_default="draft",
            nullable=False,
        ),
        sa.Column(
            "genre_tags",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column(
            "complexity_tier",
            sa.String(length=20),
            sa.CheckConstraint(
                "complexity_tier IN ('newbie', 'intermediate', 'master')"
            ),
            nullable=False,
        ),
        sa.Column(
            "player_count_support",
            sa.String(length=20),
            sa.CheckConstraint(
                "player_count_support IN ('solo', 'multiplayer', 'both')"
            ),
            nullable=False,
        ),
        sa.Column("estimated_playtime", sa.String(length=50), nullable=True),
        sa.Column("cover_image_url", sa.String(length=1024), nullable=True),
        sa.Column("content_tag", sa.String(length=100), nullable=True),
        sa.Column("play_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "rating_avg",
            sa.Numeric(precision=3, scale=2),
            server_default="0.00",
            nullable=False,
        ),
        sa.Column("narrator_persona", sa.Text(), nullable=True),
        sa.Column(
            "setup_schema",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "state_schema",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "end_conditions",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "checkpoints",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "rules",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("current_version", sa.Integer(), server_default="1", nullable=False),
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
    ]


def _create_scenarios_table() -> None:
    columns = _get_scenarios_columns()
    op.create_table("scenarios", *columns)
    op.create_index(
        "idx_scenarios_genre_tags",
        "scenarios",
        ["genre_tags"],
        postgresql_using="gin",
    )


def _create_scenario_conditions_table() -> None:
    op.create_table(
        "scenario_conditions",
        sa.Column(
            "condition_id",
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
        sa.Column(
            "condition_expression",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "condition_version",
            sa.String(length=50),
            server_default="1.0",
            nullable=False,
        ),
        sa.Column("narrator_instruction", sa.Text(), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )


def _create_playthroughs_table() -> None:
    op.create_table(
        "playthroughs",
        sa.Column(
            "playthrough_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "scenario_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scenarios.scenario_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.user_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "state",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("checkpoint", sa.String(length=255), nullable=True),
        sa.Column("turn_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            sa.CheckConstraint("status IN ('active', 'completed', 'abandoned')"),
            server_default="active",
            nullable=False,
        ),
        sa.Column("scenario_version", sa.Integer(), nullable=False),
        sa.Column(
            "scenario_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
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
    )


def _create_participants_table() -> None:
    op.create_table(
        "participants",
        sa.Column(
            "participant_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "playthrough_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("playthroughs.playthrough_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.user_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "role",
            sa.String(length=20),
            sa.CheckConstraint("role IN ('owner', 'joined')"),
            nullable=False,
        ),
        sa.Column("turn_order_position", sa.Integer(), nullable=False),
        sa.Column(
            "joined_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )


def _create_playthrough_shares_table() -> None:
    op.create_table(
        "playthrough_shares",
        sa.Column(
            "share_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("share_token", sa.String(length=255), nullable=False),
        sa.Column(
            "playthrough_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("playthroughs.playthrough_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "mode",
            sa.String(length=20),
            sa.CheckConstraint("mode IN ('spectate', 'join')"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.UniqueConstraint("share_token", name="uq_playthrough_shares_token"),
    )
    op.create_index(
        "ix_playthrough_shares_token",
        "playthrough_shares",
        ["share_token"],
    )


def _create_turn_logs_table() -> None:
    op.create_table(
        "turn_logs",
        sa.Column(
            "turn_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "playthrough_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("playthroughs.playthrough_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("turn_number", sa.Integer(), nullable=False),
        sa.Column(
            "participant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("participants.participant_id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("action_text", sa.Text(), nullable=False),
        sa.Column("narration_text", sa.Text(), nullable=True),
        sa.Column(
            "tool_calls",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.create_index(
        "idx_turn_logs_playthrough_turn",
        "turn_logs",
        ["playthrough_id", "turn_number"],
    )


def upgrade() -> None:
    _create_users_table()
    _create_scenarios_table()
    _create_scenario_conditions_table()
    _create_playthroughs_table()
    _create_participants_table()
    _create_playthrough_shares_table()
    _create_turn_logs_table()


def downgrade() -> None:
    op.drop_index("idx_turn_logs_playthrough_turn", table_name="turn_logs")
    op.drop_table("turn_logs")
    op.drop_index("ix_playthrough_shares_token", table_name="playthrough_shares")
    op.drop_table("playthrough_shares")
    op.drop_table("participants")
    op.drop_table("playthroughs")
    op.drop_table("scenario_conditions")
    op.drop_index("idx_scenarios_genre_tags", table_name="scenarios")
    op.drop_table("scenarios")
    op.drop_index("ix_users_auth_provider_id", table_name="users")
    op.drop_table("users")
