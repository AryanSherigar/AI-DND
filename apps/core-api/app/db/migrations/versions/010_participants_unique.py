"""participants unique constraints

Revision ID: 010_participants_unique
Revises: 009_turn_logs_unique_constraint
Create Date: 2026-09-07

Adds unique constraints to participants table:
- uq_participants_playthrough_user on (playthrough_id, user_id)
- uq_participants_turn_order on (playthrough_id, turn_order_position)
"""

from collections.abc import Sequence

from alembic import op

revision: str = "010_participants_unique"
down_revision: str | None = "009_turn_logs_unique_constraint"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_participants_playthrough_user",
        "participants",
        ["playthrough_id", "user_id"],
    )
    op.create_unique_constraint(
        "uq_participants_turn_order",
        "participants",
        ["playthrough_id", "turn_order_position"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_participants_turn_order",
        "participants",
        type_="unique",
    )
    op.drop_constraint(
        "uq_participants_playthrough_user",
        "participants",
        type_="unique",
    )
