"""mem1 gap #46 fix, proven against a REAL database -- the one thing the pure
in-memory tests in test_fact_projection.py/test_direct_authoring.py/
test_template_clone.py structurally cannot prove: that
`fact_search_index.fact_id` (a bare, non-context-scoped PRIMARY KEY --
db/migrations/0001, 0005) never collides when the same fact is cloned into
more than one playthrough, and that `CandidateSeeder.seed()` -- real SQL
against a real database -- actually finds a projected fact afterward.

Same skip/fixture convention as test_postgres_persistence.py.
"""

from __future__ import annotations

import os
import unittest
from pathlib import Path

try:
    import psycopg
    from psycopg_pool import ConnectionPool
except (
    ImportError
):  # pragma: no cover - exercised only before optional dependency setup
    psycopg = None
    ConnectionPool = None

from context_memory.cloning.template_clone import clone
from context_memory.core.config import Config
from context_memory.ingestion.direct_authoring import (
    DirectEntityInput,
    DirectFactInput,
    write_entity,
    write_fact,
)
from context_memory.ingestion.fact_projection import FactProjectionWriter
from context_memory.ingestion.fakes import (
    DeterministicEmbedder,
    InMemoryGraphIdAllocator,
    InMemoryGraphManifestStore,
)
from context_memory.ingestion.graph_writer import GraphWriter
from context_memory.persistence.migrations import apply_migrations
from context_memory.persistence.postgres import (
    PostgresChunkStore,
    PostgresEmbeddingStore,
    PostgresSearchIndexStore,
)
from context_memory.retrieval.models import QueryRewriterOutput
from context_memory.retrieval.seeder import CandidateSeeder

ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = ROOT / "db" / "migrations"
DATABASE_URL = os.environ.get("CONTEXT_MEMORY_TEST_DATABASE_URL")

_NO_REWRITE = QueryRewriterOutput(decomposed_queries=[], synonyms=[])


class _WriteOnlyTransport:
    """Direct authoring's own graph write -- this test never reads it back,
    only proves the Postgres side (memory_embeddings/fact_search_index)."""

    def write(self, cypher, rows, idempotency_key):
        return f"bookmark-{idempotency_key}"

    def read(self, cypher, parameters, bookmark):
        raise AssertionError("write transport should never be read from")


class _FakeHydraReadTransport:
    """Feeds clone() the one template Fact/Entity it needs to read, same
    content-sniffing convention test_template_clone.py's own FakeHydraTransport
    uses."""

    def __init__(self, entity_rows=(), fact_rows=()):
        self.entity_rows = list(entity_rows)
        self.fact_rows = list(fact_rows)

    def read(self, cypher, parameters, bookmark):
        if "MATCH (n:Entity" in cypher:
            return self.entity_rows
        if "MATCH (n:Fact" in cypher:
            return self.fact_rows
        return []

    def write(self, cypher, rows, idempotency_key):
        raise AssertionError("clone should never write through its own read transport")


@unittest.skipUnless(
    psycopg is not None and DATABASE_URL,
    "requires CONTEXT_MEMORY_TEST_DATABASE_URL and psycopg",
)
class FactProjectionCrossContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.connection = psycopg.connect(DATABASE_URL)
        apply_migrations(cls.connection, MIGRATIONS)
        cls.pool = ConnectionPool(
            DATABASE_URL, min_size=1, max_size=5, kwargs={"autocommit": True}, open=True
        )
        cls.pool.wait(timeout=30)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.connection.close()
        cls.pool.close()

    def _writer(self):
        return FactProjectionWriter(
            DeterministicEmbedder(),
            PostgresEmbeddingStore(self.pool),
            PostgresSearchIndexStore(self.pool),
            PostgresChunkStore(self.pool),
        )

    def _seeder(self):
        return CandidateSeeder(self.pool, DeterministicEmbedder(), Config())

    def test_direct_authored_fact_is_found_by_candidate_seeder(self) -> None:
        allocator = InMemoryGraphIdAllocator()
        graph_writer = GraphWriter(InMemoryGraphManifestStore(), _WriteOnlyTransport())
        projector = self._writer()
        context_id = "it-write-fact-ctx"
        write_entity(
            context_id,
            DirectEntityInput(canonical_name="Sukuna", entity_type="character"),
            allocator,
            graph_writer,
        )

        fact_id = write_fact(
            context_id,
            DirectFactInput(
                predicate="status",
                subject_canonical_name="Sukuna",
                object_literal="alive",
            ),
            allocator,
            graph_writer,
            fact_projector=projector,
        )

        seeded = self._seeder().seed(
            context_id, "Sukuna status alive", _NO_REWRITE, top_k=5
        )
        self.assertIn(str(fact_id), seeded)

    def test_cloning_the_same_template_fact_into_two_playthroughs_does_not_collide(
        self,
    ) -> None:
        source_transport = _FakeHydraReadTransport(
            entity_rows=[
                {
                    "id": 1,
                    "logical_key": "entity:Sukuna",
                    "canonical_name": "Sukuna",
                    "entity_type": "character",
                }
            ],
            fact_rows=[
                {
                    "id": 2,
                    "logical_key": "fact:direct:it-shared-hash",
                    "text": "Sukuna status alive",
                    "predicate_key": "status",
                }
            ],
        )
        allocator = InMemoryGraphIdAllocator()
        writer_a = GraphWriter(InMemoryGraphManifestStore(), _WriteOnlyTransport())
        writer_b = GraphWriter(InMemoryGraphManifestStore(), _WriteOnlyTransport())
        projector = self._writer()
        playthrough_a, playthrough_b = "it-clone-p1", "it-clone-p2"

        clone(
            "it-clone-template",
            playthrough_a,
            allocator,
            writer_a,
            source_transport,
            fact_projector=projector,
        )
        clone(
            "it-clone-template",
            playthrough_b,
            allocator,
            writer_b,
            source_transport,
            fact_projector=projector,
        )

        new_id_a = allocator.allocate_graph_id(
            "fact", playthrough_a, "fact:direct:it-shared-hash"
        )
        new_id_b = allocator.allocate_graph_id(
            "fact", playthrough_b, "fact:direct:it-shared-hash"
        )
        self.assertNotEqual(new_id_a, new_id_b)

        seeded_a = self._seeder().seed(
            playthrough_a, "Sukuna status alive", _NO_REWRITE, top_k=5
        )
        seeded_b = self._seeder().seed(
            playthrough_b, "Sukuna status alive", _NO_REWRITE, top_k=5
        )
        # Each context finds ONLY its own row -- no PK collision silently
        # overwrote or leaked the other context's copy.
        self.assertIn(str(new_id_a), seeded_a)
        self.assertNotIn(str(new_id_b), seeded_a)
        self.assertIn(str(new_id_b), seeded_b)
        self.assertNotIn(str(new_id_a), seeded_b)

        with self.pool.connection() as conn, conn.cursor() as cursor:
            cursor.execute(
                "SELECT context_id, raw_text FROM fact_search_index WHERE fact_id = %s",
                (str(new_id_a),),
            )
            context_id, raw_text = cursor.fetchone()
        self.assertEqual(context_id, playthrough_a)
        self.assertEqual(raw_text, "Sukuna status alive")
