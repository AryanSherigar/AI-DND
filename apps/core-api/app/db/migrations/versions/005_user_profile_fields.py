"""user profile fields

Revision ID: 005_user_profile_fields
Revises: 004_playthrough_end_outcome
Create Date: 2026-09-04

See docs/specs/user-profile-page.spec.md.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "005_user_profile_fields"
down_revision: str | None = "004_playthrough_end_outcome"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("bio", sa.String(length=500), nullable=True))
    op.add_column(
        "users", sa.Column("avatar_url", sa.String(length=1024), nullable=True)
    )
    op.add_column(
        "users", sa.Column("banner_url", sa.String(length=1024), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("users", "banner_url")
    op.drop_column("users", "avatar_url")
    op.drop_column("users", "bio")
