"""playthrough end outcome + playtest flag

Revision ID: 004_playthrough_end_outcome
Revises: 003_master_mode_entities_facts
Create Date: 2026-09-03

See docs/specs/master-mode-end-conditions.spec.md.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "004_playthrough_end_outcome"
down_revision: str | None = "003_master_mode_entities_facts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("playthroughs", sa.Column("ended_outcome_tag", sa.String(length=10)))
    op.add_column(
        "playthroughs", sa.Column("ended_outcome_title", sa.String(length=255))
    )
    op.add_column("playthroughs", sa.Column("ended_outcome_text", sa.Text()))
    op.add_column(
        "playthroughs",
        sa.Column("is_playtest", sa.Boolean(), server_default="false", nullable=False),
    )
    op.create_check_constraint(
        "ck_playthroughs_ended_outcome_tag",
        "playthroughs",
        "ended_outcome_tag IN ('win', 'lose')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_playthroughs_ended_outcome_tag", "playthroughs", type_="check"
    )
    op.drop_column("playthroughs", "is_playtest")
    op.drop_column("playthroughs", "ended_outcome_text")
    op.drop_column("playthroughs", "ended_outcome_title")
    op.drop_column("playthroughs", "ended_outcome_tag")
