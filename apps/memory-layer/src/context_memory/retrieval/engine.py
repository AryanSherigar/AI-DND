"""Phase 2: Hybrid Retrieval Engine implementing the 4-phase retrieval pipeline.

Bare `§N` references below are sections of docs/fixes_and_evaluation_findings.md.
"""

from __future__ import annotations

import contextvars
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from collections.abc import MutableMapping

from context_memory.core.config import Config
from context_memory.core.llm_client import LLMClient
from context_memory.core.logging import get_logger, timed_operation
from context_memory.core.ports import Embedder, GraphTransport
from context_memory.retrieval.detectors import looks_like_count_query
from context_memory.retrieval.models import DateRange, QueryRewriterOutput, RetrievedFact, RetrievedFacts, ScoredFact
from context_memory.retrieval.fuser import CandidateFuser
from context_memory.retrieval.graph_expander import GraphExpander
from context_memory.retrieval.query_rewriter import JsonFileRewriteCache, QueryRewriter
from context_memory.retrieval.reader import AnswerReader
from context_memory.retrieval.reranker import Reranker
from context_memory.retrieval.seeder import CandidateSeeder
from context_memory.retrieval.sibling_expander import SiblingExpander
from context_memory.retrieval.temporal_resolver import TemporalQueryResolver

logger = get_logger(__name__)


def _epoch_to_iso(epoch_seconds: int | None) -> str | None:
    """Fact nodes store valid_from/valid_to as raw epoch ints (graph_plan_builder.py);
    the AI-DND `Fact` contract wants ISO 8601 strings. `9999999999` and `0` are
    graph_plan_builder.py's own open-ended sentinels for "no upper/lower bound",
    not real dates -- surfaced as `None`, matching the contract's `str | None`."""
    if epoch_seconds is None or epoch_seconds in (0, 9999999999):
        return None
    return datetime.fromtimestamp(epoch_seconds, tz=timezone.utc).isoformat()


