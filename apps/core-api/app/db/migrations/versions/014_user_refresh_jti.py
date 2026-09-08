"""user refresh token single-use rotation

Revision ID: 014_user_refresh_jti
Revises: 013_scenario_music
Create Date: 2026-09-08

Adds users.current_refresh_jti: the jti of the most recently issued refresh
token for that user. POST /v1/auth/refresh rejects any refresh token whose
jti doesn't match, so a stolen-but-already-rotated refresh token can't be
replayed (HIGH-05 audit finding).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "014_user_refresh_jti"
down_revision: str | None = "013_scenario_music"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("current_refresh_jti", sa.String(length=36), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "current_refresh_jti")
