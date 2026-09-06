"""Phase 3a: 4-factor Reciprocal Rank Fusion over the seeded + graph-expanded
candidates, deduped and reranked down to the reader's window.

Bare `§N` references below are sections of docs/fixes_and_evaluation_findings.md.
"""

from __future__ import annotations

import re

from context_memory.core.config import Config
from context_memory.core.logging import get_logger, timed_operation
from context_memory.retrieval.models import QueryRewriterOutput, ScoredFact
from context_memory.retrieval.reranker import Reranker

logger = get_logger(__name__)


class CandidateFuser:
    def __init__(self, reranker: Reranker, config: Config | None = None) -> None:
        self._reranker = reranker
        self._config = config or Config()

    @staticmethod
    def _query_entity_terms(question: str, expanded_query: QueryRewriterOutput | None) -> set[str]:
        """Lowercased tokens from the question (and its rewritten forms) used to
        decide whether a fact's linked entity is one the *query* mentions."""
        parts = [question]
        if expanded_query is not None:
            parts.extend(expanded_query.synonyms)
            parts.extend(expanded_query.decomposed_queries)
        text = " ".join(parts).casefold()
        return {token for token in re.findall(r"[a-z0-9]+", text) if len(token) > 2}

    def fuse(
        self, question: str, facts: dict[str, ScoredFact], graph_data: dict, top_k: int,
        expanded_query: QueryRewriterOutput | None = None,
    ) -> list[ScoredFact] | None:
        """Returns the deduped, reranked candidate list (reader slices to
        `[:top_k]`), or `None` on abstention -- caller substitutes
        `config.retrieval_abstention_message`."""
        with timed_operation(logger, "retrieval.phase3.fuse", {"facts_to_score": len(facts)}) as ctx:
            path_cap = self._config.retrieval_structural_path_cap
            boost_cap = self._config.retrieval_entity_boost_cap
            rrf_k = self._config.retrieval_rrf_k
            query_terms = self._query_entity_terms(question, expanded_query)

            for f_id, fact in facts.items():
                g = graph_data.get(f_id, {"hop_count": 1, "path_count": 0, "entity_fact_count": 0})
                hop_count = g.get("hop_count", 1) or 1
                path_count = g.get("path_count", 0)
                entity_fact_count = g.get("entity_fact_count", 0)

                fact.structural_score = (1.0 / hop_count) * min(path_count, path_cap) / path_cap

                # Boost only entities the QUERY mentions -- FINAL_ARCHITECTURE.md
                # §"Entity boost" gates on `if entity in query_entities`, and
                # dropping that gate is not a small deviation: it hands the same
                # flat boost to every entity-linked fact in the corpus.
                # Measured on LongMemEval 118b2229 ("How long is my daily
                # commute to work?"): the gold fact carried the single highest
                # semantic score of all 113 seeds (0.716) but has no entity
                # link, so it scored 0.231 and ranked #39, while 15 unrelated
                # bike-training facts (semantic 0.58-0.69) each took +0.50 and
                # filled the entire top-15 the reader ever sees. The boost is
                # worth ~3x the entire spread of semantic scores, so ungated it
                # does not tie-break, it overrides.
                entity_key = g.get("entity_key") or ""
                canonical = entity_key.split(":", 1)[-1].casefold()
                entity_matches_query = bool(canonical) and any(
                    token in query_terms for token in re.findall(r"[a-z0-9]+", canonical) if len(token) > 2
                )
                if entity_fact_count > 0 and entity_matches_query:
                    fact.entity_boost = min(boost_cap / max(entity_fact_count, 1), boost_cap)
                else:
                    fact.entity_boost = 0.0

            # Reciprocal Rank Fusion, not a raw-score sum. The previous formula
            # added semantic_score, keyword_score, structural_score, and
            # entity_boost directly -- four differently-scaled signals (a
            # cosine-derived value, a BM25-derived value, a hop-count-derived
            # value, a capped constant) where whichever one happened to read
            # "big" for a given fact dominated the total regardless of how
            # relevant that fact actually was. That is the same failure shape
            # already fixed once for entity_boost specifically (query-gating);
            # RRF fixes it structurally for all four signals at once by fusing
            # on each fact's RANK POSITION within each channel instead of the
            # raw score value, which is scale-invariant by construction --
            # standard k=60 (Cormack et al., "Reciprocal Rank Fusion
            # Outperforms Condorcet and Individual Rank Learning Methods",
            # 2009). structural_score/entity_boost are not literal separate
            # retrieval result lists, so their "rank" is derived by sorting the
            # candidate set by that score descending; a fact with zero score in
            # a channel gets no rank and no term from it, the same "absent
            # means silent, not last-place" rule semantic/keyword already use.
            structural_rank_by_id = {
                f.fact_id: position
                for position, f in enumerate(
                    sorted((f for f in facts.values() if f.structural_score > 0), key=lambda f: -f.structural_score),
                    start=1,
                )
            }
            entity_rank_by_id = {
                f.fact_id: position
                for position, f in enumerate(
                    sorted((f for f in facts.values() if f.entity_boost > 0), key=lambda f: -f.entity_boost),
                    start=1,
                )
            }

            def _rrf_term(rank: int | None) -> float:
                return 1.0 / (rrf_k + rank) if rank is not None else 0.0

            for fact in facts.values():
                fact.composite_score = (
                    _rrf_term(fact.semantic_rank)
                    + _rrf_term(fact.keyword_rank)
                    + _rrf_term(structural_rank_by_id.get(fact.fact_id))
                    + _rrf_term(entity_rank_by_id.get(fact.fact_id))
                )

            # Sort facts
            ranked = sorted(facts.values(), key=lambda f: f.composite_score, reverse=True)

            # Abstention check. Was semantic-only: a fact found purely by BM25
            # keyword match (e.g. an exact name/term the embedding missed) with
            # zero structural support could trigger abstention even with a
            # strong keyword_score, because that score was never looked at.
            # Confirmed reachable: the query rewriter is on the same LLM call
            # path that's failed live in this session (credentials, timeouts),
            # and its failure zeroes every keyword_score for the whole request
            # (see seeder.py) -- but that's a rewriter
            # failure feeding in a real zero, not this check's own bug; abstain
            # only when semantic, keyword, AND structural are all weak.
            threshold = self._config.retrieval_abstention_semantic_threshold
            if not ranked or (
                ranked[0].semantic_score < threshold
                and ranked[0].keyword_score < threshold
                and ranked[0].structural_score == 0
            ):
                ctx["abstention_triggered"] = True
                logger.info(
                    "Retrieval: Abstention triggered (semantic/keyword scores below %s, zero structural score)",
                    threshold,
                )
                return None

            # Distinct fact_ids can carry byte-identical text (the same thing
            # said in two turns), and they were each taking their own slot in
            # the reader window -- observed live consuming 4 of ~40 slots on
            # one question (§21). Only 0.6% of the store store-wide, but the
            # slots are the scarce resource, so dedupe on text before cutting
            # to top_k rather than after.
            seen_text: set[str] = set()
            deduped: list[ScoredFact] = []
            for fact in ranked:
                key = (fact.text or "").strip().casefold()
                if key and key in seen_text:
                    continue
                if key:
                    seen_text.add(key)
                deduped.append(fact)
            ctx["duplicate_facts_dropped"] = len(ranked) - len(deduped)
            ranked = deduped

            ranked = self._reranker.rerank(question, ranked, top_k)

            top_facts = ranked[:top_k]
            excluded = ranked[top_k:]
            ctx["top_fact_score"] = top_facts[0].composite_score if top_facts else 0.0
            ctx["candidates_considered"] = len(ranked)
            ctx["candidates_excluded"] = len(excluded)
            # Every traced retrieval miss so far has had the same shape: the
            # needed fact was seeded and scored, just not high enough to make
            # this cutoff -- crowded out by a fact that matched the question on
            # surface wording (e.g. any dollar amount for a "how much" question)
            # without matching its actual topic. Without this line, finding that
            # required a one-off diagnostic script re-running the whole pipeline
            # by hand each time; now it's one log line per query.
            if top_facts and excluded:
                logger.info(
                    "Retrieval: reader window cutoff (top_k=%d) — last included "
                    "(score=%.3f): %r | first excluded (score=%.3f): %r",
                    top_k, top_facts[-1].composite_score, (top_facts[-1].text or "")[:80],
                    excluded[0].composite_score, (excluded[0].text or "")[:80],
                )

            # Ordered fact ids that reached the reader -- consumed by the
            # oracle retrieval eval (scripts/eval_retrieval_oracle.py).
            ctx["reader_fact_ids"] = [f.fact_id for f in top_facts]

            return ranked
