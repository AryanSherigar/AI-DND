from __future__ import annotations

import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import patch

from context_memory.composition import run_migrations
from context_memory.core.config import Config
from context_memory.persistence.migrations import (
    MigrationError,
    apply_migrations,
    discover_migrations,
)

ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = ROOT / "db" / "migrations"


class FakeCursor:
    def __init__(self, checksums: dict[str, str]) -> None:
        self.checksums = checksums
        self._selected: tuple[str] | None = None
        self.executed: list[str] = []

    def execute(self, query: str, params: tuple[object, ...] | None = None) -> None:
        self.executed.append(query)
        if query.startswith("SELECT checksum"):
            assert params is not None
            checksum = self.checksums.get(str(params[0]))
            self._selected = (checksum,) if checksum else None
        elif query.startswith("INSERT INTO schema_migrations"):
            assert params is not None
            self.checksums[str(params[0])] = str(params[1])

    def fetchone(self) -> tuple[str] | None:
        return self._selected

    def __enter__(self) -> FakeCursor:
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        return None


class FakeConnection:
    def __init__(self) -> None:
        self.checksums: dict[str, str] = {}
        self.cursor_instance = FakeCursor(self.checksums)

    def cursor(self) -> FakeCursor:
        return self.cursor_instance

    def transaction(self):
        return nullcontext()


class MigrationTests(unittest.TestCase):
    def test_migrations_are_discovered(self) -> None:
        migrations = discover_migrations(MIGRATIONS)
        self.assertEqual(
            [migration.version for migration in migrations],
            [
                "0001",
                "0002",
                "0003",
                "0004",
                "0005",
                "0006",
                "0007",
                "0008",
                "0009",
                "0010",
                "0011",
                "0012",
                "0013",
                "0014",
            ],
        )
        self.assertIn("evidence_chunks", migrations[0].sql)
        self.assertIn("extraction_attempts", migrations[1].sql)
        self.assertIn("graph_write_manifests", migrations[2].sql)
        self.assertIn("conversation_buffer", migrations[3].sql)
        self.assertIn("ALTER TABLE fact_search_index", migrations[4].sql)
        self.assertIn("extraction_attempts", migrations[5].sql)
        self.assertIn("journal_steps", migrations[6].sql)
        self.assertIn("save_points", migrations[7].sql)
        self.assertIn("scenario_id", migrations[8].sql)
        self.assertIn("pre_authored_fact_metadata", migrations[9].sql)
        self.assertIn("ingestion_batches", migrations[10].sql)
        self.assertIn("visible_to_participant_id", migrations[11].sql)
        self.assertIn("journal_steps_idempotency_idx", migrations[12].sql)
        self.assertIn("external_fact_ids", migrations[13].sql)

    def test_apply_is_idempotent(self) -> None:
        connection = FakeConnection()
        self.assertEqual(
            apply_migrations(connection, MIGRATIONS),
            (
                "0001",
                "0002",
                "0003",
                "0004",
                "0005",
                "0006",
                "0007",
                "0008",
                "0009",
                "0010",
                "0011",
                "0012",
                "0013",
                "0014",
            ),
        )
        self.assertEqual(apply_migrations(connection, MIGRATIONS), ())

    def test_checksum_drift_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            migration = directory / "0001_example.sql"
            migration.write_text("SELECT 1;", encoding="utf-8")
            connection = FakeConnection()
            apply_migrations(connection, directory)
            migration.write_text("SELECT 2;", encoding="utf-8")
            with self.assertRaisesRegex(MigrationError, "checksum changed"):
                apply_migrations(connection, directory)

    def test_duplicate_version_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            (directory / "0001_first.sql").write_text("SELECT 1;", encoding="utf-8")
            (directory / "0001_second.sql").write_text("SELECT 2;", encoding="utf-8")
            with self.assertRaisesRegex(MigrationError, "duplicate migration version"):
                discover_migrations(directory)


class RunMigrationsTests(unittest.TestCase):
    """`run_migrations` (composition.py) is the standalone entry point
    `scripts/run_migrations.py` calls -- unlike `build_memory_engine`, it
    opens its own dedicated connection rather than the shared pool."""

    def test_run_migrations_opens_its_own_connection_and_applies(self) -> None:
        fake_connection = FakeConnection()
        with patch("context_memory.composition.psycopg.connect") as mock_connect:
            mock_connect.return_value.__enter__.return_value = fake_connection
            applied = run_migrations(Config(database_url="postgresql://unused"))
        mock_connect.assert_called_once_with("postgresql://unused", autocommit=True)
        self.assertEqual(len(applied), 14)

    def test_run_migrations_returns_empty_tuple_without_touching_db(self) -> None:
        with patch("context_memory.composition.Path") as mock_path:
            mock_path.return_value.resolve.return_value.parents.__getitem__.return_value = Path(
                tempfile.mkdtemp()
            )
            with patch("context_memory.composition.psycopg.connect") as mock_connect:
                applied = run_migrations(Config(database_url="postgresql://unused"))
        mock_connect.assert_not_called()
        self.assertEqual(applied, ())
