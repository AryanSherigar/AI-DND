"""scenario entity types (custom entity type templates)

Revision ID: 006_scenario_entity_types
Revises: 005_user_profile_fields
Create Date: 2026-09-04

Adds a per-scenario reusable template for custom entity types (creators can
name a type beyond the five built-ins and define its attributes schema once).
Also drops the check constraint that previously restricted `entities.entity_type`
to the five built-in values, since custom type keys must now be accepted.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "006_scenario_entity_types"
down_revision: str | None = "005_user_profile_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_entities_entity_type", "entities", type_="check")

    op.create_table(
        "scenario_entity_types",
        sa.Column(
            "scenario_entity_type_id",
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
        sa.Column("type_key", sa.String(length=30), nullable=False),
        sa.Column("display_label", sa.String(length=60), nullable=False),
        sa.Column(
            "attributes_schema",
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
        sa.UniqueConstraint(
            "scenario_id", "type_key", name="uq_scenario_entity_types_type_key"
        ),
    )
    op.create_index(
        "idx_scenario_entity_types_scenario_id",
        "scenario_entity_types",
        ["scenario_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_scenario_entity_types_scenario_id",
        table_name="scenario_entity_types",
    )
    op.drop_table("scenario_entity_types")
    op.create_check_constraint(
        "ck_entities_entity_type",
        "entities",
        "entity_type IN ('character', 'location', 'item', 'faction', 'organization')",
    )
