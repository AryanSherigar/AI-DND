"""Phase 1: semantic (pgvector) + keyword (BM25) candidate seeding."""

from __future__ import annotations

from context_memory.core.config import Config
from context_memory.core.logging import get_logger, timed_operation
from context_memory.core.ports import Embedder
from context_memory.retrieval.models import QueryRewriterOutput, ScoredFact

logger = get_logger(__name__)


class CandidateSeeder:
    def __init__(self, pg_connection: object, embedder: Embedder, config: Config | None = None) -> None:
        self._pg = pg_connection
        self._embedder = embedder
        self._config = config or Config()

    def seed(
        self, context_id: str, question: str, expanded_query: QueryRewriterOutput, top_k: int
    ) -> dict[str, ScoredFact]:
        with timed_operation(logger, "retrieval.phase1.seeding", {"context_id": context_id, "top_k": top_k}) as ctx:
            limit = max(top_k * self._config.retrieval_overfetch_multiplier, self._config.retrieval_overfetch_floor)
            facts = {}

            # 1. Semantic Search
            vector = self._embedder.embed(question)
            vector_literal = "[" + ",".join(repr(float(v)) for v in vector) + "]"

            # §12 fix: was unfiltered by model_name/model_version -- a query
            # vector from the CURRENT embedder got ranked by raw distance
            # against every stored vector regardless of which model/version
            # produced it. `memory_embeddings` is genuinely versioned
            # (Embedding.model_name/model_version, ADR-013/027) precisely so
            # an embedding-model upgrade doesn't require re-embedding
            # everything atomically -- old and new vectors coexist. Without
            # this filter, a distance comparison across two different
            # models' vector spaces is meaningless (and if dimensions ever
            # differ, `<=>` errors outright) -- not just noisy ranking.
            model_name = getattr(self._embedder, "model_name", "unknown")
            model_version = getattr(self._embedder, "model_version", "1")

            with self._pg.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT subject_id, embedding <=> %s::vector AS distance
                    FROM memory_embeddings
                    WHERE context_id = %s AND subject_kind = 'fact' AND is_active = true
                      AND model_name = %s AND model_version = %s
                    ORDER BY distance ASC
                    LIMIT %s
                    """,
                    (vector_literal, context_id, model_name, model_version, limit)
                )
                for position, row in enumerate(cursor.fetchall(), start=1):
                    fact_id = str(row[0])
                    distance = float(row[1]) if row[1] is not None else 0.0
                    semantic_score = 1.0 / (1.0 + distance)
                    if fact_id not in facts:
                        facts[fact_id] = ScoredFact(fact_id, "", semantic_score=semantic_score, semantic_rank=position)
                    else:
                        facts[fact_id].semantic_score = max(facts[fact_id].semantic_score, semantic_score)
                        facts[fact_id].semantic_rank = min(facts[fact_id].semantic_rank or position, position)

            # 2. Keyword Search (BM25). Use websearch_to_tsquery with OR combination and @@ matching
            terms = [t.strip() for t in (expanded_query.synonyms + expanded_query.decomposed_queries + [question]) if t.strip()]
            search_query_str = " OR ".join(f'"{t}"' if " " in t else t for t in terms) if terms else question
            if search_query_str:
                with self._pg.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT fact_id, raw_text, ts_rank_cd(text_tsvector, websearch_to_tsquery('english', %s)) AS rank
                        FROM fact_search_index
                        WHERE context_id = %s AND is_active = true AND text_tsvector @@ websearch_to_tsquery('english', %s)
                        ORDER BY rank DESC
                        LIMIT %s
                        """,
                        (search_query_str, context_id, search_query_str, limit)
                    )
                    position = 0
                    for row in cursor.fetchall():
                        fact_id = str(row[0])
                        raw_text = str(row[1])
                        rank = float(row[2]) if row[2] is not None else 0.0
                        if rank <= 0.0:
                            continue
                        position += 1  # dense rank over accepted rows only, not the raw fetch
                        keyword_score = rank / (1.0 + rank)
                        if fact_id not in facts:
                            facts[fact_id] = ScoredFact(fact_id, raw_text, keyword_score=keyword_score, keyword_rank=position)
                        else:
                            facts[fact_id].keyword_score = max(facts[fact_id].keyword_score, keyword_score)
                            facts[fact_id].keyword_rank = min(facts[fact_id].keyword_rank or position, position)
                            if not facts[fact_id].text:
                                facts[fact_id].text = raw_text

            ctx["total_seeded_facts"] = len(facts)
            return facts
