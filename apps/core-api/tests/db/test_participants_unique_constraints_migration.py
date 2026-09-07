"""Unit tests for migration 010 (participants unique constraints)."""

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
        / "010_participants_unique_constraints.py"
    )
    spec = importlib.util.spec_from_file_location("migration_010", migration_path)
    assert spec is not None, "Failed to load migration spec"
    assert spec.loader is not None, "Failed to load migration loader"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_010_metadata() -> None:
    module = _load_migration_module()
    assert module.revision == "010_participants_unique_constraints"
    assert module.down_revision == "009_turn_logs_unique_constraint"


def test_migration_010_callables() -> None:
    module = _load_migration_module()
    assert callable(module.upgrade)
    assert callable(module.downgrade)
