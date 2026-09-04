"""master mode maps

Revision ID: 007_master_mode_maps
Revises: 006_scenario_entity_types
Create Date: 2026-09-05

Adds Maps to master-mode scenarios: scenario_maps (image + display metadata),
map_pins (location entities placed on a map, with exactly one scenario-wide
start pin), and map_connections (a scenario-wide, possibly cross-map graph of
location-to-location edges). See docs/specs/master-mode-maps.spec.md.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "007_master_mode_maps"
down_revision: str | None = "006_scenario_entity_types"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    _create_scenario_maps_table()
    _create_map_pins_table()
    _create_map_connections_table()


def downgrade() -> None:
    op.drop_index("idx_map_connections_scenario_id", table_name="map_connections")
    op.drop_table("map_connections")
    op.drop_index("idx_map_pins_one_start_per_scenario", table_name="map_pins")
    op.drop_index("idx_map_pins_map_id", table_name="map_pins")
    op.drop_table("map_pins")
    op.drop_index("idx_scenario_maps_scenario_id", table_name="scenario_maps")
    op.drop_table("scenario_maps")


def _create_scenario_maps_table() -> None:
    op.create_table(
        "scenario_maps",
        sa.Column(
            "map_id",
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
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("image_url", sa.String(length=1024), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
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
    op.create_index("idx_scenario_maps_scenario_id", "scenario_maps", ["scenario_id"])


def _create_map_pins_table() -> None:
    op.create_table(
        "map_pins",
        sa.Column(
            "pin_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "map_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scenario_maps.map_id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Denormalized, same precedent as facts.scenario_id alongside
        # subject_entity_id — needed so "exactly one start pin" can be a
        # single scenario-scoped partial unique index below, not a
        # cross-table query.
        sa.Column(
            "scenario_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scenarios.scenario_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "entity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("entities.entity_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("x", sa.Float(), nullable=False),
        sa.Column("y", sa.Float(), nullable=False),
        sa.Column(
            "is_start_location", sa.Boolean(), server_default="false", nullable=False
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.create_index("idx_map_pins_map_id", "map_pins", ["map_id"])
    op.create_index(
        "idx_map_pins_one_start_per_scenario",
        "map_pins",
        ["scenario_id"],
        unique=True,
        postgresql_where=sa.text("is_start_location"),
    )


def _create_map_connections_table() -> None:
    op.create_table(
        "map_connections",
        sa.Column(
            "connection_id",
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
        sa.Column(
            "entity_id_a",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("entities.entity_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "entity_id_b",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("entities.entity_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("label", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        # Service always inserts the sorted-UUID pair; this single constraint
        # rejects both self-loops (a == b fails "<") and reversed duplicates
        # (combined with the unique constraint below).
        sa.CheckConstraint(
            "entity_id_a < entity_id_b", name="ck_map_connections_sorted_pair"
        ),
        sa.UniqueConstraint(
            "scenario_id", "entity_id_a", "entity_id_b", name="uq_map_connections_pair"
        ),
    )
    op.create_index(
        "idx_map_connections_scenario_id", "map_connections", ["scenario_id"]
    )
