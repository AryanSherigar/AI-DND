"""entity is_player column and unique partial index

Revision ID: 012_entity_is_player
Revises: 011_turn_logs_image_url
Create Date: 2026-09-08

Adds is_player boolean column to entities and enforces at most one player character
entity per scenario via a partial unique index.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "012_entity_is_player"
down_revision: str | None = "011_turn_logs_image_url"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "entities",
        sa.Column(
            "is_player",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.create_index(
        "uq_entities_scenario_player",
        "entities",
        ["scenario_id"],
        unique=True,
        postgresql_where=sa.text("is_player IS TRUE"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_entities_scenario_player",
        table_name="entities",
        postgresql_where=sa.text("is_player IS TRUE"),
    )
    op.drop_column("entities", "is_player")
