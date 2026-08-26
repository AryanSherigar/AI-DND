"""Comprehensive unit tests for SQLAlchemy Base, metadata, ORM models, indexes, FKs, and DDL compilation."""

import uuid
from decimal import Decimal

from app.db.base import (
    NAMING_CONVENTION,
    Base,
)
from app.db.models import (
    Participant,
    Playthrough,
    PlaythroughShare,
    Scenario,
    ScenarioCondition,
    TurnLog,
    User,
)
from sqlalchemy import schema
from sqlalchemy.dialects import postgresql


def test_base_metadata_contains_all_tables() -> None:
    """Verify that Base.metadata registers all 7 domain ORM model tables."""
    expected_tables = {
        "users",
        "scenarios",
        "scenario_conditions",
        "playthroughs",
        "participants",
        "playthrough_shares",
        "turn_logs",
    }
    registered_tables = set(Base.metadata.tables.keys())
    assert expected_tables.issubset(registered_tables)


def test_naming_convention_configuration() -> None:
    """Verify that Base.metadata uses the explicit PostgreSQL naming convention."""
    assert Base.metadata.naming_convention == NAMING_CONVENTION
    assert Base.metadata.naming_convention["pk"] == "pk_%(table_name)s"
    assert Base.metadata.naming_convention["fk"] == (
        "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"
    )


def test_orm_models_exported_classes() -> None:
    """Verify ORM model class exports and tablenames."""
    assert User.__tablename__ == "users"
    assert Scenario.__tablename__ == "scenarios"
    assert ScenarioCondition.__tablename__ == "scenario_conditions"
    assert Playthrough.__tablename__ == "playthroughs"
    assert Participant.__tablename__ == "participants"
    assert PlaythroughShare.__tablename__ == "playthrough_shares"
    assert TurnLog.__tablename__ == "turn_logs"


def test_primary_key_column_names() -> None:
    """Verify that each table defines its specific primary key column name."""
    pk_mapping = {
        "users": "user_id",
        "scenarios": "scenario_id",
        "scenario_conditions": "condition_id",
        "playthroughs": "playthrough_id",
        "participants": "participant_id",
        "playthrough_shares": "share_id",
        "turn_logs": "turn_id",
    }
    for table_name, expected_pk in pk_mapping.items():
        table = Base.metadata.tables[table_name]
        pk_cols = [col.name for col in table.primary_key.columns]
        assert pk_cols == [expected_pk]


def test_foreign_key_relationships() -> None:
    """Verify foreign key columns, target tables, and ondelete rules."""
    fk_checks = [
        ("scenarios", "creator_id", "users.user_id", "RESTRICT"),
        ("scenario_conditions", "scenario_id", "scenarios.scenario_id", "CASCADE"),
        ("playthroughs", "scenario_id", "scenarios.scenario_id", "RESTRICT"),
        ("playthroughs", "created_by", "users.user_id", "RESTRICT"),
        ("participants", "playthrough_id", "playthroughs.playthrough_id", "RESTRICT"),
        ("participants", "user_id", "users.user_id", "RESTRICT"),
        (
            "playthrough_shares",
            "playthrough_id",
            "playthroughs.playthrough_id",
            "RESTRICT",
        ),
        ("turn_logs", "playthrough_id", "playthroughs.playthrough_id", "RESTRICT"),
        ("turn_logs", "participant_id", "participants.participant_id", "RESTRICT"),
    ]

    for table_name, col_name, target, expected_ondelete in fk_checks:
        table = Base.metadata.tables[table_name]
        column = table.columns[col_name]
        assert len(column.foreign_keys) == 1
        fk = next(iter(column.foreign_keys))
        assert fk._get_colspec() == target
        assert fk.ondelete == expected_ondelete


def test_indexes_and_unique_constraints() -> None:
    """Verify unique indexes and composite indexes across tables."""
    scenarios_table = Base.metadata.tables["scenarios"]
    scenarios_index_names = {idx.name for idx in scenarios_table.indexes}
    assert "idx_scenarios_genre_tags" in scenarios_index_names

    turn_logs_table = Base.metadata.tables["turn_logs"]
    turn_logs_index_names = {idx.name for idx in turn_logs_table.indexes}
    assert "idx_turn_logs_playthrough_turn" in turn_logs_index_names

    users_table = Base.metadata.tables["users"]
    auth_col = users_table.columns["auth_provider_id"]
    assert auth_col.unique or any(
        "auth_provider_id" in [c.name for c in idx.columns]
        for idx in users_table.indexes
    )


def test_model_instantiation_and_column_defaults() -> None:
    """Verify in-memory model instantiation and column default configurations."""
    user = User(display_name="Test Creator", auth_provider_id="google-123")
    assert user.display_name == "Test Creator"
    assert user.auth_provider_id == "google-123"

    creator_id = uuid.uuid4()
    scenario = Scenario(
        creator_id=creator_id,
        title="Test Scenario",
        mode="master",
        complexity_tier="intermediate",
        player_count_support="solo",
        status="draft",
        play_count=0,
        rating_avg=Decimal("0.00"),
    )
    assert scenario.creator_id == creator_id
    assert scenario.title == "Test Scenario"
    assert scenario.status == "draft"
    assert scenario.play_count == 0

    scenarios_table = Base.metadata.tables["scenarios"]
    assert scenarios_table.columns["status"].default.arg == "draft"
    assert scenarios_table.columns["play_count"].default.arg == 0
    assert scenarios_table.columns["rating_avg"].default.arg == Decimal("0.00")

    condition = ScenarioCondition(
        scenario_id=uuid.uuid4(),
        label="Ghost Shadow",
        narrator_instruction="A ghost shadows the player.",
    )
    assert condition.label == "Ghost Shadow"
    assert condition.narrator_instruction == "A ghost shadows the player."

    conditions_table = Base.metadata.tables["scenario_conditions"]
    assert conditions_table.columns["condition_version"].default.arg == "1.0"

    turn_log = TurnLog(
        playthrough_id=uuid.uuid4(),
        turn_number=1,
        action_text="Open the ancient door",
    )
    assert turn_log.turn_number == 1
    assert turn_log.action_text == "Open the ancient door"


def test_schema_ddl_compilation() -> None:
    """Verify that PostgreSQL DDL compiles cleanly for all tables in Base.metadata."""
    pg_dialect = postgresql.dialect()
    for table in Base.metadata.tables.values():
        ddl_str = str(schema.CreateTable(table).compile(dialect=pg_dialect))
        assert "CREATE TABLE" in ddl_str
        assert table.name in ddl_str
