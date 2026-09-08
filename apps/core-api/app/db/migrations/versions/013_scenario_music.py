"""scenario music: mood-slot tracks, generation jobs, generation quota log

Revision ID: 013_scenario_music
Revises: 012_entity_is_player
Create Date: 2026-09-08

Adds three tables backing per-scenario custom music:
- scenario_music: one row per mood slot (upload / generated / default track)
- music_generation_jobs: persisted Lyria job state (core-api is stateless,
  so job progress can't live in a process-local dict)
- music_generation_log: append-only generation-attempt log used for quota
  accounting (COUNT(*) queries, no mutable counters to race)
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "013_scenario_music"
down_revision: str | None = "012_entity_is_player"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_MOOD_CHECK = "mood IN ('peaceful','mystery','tension','combat','melancholy','triumph')"


def upgrade() -> None:
    op.create_table(
        "scenario_music",
        sa.Column(
            "scenario_music_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("scenario_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mood", sa.String(length=20), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("track_url", sa.String(length=2048), nullable=True),
        sa.Column("generation_prompt", sa.String(length=500), nullable=True),
        sa.Column("key", sa.String(length=20), nullable=True),
        sa.Column("bpm", sa.Integer(), nullable=True),
        sa.Column("duration_seconds", sa.Numeric(6, 2), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["scenario_id"],
            ["scenarios.scenario_id"],
            ondelete="CASCADE",
            name="fk_scenario_music_scenario_id_scenarios",
        ),
        sa.PrimaryKeyConstraint("scenario_music_id", name="pk_scenario_music"),
        sa.CheckConstraint(_MOOD_CHECK, name="ck_scenario_music_mood"),
        sa.CheckConstraint(
            "source IN ('upload','generated','default')",
            name="ck_scenario_music_source",
        ),
        sa.UniqueConstraint(
            "scenario_id", "mood", name="uq_scenario_music_scenario_id_mood"
        ),
    )

    op.create_table(
        "music_generation_jobs",
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("scenario_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("creator_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mood", sa.String(length=20), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("preview_url", sa.String(length=2048), nullable=True),
        sa.Column("key", sa.String(length=20), nullable=True),
        sa.Column("bpm", sa.Integer(), nullable=True),
        sa.Column("duration_seconds", sa.Numeric(6, 2), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["scenario_id"],
            ["scenarios.scenario_id"],
            ondelete="CASCADE",
            name="fk_music_generation_jobs_scenario_id_scenarios",
        ),
        sa.ForeignKeyConstraint(
            ["creator_id"],
            ["users.user_id"],
            ondelete="RESTRICT",
            name="fk_music_generation_jobs_creator_id_users",
        ),
        sa.PrimaryKeyConstraint("job_id", name="pk_music_generation_jobs"),
        sa.CheckConstraint(
            "status IN ('pending','running','succeeded','failed')",
            name="ck_music_generation_jobs_status",
        ),
    )
    op.create_index(
        "ix_music_generation_jobs_scenario_id",
        "music_generation_jobs",
        ["scenario_id"],
    )

    op.create_table(
        "music_generation_log",
        sa.Column(
            "log_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("scenario_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("creator_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["scenario_id"],
            ["scenarios.scenario_id"],
            ondelete="CASCADE",
            name="fk_music_generation_log_scenario_id_scenarios",
        ),
        sa.ForeignKeyConstraint(
            ["creator_id"],
            ["users.user_id"],
            ondelete="RESTRICT",
            name="fk_music_generation_log_creator_id_users",
        ),
        sa.PrimaryKeyConstraint("log_id", name="pk_music_generation_log"),
    )
    op.create_index(
        "ix_music_generation_log_scenario_id",
        "music_generation_log",
        ["scenario_id"],
    )
    op.create_index(
        "ix_music_generation_log_creator_id_created_at",
        "music_generation_log",
        ["creator_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_music_generation_log_creator_id_created_at",
        table_name="music_generation_log",
    )
    op.drop_index(
        "ix_music_generation_log_scenario_id", table_name="music_generation_log"
    )
    op.drop_table("music_generation_log")

    op.drop_index(
        "ix_music_generation_jobs_scenario_id", table_name="music_generation_jobs"
    )
    op.drop_table("music_generation_jobs")

    op.drop_table("scenario_music")
