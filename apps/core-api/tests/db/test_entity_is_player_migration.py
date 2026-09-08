"""Unit tests for migration 012 (entity is_player column and unique index)."""

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_migration_module() -> ModuleType:
    migration_path = (
        Path(__file__).parent.parent.parent
        / "app"
        / "db"
        / "migrations"
        / "versions"
        / "012_entity_is_player.py"
    )
    spec = importlib.util.spec_from_file_location("migration_012", migration_path)
    assert spec is not None, "Failed to load migration spec"
    assert spec.loader is not None, "Failed to load migration loader"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_012_metadata() -> None:
    module = _load_migration_module()
    assert module.revision == "012_entity_is_player"
    assert module.down_revision == "011_turn_logs_image_url"


def test_migration_012_callables() -> None:
    module = _load_migration_module()
    assert callable(module.upgrade)
    assert callable(module.downgrade)
