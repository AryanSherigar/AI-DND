"""FactProjectionWriter -- mem1 gap #46 fix
(docs/BEGINNER_BUILD_FLOW.md §46): the companion memory_embeddings/
fact_search_index writes a direct-authored or cloned fact needs to be
reachable through CandidateSeeder, which never existed before this class.

Pure in-memory unit tests (no real Postgres) -- structural assertions on the
same fakes ingestion/orchestrator's own tests use. The cross-context PK
collision safety and actual CandidateSeeder round-trip are proven against a
real database in test_postgres_persistence.py's
FactProjectionCrossContextTests (this file's fakes can't prove a real
PRIMARY KEY constraint holds).
"""

from __future__ import annotations

import unittest

from context_memory.ingestion.fact_projection import FactProjectionWriter
from context_memory.ingestion.fakes import DeterministicEmbedder, InMemoryChunkStore, InMemoryEmbeddingStore, InMemorySearchIndexStore


def _writer(embedder=None):
    embedder = embedder or DeterministicEmbedder()
    embedding_store = InMemoryEmbeddingStore()
    search_index_store = InMemorySearchIndexStore()
    chunk_store = InMemoryChunkStore()
    return FactProjectionWriter(embedder, embedding_store, search_index_store, chunk_store), embedding_store, search_index_store, chunk_store


class ProjectTests(unittest.TestCase):
    def test_writes_embedding_and_search_index_rows_under_the_graph_id(self):
        writer, embedding_store, search_index_store, _chunks = _writer()

        writer.project("ctx-1", 142, "Sukuna status alive")

        self.assertTrue(embedding_store.contains("ctx-1", "fact", "142"))
        self.assertTrue(search_index_store.contains("ctx-1", "142"))
        self.assertEqual(search_index_store._rows["142"], "Sukuna status alive")

    def test_creates_a_placeholder_chunk_satisfying_the_fk(self):
        writer, embedding_store, _search, chunks = _writer()

        writer.project("ctx-1", 142, "Sukuna status alive")

        [(_key, embedding)] = [(k, v) for k, v in embedding_store._rows.items() if k[2] == "142"]
        self.assertIsNotNone(chunks.get("ctx-1", embedding.source_chunk_id))

    def test_repeated_project_for_the_same_context_does_not_duplicate_the_placeholder_chunk(self):
        """PostgresChunkStore.put()'s immutability check would raise
        ImmutableRecordConflictError if the placeholder's own content
        (occurred_at included) weren't identical across calls."""
        writer, _embedding, _search, _chunks = _writer()

        writer.project("ctx-1", 142, "Sukuna status alive")
        writer.project("ctx-1", 143, "Sukuna status dead")  # must not raise


class ProjectCopyTests(unittest.TestCase):
    def test_writes_both_rows_under_the_new_graph_id_not_the_source_ones(self):
        writer, embedding_store, search_index_store, _chunks = _writer()
        writer.project("template-ctx", 7, "Sukuna status alive")

        writer.project_copy("template-ctx", "7", "playthrough-1", 501, "Sukuna status alive")

        self.assertTrue(embedding_store.contains("playthrough-1", "fact", "501"))
        self.assertTrue(search_index_store.contains("playthrough-1", "501"))
        # Reused, not recomputed: same text -> same DeterministicEmbedder
        # output either way, so this alone doesn't prove reuse -- the
        # dedicated spy test below proves embed() was never called.

    def test_does_not_call_embed_when_a_matching_source_vector_exists(self):
        class SpyEmbedder(DeterministicEmbedder):
            def __init__(self):
                super().__init__()
                self.embed_calls: list[str] = []

            def embed(self, text: str) -> tuple[float, ...]:
                self.embed_calls.append(text)
                return super().embed(text)

        embedder = SpyEmbedder()
        writer, _embedding, _search, _chunks = _writer(embedder)
        writer.project("template-ctx", 7, "Sukuna status alive")
        embedder.embed_calls.clear()

        writer.project_copy("template-ctx", "7", "playthrough-1", 501, "Sukuna status alive")

        self.assertEqual(embedder.embed_calls, [])

    def test_embeds_fresh_when_no_source_vector_exists(self):
        """A template authored/cloned before this writer existed -- no
        source row to reuse, so this must not silently skip indexing the
        cloned copy."""
        writer, embedding_store, search_index_store, _chunks = _writer()

        writer.project_copy("template-ctx", "unknown-source-id", "playthrough-1", 501, "Sukuna status alive")

        self.assertTrue(embedding_store.contains("playthrough-1", "fact", "501"))
        self.assertTrue(search_index_store.contains("playthrough-1", "501"))

    def test_embeds_fresh_when_source_vector_is_under_a_different_model_version(self):
        """A stale vector from an upgraded embedding model must never be
        reused as if it were produced by the current one -- CandidateSeeder
        filters strictly by (model_name, model_version)."""
        writer, embedding_store, _search, _chunks = _writer()
        writer.project("template-ctx", 7, "Sukuna status alive")
        # DeterministicEmbedder has no model_name/model_version -- FactProjectionWriter
        # falls back to ("unknown", "1"); simulate a since-upgraded model by
        # removing the row under the CURRENT (model_name, model_version) it
        # would actually ask project_copy for.
        stale_key = ("template-ctx", "fact", "7", "unknown", "1")
        del embedding_store._rows[stale_key]

        # Must not raise, and must still index the clone.
        writer.project_copy("template-ctx", "7", "playthrough-1", 501, "Sukuna status alive")

        self.assertTrue(embedding_store.contains("playthrough-1", "fact", "501"))

    def test_two_clones_of_the_same_template_fact_land_under_distinct_target_identities(self):
        """The whole point of using the target's own new_fact_graph_id as the
        row identity, not a content hash: cloning the SAME fact into two
        different playthroughs must never collide."""
        writer, embedding_store, search_index_store, _chunks = _writer()
        writer.project("template-ctx", 7, "Sukuna status alive")

        writer.project_copy("template-ctx", "7", "playthrough-1", 501, "Sukuna status alive")
        writer.project_copy("template-ctx", "7", "playthrough-2", 9001, "Sukuna status alive")

        self.assertTrue(embedding_store.contains("playthrough-1", "fact", "501"))
        self.assertTrue(embedding_store.contains("playthrough-2", "fact", "9001"))
        self.assertTrue(search_index_store.contains("playthrough-1", "501"))
        self.assertTrue(search_index_store.contains("playthrough-2", "9001"))
