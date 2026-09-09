"""In-memory vector index over entity display names, for Tier 3 embedding-
similarity entity resolution (see `entity_registry.py`). Not persistence --
this is a process-lifetime NumPy cache, nothing durable.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import numpy as np

from context_memory.core.logging import get_logger

logger = get_logger(__name__)


class EntityNameIndex:
    """Partitioned by haystack_id.

    §12 fix ("entity alias registry remains process-local"): this index --
    and `EntityRegistry`'s own `_profiles` above it -- lives only in this
    process's memory, built up incrementally as `EntityRegistry.register()`
    is called during ingestion. A fresh process/replica starts with zero
    candidates for Tier 3 embedding-similarity blocking, degrading (not
    breaking -- `allocator.allocate_graph_id` is durable/Postgres-backed,
    so a cold replica can never *duplicate* an entity, only miss a fuzzy
    match it hasn't personally re-learned yet) until enough new turns
    rebuild it from scratch. `rebuild_from_entities` below is the real,
    explicit recovery path -- bulk-repopulate from a durable source (a
    HydraDB read of existing Entity nodes for a context, e.g. via
    `cloning.template_clone._read_labeled`'s query shape) instead of
    waiting for organic re-ingestion. Not wired to run automatically
    anywhere: WHEN to warm a fresh replica (every startup? lazily on first
    miss per context_id?) is a deployment-topology decision, not one this
    module should make unilaterally.
    """

    def __init__(self, embedder: Any | None = None) -> None:
        self._embedder = embedder

        self._embeddings: dict[str, np.ndarray] = {}
        self._haystacks: dict[str, str] = {}
        self._types: dict[str, str] = {}
        self._names: dict[str, str] = {}

    def encode_text(self, text: str) -> np.ndarray:
        """Encode text into an L2-normalized 1D float32 numpy vector."""
        if not text or not isinstance(text, str):
            raise ValueError("text must be a non-empty string")
        vector = self._embedder.embed(text)
        return self._normalize_vector(np.asarray(vector, dtype=np.float32))

    def _normalize_vector(self, vector: np.ndarray) -> np.ndarray:
        """Ensure vector is 1D float32 and L2-normalized."""
        vec = np.asarray(vector, dtype=np.float32).flatten()
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec

    def add(
        self,
        entity_id: str,
        name: str,
        entity_type: str,
        haystack_id: str,
    ) -> None:
        """Index an entity display name for semantic blocking."""
        if not entity_id or not isinstance(entity_id, str):
            raise ValueError("entity_id must be a non-empty string")
        if not haystack_id or not isinstance(haystack_id, str):
            raise ValueError("haystack_id must be a non-empty string")
        if not name or not isinstance(name, str):
            raise ValueError("name must be a non-empty string")

        vec = self.encode_text(name)
        self._embeddings[entity_id] = vec
        self._haystacks[entity_id] = haystack_id
        self._types[entity_id] = entity_type
        self._names[entity_id] = name

    def add_vector(
        self,
        entity_id: str,
        vector: np.ndarray,
        name: str,
        entity_type: str,
        haystack_id: str,
    ) -> None:
        """Add pre-computed embedding vector for an entity."""
        if not entity_id or not isinstance(entity_id, str):
            raise ValueError("entity_id must be a non-empty string")
        if not haystack_id or not isinstance(haystack_id, str):
            raise ValueError("haystack_id must be a non-empty string")

        norm_vec = self._normalize_vector(vector)
        self._embeddings[entity_id] = norm_vec
        self._haystacks[entity_id] = haystack_id
        self._types[entity_id] = entity_type
        self._names[entity_id] = name

    def remove(self, entity_id: str) -> None:
        """Remove an entity from the index (e.g. when merged or deleted)."""
        self._embeddings.pop(entity_id, None)
        self._haystacks.pop(entity_id, None)
        self._types.pop(entity_id, None)
        self._names.pop(entity_id, None)

    def find_candidates(
        self,
        query_name: str,
        entity_type: str,
        haystack_id: str,
        top_k: int = 5,
        threshold: float = 0.75,
    ) -> list[dict[str, Any]]:
        """Return candidate entities with similarity >= threshold, scoped to
        haystack_id. Sorted by type_match (True first), then similarity descending."""
        if not haystack_id or not isinstance(haystack_id, str):
            raise ValueError("haystack_id must be a non-empty string")

        query_vec = self.encode_text(query_name)

        candidates = []
        for eid, vec in self._embeddings.items():
            if self._haystacks[eid] != haystack_id:
                continue

            sim = float(np.dot(query_vec, vec))
            if sim >= threshold:
                candidates.append(
                    {
                        "entity_id": eid,
                        "name": self._names[eid],
                        "entity_type": self._types[eid],
                        "similarity": sim,
                        "type_match": self._types[eid] == entity_type,
                    }
                )

        candidates.sort(key=lambda c: (-c["type_match"], -c["similarity"]))
        return candidates[:top_k]

    def rebuild_from_entities(
        self, entities: Iterable[tuple[str, str, str, str]]
    ) -> int:
        """§12 fix: bulk-repopulates this index from a durable source --
        `entities` is `(entity_id, name, entity_type, haystack_id)` tuples,
        e.g. read straight from HydraDB's own Entity nodes. Returns the
        count actually indexed; one entity failing to encode (empty name,
        encoder error) is logged and skipped, not fatal to the rest of the
        rebuild -- a partial recovery is strictly better than none."""
        indexed = 0
        for entity_id, name, entity_type, haystack_id in entities:
            try:
                self.add(entity_id, name, entity_type, haystack_id)
                indexed += 1
            except Exception as error:
                logger.warning(
                    "EntityNameIndex.rebuild_from_entities: skipped %s (%r): %s",
                    entity_id,
                    name,
                    error,
                )
        return indexed

    def clear(self) -> None:
        """Clear all stored entity name embeddings."""
        self._embeddings.clear()
        self._haystacks.clear()
        self._types.clear()
        self._names.clear()

    def size(self, haystack_id: str | None = None) -> int:
        """Return count of indexed entities, optionally filtered by haystack_id."""
        if haystack_id is not None:
            return sum(1 for h in self._haystacks.values() if h == haystack_id)
        return len(self._embeddings)
