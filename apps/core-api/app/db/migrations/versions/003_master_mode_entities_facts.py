"""master mode entities, facts, end_conditions, rule_invariants

Revision ID: 003_master_mode_entities_facts
Revises: 002_bookmarks_and_reviews
Create Date: 2026-09-03

See docs/specs/master-mode-data-model.spec.md.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003_master_mode_entities_facts"
down_revision: str | None = "002_bookmarks_and_reviews"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_entities_table() -> None:
    op.create_table(
        "entities",
        sa.Column(
            "entity_id",
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
            "entity_type",
            sa.String(length=30),
            sa.CheckConstraint(
                "entity_type IN ('character', 'location', 'item', "
                "'faction', 'organization')",
                name="ck_entities_entity_type",
            ),
            nullable=False,
        ),
        sa.Column("canonical_name", sa.String(length=255), nullable=False),
        sa.Column(
            "aliases",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("obtainable", sa.Boolean(), nullable=True),
        sa.Column(
            "attributes_schema",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("narrator_instruction", sa.Text(), nullable=True),
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
    op.create_index("idx_entities_scenario_id", "entities", ["scenario_id"])


def _create_facts_table() -> None:
    op.create_table(
        "facts",
        sa.Column(
            "fact_id",
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
            "subject_entity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("entities.entity_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("predicate", sa.String(length=100), nullable=False),
        sa.Column(
            "object_entity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("entities.entity_id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("object_literal", sa.Text(), nullable=True),
        sa.Column("valid_from", sa.String(length=100), nullable=True),
        sa.Column(
            "when_active", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("hidden", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "superseded_fact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("facts.fact_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "metadata",
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
        sa.CheckConstraint(
            "(object_entity_id IS NOT NULL) != (object_literal IS NOT NULL)",
            name="ck_facts_object_exclusive",
        ),
    )
    op.create_index("idx_facts_scenario_id", "facts", ["scenario_id"])
    op.create_index("idx_facts_subject_entity_id", "facts", ["subject_entity_id"])


def _create_end_conditions_table() -> None:
    op.create_table(
        "end_conditions",
        sa.Column(
            "end_condition_id",
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
            "condition_expression",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "outcome_tag",
            sa.String(length=10),
            sa.CheckConstraint(
                "outcome_tag IN ('win', 'lose')",
                name="ck_end_conditions_outcome_tag",
            ),
            nullable=False,
        ),
        sa.Column("outcome_title", sa.String(length=255), nullable=False),
        sa.Column("outcome_text", sa.Text(), nullable=False),
        sa.Column("is_secret", sa.Boolean(), server_default="false", nullable=False),
        # Explicit creator-controlled precedence for "first match wins"
        # evaluation (master-mode-end-conditions.spec.md) — NOT createdAt
        # order, since the Studio's reorder UI (master-mode-studio-ui.spec.md)
        # must let a creator change precedence without deleting and
        # recreating rows. Lower value evaluates first.
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.create_index(
        "idx_end_conditions_scenario_priority",
        "end_conditions",
        ["scenario_id", "priority"],
    )


def _create_rule_invariants_table() -> None:
    op.create_table(
        "rule_invariants",
        sa.Column(
            "invariant_id",
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
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column(
            "invariant_expression",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("applies_to", sa.String(length=255), nullable=False),
        sa.Column("narrator_text", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.create_index(
        "idx_rule_invariants_scenario_id", "rule_invariants", ["scenario_id"]
    )


def _add_effect_c_column_to_scenario_conditions() -> None:
    op.add_column(
        "scenario_conditions",
        sa.Column(
            "state_mutation", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
    )


def _add_studio_authoring_columns_to_scenarios() -> None:
    """Small, independent creator-power fields locked in during the Q&A pass
    that don't warrant their own migration — added here alongside the other
    master-mode schema work. All nullable/defaulted: safe no-op for existing
    (including newbie-mode) scenarios."""
    op.add_column("scenarios", sa.Column("opening_scene", sa.Text(), nullable=True))
    op.add_column(
        "scenarios", sa.Column("narration_font", sa.String(length=50), nullable=True)
    )
    op.add_column(
        "scenarios",
        sa.Column(
            "action_chips",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
    )
    op.add_column(
        "scenarios",
        sa.Column(
            "setup_archetypes",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )


def upgrade() -> None:
    _create_entities_table()
    _create_facts_table()
    _create_end_conditions_table()
    _create_rule_invariants_table()
    _add_effect_c_column_to_scenario_conditions()
    _add_studio_authoring_columns_to_scenarios()


def downgrade() -> None:
    op.drop_column("scenarios", "setup_archetypes")
    op.drop_column("scenarios", "action_chips")
    op.drop_column("scenarios", "narration_font")
    op.drop_column("scenarios", "opening_scene")
    op.drop_column("scenario_conditions", "state_mutation")
    op.drop_index("idx_rule_invariants_scenario_id", table_name="rule_invariants")
    op.drop_table("rule_invariants")
    op.drop_index("idx_end_conditions_scenario_priority", table_name="end_conditions")
    op.drop_table("end_conditions")
    op.drop_index("idx_facts_subject_entity_id", table_name="facts")
    op.drop_index("idx_facts_scenario_id", table_name="facts")
    op.drop_table("facts")
    op.drop_index("idx_entities_scenario_id", table_name="entities")
    op.drop_table("entities")
