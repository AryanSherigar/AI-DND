"""Unit tests for migration 009 (turn_logs unique constraint)."""

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
        / "009_turn_logs_unique_constraint.py"
    )
    spec = importlib.util.spec_from_file_location("migration_009", migration_path)
    assert spec is not None, "Failed to load migration spec"
    assert spec.loader is not None, "Failed to load migration loader"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_009_metadata() -> None:
    module = _load_migration_module()
    assert module.revision == "009_turn_logs_unique_constraint"
    assert module.down_revision == "008_master_mode_minigames"


def test_migration_009_callables() -> None:
    module = _load_migration_module()
    assert callable(module.upgrade)
    assert callable(module.downgrade)
