"""turn logs unique constraint

Revision ID: 009_turn_logs_unique_constraint
Revises: 008_master_mode_minigames
Create Date: 2026-09-07

Replaces non-unique idx_turn_logs_playthrough_turn index on turn_logs with
a UniqueConstraint uq_turn_logs_playthrough_turn on (playthrough_id, turn_number),
preventing duplicate narrative turn rows from concurrent turn submissions.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "009_turn_logs_unique_constraint"
down_revision: str | None = "008_master_mode_minigames"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("idx_turn_logs_playthrough_turn", table_name="turn_logs")
    op.create_unique_constraint(
        "uq_turn_logs_playthrough_turn",
        "turn_logs",
        ["playthrough_id", "turn_number"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_turn_logs_playthrough_turn",
        "turn_logs",
        type_="unique",
    )
    op.create_index(
        "idx_turn_logs_playthrough_turn",
        "turn_logs",
        ["playthrough_id", "turn_number"],
    )
