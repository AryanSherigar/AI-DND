"""Neighboring-turn evidence expansion (FINAL_ARCHITECTURE.md's ADR-005 tier:
fact+span -> neighboring turn -> full chunk), scored by SCAR so a shared cap
across every anchor's siblings can't starve out a needed fact.
"""

from __future__ import annotations

from context_memory.core.config import Config
from context_memory.core.ports import Embedder


class SiblingExpander:
    def __init__(
        self, pool: object, embedder: Embedder, config: Config | None = None
    ) -> None:
        self._pool = pool
        self._embedder = embedder
        self._config = config or Config()

    def find_siblings(
        self, context_id: str, fact_ids: list[str], question: str
    ) -> dict[str, tuple[str, int | None]]:
        """Returns `{fact_id: (raw_text, observed_at)}` for facts extracted from the same
        source turn as any fact in `fact_ids` -- the "neighboring turn" tier
        of FINAL_ARCHITECTURE.md's ADR-005 progressive evidence expansion
        (fact+span -> neighboring turn -> full chunk), accepted at design time
        but never actually implemented until now.

        Why this matters: a single turn is routinely split into several
        atomic facts at extraction time (by design), and those facts are then
        scored and ranked *independently* in Phase 3. Traced live: "User sold
        20 potted herb plants" and "Each potted herb plant was sold for $7.5"
        come from the same turn, but only the second one scored high enough
        to reach the reader on its own.

        Selection is Reciprocal-adjacent but not RRF: it's Semantic
        Continuity-Aware Retrieval (SCAR; Zhong et al. 2026,
        arxiv.org/abs/2606.16661), chosen over a flat "pull every same-turn
        fact" or a bare `ORDER BY` after the first version of this method hit
        a real, measured failure -- a shared LIMIT across every anchor's
        siblings starved out a needed fact (4 candidates for its own turn,
        available, but never reached: unrelated turns' siblings filled the
        cap first because nothing was scored or ordered). A same-turn fact
        still is not automatically the right one to add -- the actually-
        missing gold fact can just as easily live in a *different* turn
        entirely, which no amount of neighbor expansion reaches; the goal
        here is only to stop within-turn continuity from being either
        all-or-nothing or arbitrarily ordered.

        SCAR scores each candidate neighbor n of anchor a:
            S(a,n) = cos(query, n) - lambda * (1 - cos(a, n))
        and keeps n only if it clears a threshold set *relative to its own
        anchor's* query relevance:
            S(a,n) > gamma * cos(query, a)
        so a weakly-relevant anchor sets a low bar and a strongly-relevant
        one demands genuinely comparable neighbors, rather than one fixed cut
        for every fact regardless of how well it matched in the first place.
        Paper defaults (lambda=0.1, gamma=0.80) are used unchanged -- no
        tuning data of our own exists yet to justify moving them.

        `observed_at` is joined from `extracted_memory_candidates` (subject_id
        is that table's candidate_id for fact-kind embeddings) rather than
        HydraDB, since it's a plain Postgres join, not a second round trip.
        Previously omitted entirely -- siblings reached the reader as bare
        `- {text}` with no date at all, while top-ranked facts carried
        `[YYYY-MM-DD | speaker]`. Measured live (docs/fixes_and_evaluation_findings.md
        §11.2): ~30% of the reader's context (8.6 of ~29 facts/query on
        average) was undated, and it produced a wrong-order answer on a real
        date-arithmetic question with the correctly-dated fact sitting
        unused in the store. Speaker is not carried (no such column here;
        that fact only exists in the HydraDB graph node, and formatting
        the date alone already closes the observed failure mode).
        """
        if not fact_ids:
            return {}
        vector = self._embedder.embed(question)
        vector_literal = "[" + ",".join(repr(float(v)) for v in vector) + "]"
        lam = self._config.retrieval_sibling_continuity_penalty
        gamma = self._config.retrieval_sibling_relevance_ratio

        with self._pool.connection() as conn, conn.cursor() as cursor:
            cursor.execute(
                """
                    SELECT sibling.subject_id, fsi.raw_text, emc.observed_at,
                           (anchor.embedding <=> %s::vector) AS anchor_query_distance,
                           (sibling.embedding <=> %s::vector) AS sibling_query_distance,
                           (anchor.embedding <=> sibling.embedding) AS boundary_distance
                    FROM memory_embeddings anchor
                    JOIN memory_embeddings sibling
                      ON sibling.source_chunk_id = anchor.source_chunk_id
                     AND sibling.context_id = anchor.context_id
                     AND sibling.subject_kind = 'fact'
                     AND sibling.is_active = true
                    JOIN fact_search_index fsi
                      ON fsi.fact_id = sibling.subject_id AND fsi.is_active = true
                    LEFT JOIN extracted_memory_candidates emc
                      ON emc.candidate_id = sibling.subject_id
                    WHERE anchor.context_id = %s
                      AND anchor.subject_kind = 'fact'
                      AND anchor.subject_id = ANY(%s)
                      AND sibling.subject_id != ALL(%s)
                    """,
                (vector_literal, vector_literal, context_id, fact_ids, fact_ids),
            )
            rows = cursor.fetchall()

        # pgvector's <=> is cosine DISTANCE (0 = identical), so similarity is
        # (1 - distance). A sibling reachable via more than one anchor in this
        # batch is scored against each and kept at its best-scoring pairing --
        # SCAR is defined per anchor-neighbor pair, and there is no reason to
        # penalize a fact for happening to sit next to two relevant facts
        # instead of one.
        best: dict[str, tuple[float, str, int | None]] = {}
        for fact_id, raw_text, observed_at, anchor_qd, sibling_qd, boundary_d in rows:
            anchor_relevance = 1.0 - float(anchor_qd)
            sibling_relevance = 1.0 - float(sibling_qd)
            score = sibling_relevance - lam * float(boundary_d)
            if score <= gamma * anchor_relevance:
                continue
            fact_id = str(fact_id)
            observed_epoch = (
                int(observed_at.timestamp()) if observed_at is not None else None
            )
            if fact_id not in best or score > best[fact_id][0]:
                best[fact_id] = (score, raw_text, observed_epoch)

        ranked = sorted(best.items(), key=lambda kv: -kv[1][0])[
            : self._config.retrieval_sibling_fact_limit
        ]
        return {
            fact_id: (text, observed_epoch)
            for fact_id, (_, text, observed_epoch) in ranked
        }
