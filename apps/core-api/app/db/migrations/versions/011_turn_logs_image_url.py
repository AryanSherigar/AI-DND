"""turn logs image url

Revision ID: 011_turn_logs_image_url
Revises: 010_participants_unique
Create Date: 2026-09-08

Adds nullable image_url, location_id, and scene_image_prompt columns to
turn_logs, supporting AI-generated scene images for "see" action turns.
location_id and scene_image_prompt exist purely to support looking up the
prior scene image generated for the same location in the same playthrough,
for cross-turn visual consistency.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "011_turn_logs_image_url"
down_revision: str | None = "010_participants_unique"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("turn_logs", sa.Column("image_url", sa.String(1024), nullable=True))
    op.add_column("turn_logs", sa.Column("location_id", sa.String(255), nullable=True))
    op.add_column(
        "turn_logs", sa.Column("scene_image_prompt", sa.Text(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("turn_logs", "scene_image_prompt")
    op.drop_column("turn_logs", "location_id")
    op.drop_column("turn_logs", "image_url")