class HybridRetrievalEngine:
    def __init__(
        self,
        llm_client: LLMClient,
        embedder: Embedder,
        pool: object,
        hydra_client: GraphTransport,
        config: Config | None = None,
        temporal_resolver_client: LLMClient | None = None,
        query_rewriter_client: LLMClient | None = None,
        rerank_client: LLMClient | None = None,
    ) -> None:
        """`llm_client` is the reader/answer-synthesis role, and also the default
        for temporal resolution/query rewriting when no role-specific client is
        given — so a single fake/client injected here still drives every LLM call
        in this engine, same as before role-specific clients existed. Pass
        `temporal_resolver_client`/`query_rewriter_client` explicitly (see
        `routes.py`, which builds them from `Config`) to actually split roles
        across different models."""
        self._llm = llm_client
        self._embedder = embedder
        self._pool = pool
        self._hydra = hydra_client
        self._config = config or Config()
        self._temporal_resolver_client = temporal_resolver_client or llm_client
        self._query_rewriter_client = query_rewriter_client or llm_client
        self._rerank_client = rerank_client or llm_client
        # Engine-lifetime, not per-call: QueryRewriter is constructed per request.
        self._rewrite_cache: MutableMapping[str, QueryRewriterOutput] | None = None
        if self._config.query_rewrite_cache_enabled:
            path = self._config.query_rewrite_cache_path
            self._rewrite_cache = JsonFileRewriteCache(path) if path else {}
        self._seeder = CandidateSeeder(pool, embedder, self._config)
        self._graph_expander = GraphExpander(pool, hydra_client, self._config)
        self._fuser = CandidateFuser(Reranker(self._rerank_client, self._config), self._config)
        self._reader = AnswerReader(
            llm_client, SiblingExpander(pool, embedder, self._config), self._config
        )

    def retrieve_and_answer(self, context_id: str, question: str, question_date: datetime, top_k: int | None = None) -> str:
        ranked, _graph_data, top_k = self._retrieve_ranked(
            context_id, question, question_date, top_k, operation_name="retrieval.retrieve_and_answer"
        )
        if ranked is None:
            return self._config.retrieval_abstention_message
        return self._reader.read(question, ranked[:top_k], context_id, question_date)

    def retrieve_facts(
        self,
        context_id: str,
        query_text: str,
        question_date: datetime,
        game_state: dict | None = None,
        checkpoint: str | None = None,
        as_of_turn: int | None = None,
        top_k: int | None = None,
        template_context_id: str | None = None,
        participant_id: str | None = None,
    ) -> RetrievedFacts:
        """Structured counterpart to `retrieve_and_answer` for the AI-DND
        `POST /v1/memory/query` contract (Milestone 1 of the bridge --
        FINAL_ARCHITECTURE.md's retrieval pipeline is unchanged, this just
        stops before Phase 4's prose synthesis and returns the ranked facts
        themselves instead).

        `checkpoint` implements ADR-9's checkpoint-scoped visibility
        (Milestone 5): a candidate fact whose `checkpoint` hasn't been
        reached yet is dropped before the `top_k` cut -- never consumes a
        results slot it shouldn't. `template_context_id` (derived by the
        caller from `scenario_id`, not `context_id`/`playthrough_id` -- see
        the bridge plan's identifier mapping) is where the scenario's
        ordered checkpoint list lives, since it's authored once per
        scenario, not per playthrough clone.

        `game_state` is accepted (AI-DND memory-layer contract) but no
        longer used to filter here -- Gap B of that contract: `when_active`
        is returned on every `Fact` response instead (see
        `_to_retrieved_fact`), and the caller evaluates it client-side with
        its own already-tested expression grammar, a superset of this
        codebase's own `expression_eval.py`. Kept as a parameter rather
        than dropped, since removing it would be its own wire-contract
        break and the caller still sends it either way.

        §5 fix: `participant_id` and `as_of_turn` actually filter -- a fact
        authored as visible to one participant only
        (`DirectFactInput.visible_to_participant_id`) is dropped for every
        other participant, and a fact extracted from a later turn than
        `as_of_turn` is dropped from an as-of-that-turn query (using
        `turn_number`, written onto the Fact node itself -- see
        graph_plan_builder._fact_node and §4's fix). Both fail OPEN on
        missing data (an older fact with no turn_number, or a query that
        doesn't supply a participant_id against a restricted fact only when
        it can't be evaluated) -- same "config gap is never a silent hide"
        philosophy `_fact_is_visible`'s checkpoint check already uses.
        """
        # AI-DND memory-layer contract (Bug 3): this is the only caller of
        # this endpoint (POST /v1/memory/query, TRS's per-turn blocking
        # call) -- retrieve_and_answer (chat/LongMemEval/benchmark) is a
        # fully separate call path and is never affected by this flag.
        # Skipping Phase 0 (temporal resolver + query rewriter) and the
        # reranker cuts 2-3 real LLM round trips per query; verified safe
        # for this caller's query shape (game-action text, never a
        # real-world date phrase) since the resolver's own "no anchor"
        # fallback -- what it already returns for every query this endpoint
        # has ever sent it -- is reproduced exactly below, not approximated.
        ranked, graph_data, top_k = self._retrieve_ranked(
            context_id, query_text, question_date, top_k,
            operation_name="retrieval.retrieve_facts", skip_llm_stages=True,
        )
        if ranked is None:
            return RetrievedFacts(facts=[], abstained=True, resolved_time_point=None)

        metadata_by_fact_id = self._fetch_fact_metadata(context_id, [f.fact_id for f in ranked])
        checkpoint_order = self._fetch_checkpoint_order(template_context_id) if template_context_id else None
        current_index = (
            checkpoint_order.index(checkpoint)
            if checkpoint_order and checkpoint in checkpoint_order
            else None
        )

        visible = [
            scored for scored in ranked
            if self._fact_is_visible(
                scored, metadata_by_fact_id, checkpoint_order, current_index,
                graph_data, as_of_turn, participant_id,
            )
        ]

        facts = [
            self._to_retrieved_fact(
                scored, graph_data.get(scored.fact_id, {}),
                metadata_by_fact_id.get(scored.fact_id, (None, None, None, False)),
            )
            for scored in visible[:top_k]
        ]
        resolved_time_point = str(as_of_turn) if as_of_turn is not None else None
        return RetrievedFacts(facts=facts, abstained=False, resolved_time_point=resolved_time_point)

    @staticmethod
    def _fact_is_visible(
        scored: ScoredFact, metadata_by_fact_id: dict[str, tuple[str | None, dict | None, str | None, bool]],
        checkpoint_order: list[str] | None, current_index: int | None,
        graph_data: dict, as_of_turn: int | None = None, participant_id: str | None = None,
    ) -> bool:
        fact_checkpoint, _when_active, visible_to_participant_id, _hidden = metadata_by_fact_id.get(
            scored.fact_id, (None, None, None, False)
        )
        # Gap B (AI-DND memory-layer contract handoff): `when_active` is no
        # longer evaluated/filtered here at all -- the product's own
        # request was to shrink mem1's obligation to "return
        # when_active-tagged facts" and let the caller evaluate client-side
        # with its own already-tested grammar (a superset of this
        # codebase's `expression_eval.py`: `in`/`contains`/`matches`/`NOT`,
        # cross-field comparisons). `when_active` is still fetched above
        # and passed through to `_to_retrieved_fact` for the response --
        # only the authoritative filtering moved. `checkpoint`-gating below
        # is unaffected: the product has no client-side equivalent for it,
        # so it stays mem1's job.
        if fact_checkpoint is not None and checkpoint_order is not None and fact_checkpoint in checkpoint_order:
            # Unset/unresolvable current_index (no checkpoint given, or one
            # not in this scenario's own list) and an unrecognized
            # fact_checkpoint both fail OPEN, not closed -- a configuration
            # gap should never silently hide a fact a creator authored to be
            # visible; it only filters when both sides are confidently known.
            required_index = checkpoint_order.index(fact_checkpoint)
            if current_index is None or required_index > current_index:
                return False
        # §5 fix: participant-scoped visibility. A confident mismatch (both
        # sides known, and they differ) hides the fact; a direct engine caller
        # that supplies no participant_id cannot confidently exclude anything,
        # so that case fails open. Checkpoints differ: when ordering exists and
        # the fact's checkpoint is known, a missing/unknown requested checkpoint
        # fails closed above; only absent ordering or an unknown fact checkpoint
        # fails open.
        if (
            visible_to_participant_id is not None
            and participant_id is not None
            and visible_to_participant_id != participant_id
        ):
            return False
        # §5 fix: as_of_turn. A fact with no turn_number (older data,
        # direct-authored facts, or anything predating §4) can't be
        # confidently placed relative to the requested turn, so it fails
        # open rather than vanishing from every as_of_turn query.
        if as_of_turn is not None:
            turn_number = graph_data.get(scored.fact_id, {}).get("turn_number")
            if turn_number is not None and turn_number > as_of_turn:
                return False
        return True

    def _fetch_fact_metadata(
        self, context_id: str, fact_ids: list[str]
    ) -> dict[str, tuple[str | None, dict | None, str | None, bool]]:
        """Keyed by the caller's own `ScoredFact.fact_id` string, not the
        Postgres `INTEGER` column directly -- `fact_id` is only ever a real
        pre-authored graph_id for direct-authored facts (Milestone 3a);
        runtime-extracted facts and test fixtures alike may use non-numeric
        ids, which simply can't have metadata and are skipped rather than
        raising on `int()`."""
        numeric_id_by_fact_id: dict[int, str] = {}
        for fact_id in fact_ids:
            try:
                numeric_id_by_fact_id[int(fact_id)] = fact_id
            except (TypeError, ValueError):
                continue
        if not numeric_id_by_fact_id:
            return {}
        try:
            with self._pool.connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "SELECT fact_id, checkpoint, when_active, visible_to_participant_id, hidden "
                        "FROM pre_authored_fact_metadata WHERE context_id = %s AND fact_id = ANY(%s)",
                        (context_id, list(numeric_id_by_fact_id.keys())),
                    )
                    return {
                        numeric_id_by_fact_id[row[0]]: (row[1], row[2], row[3], bool(row[4]))
                        for row in cursor.fetchall() if row[0] in numeric_id_by_fact_id
                    }
        except Exception as e:
            logger.warning("pre_authored_fact_metadata lookup skipped: %s", e)
            return {}

    def _fetch_checkpoint_order(self, template_context_id: str) -> list[str] | None:
        try:
            with self._pool.connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "SELECT checkpoints FROM scenario_template_checkpoints WHERE context_id = %s",
                        (template_context_id,),
                    )
                    row = cursor.fetchone()
                    return row[0] if row else None
        except Exception as e:
            logger.warning("scenario_template_checkpoints lookup skipped: %s", e)
            return None

    @staticmethod
    def _to_retrieved_fact(
        scored: ScoredFact, graph_fields: dict,
        metadata: tuple[str | None, dict | None, str | None, bool] = (None, None, None, False),
    ) -> RetrievedFact:
        # §9 fix: `subject`/`object_literal` are the real triple components
        # extraction (or direct authoring) wrote onto the Fact node -- used
        # first, so a rules engine gets 'western_gate', not the whole
        # sentence. Both fall back to the pre-existing behavior (the linked
        # ABOUT entity / RELATES_TO entity / full sentence text) for facts
        # that predate this, or where the extractor left them blank.
        entity_key = graph_fields.get("entity_key")
        # logical_key is "entity:<canonical_name>" (graph_plan_builder.py's
        # `_entity_node`) -- split, don't casefold: this is a display value,
        # not the case-normalized matching key fuser.py derives from the same
        # string for scoring purposes.
        entity_subject = entity_key.split(":", 1)[-1] if entity_key else None
        subject = graph_fields.get("subject") or entity_subject or "unknown"
        object_value = (
            graph_fields.get("object_literal")
            or graph_fields.get("object_entity_name")
            or scored.text
        )
        confidence = graph_fields.get("confidence")
        _checkpoint, when_active, _participant, hidden = metadata
        return RetrievedFact(
            fact_id=scored.fact_id,
            subject=subject,
            predicate=graph_fields.get("predicate_key") or "related_to",
            object=object_value,
            valid_from=_epoch_to_iso(graph_fields.get("valid_from")),
            valid_until=_epoch_to_iso(graph_fields.get("valid_to")),
            confidence=confidence if confidence is not None else scored.composite_score,
            # AI-DND memory-layer contract: `hidden` is returned as-is
            # (never filtered by mem1 -- the caller applies its own
            # revealed_facts override). `when_active` is returned instead of
            # evaluated (Gap B) -- `None` for a fact that never had one,
            # which the caller's evaluator should treat as always-active,
            # same convention `expression_eval.evaluate_expression` used
            # here before this fix.
            when_active=when_active,
            hidden=hidden,
        )

    def _retrieve_ranked(
        self, context_id: str, question: str, question_date: datetime, top_k: int | None, operation_name: str,
        skip_llm_stages: bool = False,
    ) -> tuple[list[ScoredFact] | None, dict, int]:
        """Phases 0-3, shared by `retrieve_and_answer` and `retrieve_facts`:
        temporal resolution, query rewriting, seeding, graph expansion, and
        fusion/abstention. Returns `(None, {}, top_k)` on abstention -- callers
        decide what that means for their own response shape. `operation_name`
        keeps each public method's own timed_operation span name (existing
        tests/dashboards key off `retrieval.retrieve_and_answer` specifically)
        even though both now share this one implementation.

        `skip_llm_stages` (AI-DND memory-layer contract, Bug 3): only ever
        `True` from `retrieve_facts`. Skips Phase 0's two LLM calls, using
        each one's own "no anchor / no expansion" fallback directly, and
        skips the reranker in `fuse()` (RRF order stands as final)."""
        # Widen only when the caller left top_k unset -- an explicit override
        # (tests, API callers) is never second-guessed by the heuristic.
        is_count_query = top_k is None and looks_like_count_query(question)
        if top_k is None:
            top_k = self._config.retrieval_count_query_top_k if is_count_query else self._config.retrieval_top_k
        with timed_operation(
            logger, operation_name,
            {"context_id": context_id, "question_len": len(question), "is_count_query": is_count_query, "top_k": top_k},
        ) as ctx:
            # Phase 0: Temporal Resolution & Query Rewriting. Two independent
            # LLM calls -- the rewriter doesn't use temporal_bounds and the
            # resolver doesn't use expanded_query -- run concurrently rather
            # than one after the other; each is a real network round trip, so
            # this halves Phase 0's wall time for free.
            if skip_llm_stages:
                # Exactly TemporalQueryResolver.resolve/QueryRewriter.rewrite's
                # own exception fallbacks -- not new sentinel values -- and,
                # per this endpoint's own resolver prompt, what the LLM call
                # already returns for AI-DND's query shape in practice
                # (verified: no temporal-phrase, no-anchor case, every time).
                temporal_bounds = DateRange()
                expanded_query = QueryRewriterOutput(decomposed_queries=[question], synonyms=[])
            else:
                resolver = TemporalQueryResolver(self._temporal_resolver_client, self._config)
                rewriter = QueryRewriter(self._query_rewriter_client, self._config, cache=self._rewrite_cache)
                # `ThreadPoolExecutor` doesn't propagate `ContextVar`s to its
                # workers (that's asyncio-only) -- without this, both calls'
                # journal rows (Phase 5) lose the request's correlation_id/
                # context_id, each minting its own instead of sharing this
                # request's. A `Context` can only be `.run()` by one thread at a
                # time, so each concurrent task needs its own copy, not one
                # shared snapshot -- two calls is cheap, both still see the same
                # ambient values since neither has diverged from this point yet.
                with ThreadPoolExecutor(max_workers=2) as thread_pool:
                    temporal_future = thread_pool.submit(contextvars.copy_context().run, resolver.resolve, question, question_date)
                    rewriter_future = thread_pool.submit(contextvars.copy_context().run, rewriter.rewrite, question)
                    temporal_bounds = temporal_future.result()
                    expanded_query = rewriter_future.result()

            # Phase 1: Semantic + Keyword Seeding
            seed_facts = self._seeder.seed(context_id, question, expanded_query, top_k)
            ctx["seed_facts_count"] = len(seed_facts)

            # Phase 2: Graph Expansion & Temporal Filtering
            graph_data = self._graph_expander.expand(context_id, seed_facts, temporal_bounds, question_date)
            ctx["graph_expanded_facts"] = len(graph_data)

            # Fallback: Populate missing fact text from PostgreSQL if empty
            missing_text_fids = [fid for fid, fact in seed_facts.items() if not fact.text]
            if missing_text_fids:
                try:
                    with self._pool.connection() as conn:
                        with conn.cursor() as cursor:
                            cursor.execute(
                                "SELECT fact_id, raw_text FROM fact_search_index WHERE context_id = %s AND fact_id = ANY(%s)",
                                (context_id, missing_text_fids)
                            )
                            for r_fid, r_text in cursor.fetchall():
                                if str(r_fid) in seed_facts:
                                    seed_facts[str(r_fid)].text = r_text
                except Exception as e:
                    logger.debug("PostgreSQL fallback fact_search_index query skipped: %s", e)

            # Phase 3: 4-Factor Composite Scoring (Reader Synthesis is the
            # caller's job now -- retrieve_and_answer's, not this method's).
            ranked = self._fuser.fuse(
                question, seed_facts, graph_data, top_k, expanded_query, skip_reranker=skip_llm_stages
            )
            ctx["ranked_count"] = 0 if ranked is None else len(ranked)
            return ranked, graph_data, top_k
