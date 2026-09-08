"""Unit tests for migration 011 (turn_logs image_url, location_id, scene_image_prompt)."""

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
        / "011_turn_logs_image_url.py"
    )
    spec = importlib.util.spec_from_file_location("migration_011", migration_path)
    assert spec is not None, "Failed to load migration spec"
    assert spec.loader is not None, "Failed to load migration loader"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_011_metadata() -> None:
    module = _load_migration_module()
    assert module.revision == "011_turn_logs_image_url"
    assert module.down_revision == "010_participants_unique"


def test_migration_011_callables() -> None:
    module = _load_migration_module()
    assert callable(module.upgrade)
    assert callable(module.downgrade)
