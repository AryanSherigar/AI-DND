import importlib.util
from pathlib import Path
from typing import Any


def _load_migration_module() -> Any:
    migration_path = (
        Path(__file__).parent.parent.parent
        / "app"
        / "db"
        / "migrations"
        / "versions"
        / "001_initial_schema.py"
    )
    spec = importlib.util.spec_from_file_location("migration_001", migration_path)
    assert spec is not None, "Failed to load migration spec"
    assert spec.loader is not None, "Failed to load migration loader"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_metadata() -> None:
    module = _load_migration_module()
    assert module.revision == "001_initial_schema"
    assert module.down_revision is None


def test_migration_callables() -> None:
    module = _load_migration_module()
    assert callable(module.upgrade)
    assert callable(module.downgrade)
    assert callable(module._create_users_table)
    assert callable(module._create_scenarios_table)
    assert callable(module._create_scenario_conditions_table)
    assert callable(module._create_playthroughs_table)
    assert callable(module._create_participants_table)
    assert callable(module._create_playthrough_shares_table)
    assert callable(module._create_turn_logs_table)


def test_scenarios_columns_structure() -> None:
    module = _load_migration_module()
    columns = module._get_scenarios_columns()
    column_names = [col.name for col in columns]
    expected_names = [
        "scenario_id",
        "creator_id",
        "title",
        "mode",
        "world_data",
        "status",
        "genre_tags",
        "complexity_tier",
        "player_count_support",
        "estimated_playtime",
        "cover_image_url",
        "content_tag",
        "publish_error",
        "published_at",
        "play_count",
        "rating_avg",
        "narrator_persona",
        "setup_schema",
        "state_schema",
        "end_conditions",
        "checkpoints",
        "rules",
        "current_version",
        "created_at",
        "updated_at",
    ]
    for expected in expected_names:
        assert expected in column_names, f"Missing column {expected}"


def test_scenarios_status_check_constraint_includes_publish_states() -> None:
    module = _load_migration_module()
    columns = module._get_scenarios_columns()
    status_col = next(col for col in columns if col.name == "status")
    check_constraint = next(iter(status_col.constraints))
    constraint_text = str(check_constraint.sqltext)
    for expected_state in (
        "draft",
        "publishing",
        "published",
        "publish_failed",
        "archived",
    ):
        assert expected_state in constraint_text
