import pytest
from sentence_transformers import SentenceTransformer

from context_memory.core.id_generator import IdGenerator
from context_memory.ingestion.entity_name_index import EntityNameIndex


@pytest.fixture(scope="module")
def shared_model():
    """Module-scoped shared SentenceTransformer model instance for test speed."""
    return SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2", device="cpu")


@pytest.fixture
def id_gen():
    """IdGenerator instance."""
    return IdGenerator()


class TestEntityNameIndex:
    """Test suite for EntityNameIndex."""

    def test_add_and_find_candidates(self, shared_model, id_gen):
        index = EntityNameIndex(model=shared_model)
        hid = "haystack_001"

        eid1 = id_gen.entity_id(hid, "max", "pet")
        eid2 = id_gen.entity_id(hid, "maxwell", "person")
        eid3 = id_gen.entity_id(hid, "san francisco", "place")

        index.add(eid1, "Max", "pet", hid)
        index.add(eid2, "Maxwell", "person", hid)
        index.add(eid3, "San Francisco", "place", hid)

        assert index.size(hid) == 3

        # Search candidates for mentions of "Max" with entity_type="pet"
        candidates = index.find_candidates("Max", entity_type="pet", haystack_id=hid, threshold=0.7)
        assert len(candidates) >= 1

        # Matching entity type should be ranked first
        top_cand = candidates[0]
        assert top_cand["entity_id"] == eid1
        assert top_cand["entity_type"] == "pet"
        assert top_cand["type_match"] is True

    def test_threshold_filtering(self, shared_model, id_gen):
        index = EntityNameIndex(model=shared_model)
        hid = "haystack_001"

        eid1 = id_gen.entity_id(hid, "golden retriever", "pet")
        index.add(eid1, "Golden Retriever", "pet", hid)

        # High threshold for completely unrelated query returns empty
        candidates = index.find_candidates("Quantum Mechanics", entity_type="topic", haystack_id=hid, threshold=0.75)
        assert len(candidates) == 0

    def test_remove_entity(self, shared_model, id_gen):
        index = EntityNameIndex(model=shared_model)
        hid = "haystack_001"

        eid = id_gen.entity_id(hid, "buddy", "pet")
        index.add(eid, "Buddy", "pet", hid)
        assert index.size(hid) == 1

        index.remove(eid)
        assert index.size(hid) == 0
        candidates = index.find_candidates("Buddy", entity_type="pet", haystack_id=hid, threshold=0.5)
        assert len(candidates) == 0


class _FakeModel:
    """Deterministic stand-in for SentenceTransformer -- no network/model
    download needed for a pure bulk-load unit test."""

    def encode(self, text, normalize_embeddings=True):
        import numpy as np

        digest = sum(ord(c) for c in text) or 1
        return np.random.default_rng(digest).random(8).astype("float32")


class TestRebuildFromEntities:
    """§12 fix: the real recovery path for a process-local index that
    started empty (a fresh replica, or a process restart)."""

    def test_rebuild_populates_the_index(self) -> None:
        index = EntityNameIndex(model=_FakeModel())

        count = index.rebuild_from_entities([
            ("1", "Max", "pet", "hid-1"),
            ("2", "Maxwell", "person", "hid-1"),
        ])

        assert count == 2
        assert index.size("hid-1") == 2

    def test_a_bad_entry_is_skipped_not_fatal_to_the_rest_of_the_rebuild(self) -> None:
        index = EntityNameIndex(model=_FakeModel())

        count = index.rebuild_from_entities([
            ("1", "", "pet", "hid-1"),  # empty name -> add() rejects it
            ("2", "Maxwell", "person", "hid-1"),
        ])

        assert count == 1
        assert index.size("hid-1") == 1
