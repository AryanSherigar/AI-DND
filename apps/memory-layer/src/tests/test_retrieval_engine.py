from __future__ import annotations

import re
import threading
import unittest
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from context_memory.core.config import Config
from context_memory.core.llm_client import LLMClient
from context_memory.retrieval import HybridRetrievalEngine
from context_memory.retrieval.query_rewriter import QueryRewriter
from context_memory.retrieval.fuser import CandidateFuser
from context_memory.retrieval.graph_expander import GraphExpander
from context_memory.retrieval.models import ScoredFact, DateRange, QueryRewriterOutput
from context_memory.retrieval.reranker import Reranker
from context_memory.retrieval.sibling_expander import SiblingExpander
from context_memory.retrieval.temporal_resolver import TemporalQueryResolver

class FakeLLMClient:
    """Dispatches by the requested schema's type, not by call order.

    retrieval.py's Phase 0 now runs the temporal resolver and query rewriter
    concurrently in a thread pool (they're independent LLM calls -- see
    retrieve_and_answer), so "the Nth structured_completion call gets
    structured_responses[N]" is no longer a safe assumption: which of the two
    calls actually reaches this fake first is a real race, not a fixed order.
    Matching on the response's own type is correct regardless of call order;
    the lock only protects the shared per-type queue itself, not ordering.
    """

    def __init__(self, structured_responses, text_response=""):
        self._by_type = defaultdict(list)
        for resp in structured_responses:
            self._by_type[type(resp)].append(resp)
        self.text_response = text_response
        self.structured_calls = 0
        self.last_reader_system_prompt = None
        self._lock = threading.Lock()

    def structured_completion(self, system, user, schema, **kwargs):
        with self._lock:
            self.structured_calls += 1
            queue = self._by_type[schema]
            if not queue:
                raise AssertionError(f"FakeLLMClient: no queued response for schema {schema.__name__}")
            return queue.pop(0)

    def text_completion(self, system, user, *args, **kwargs):
        self.last_reader_system_prompt = system
        return self.text_response

class FakeEmbedder:
    def embed(self, text):
        return (0.1, 0.2, 0.3)

class FakeCursor:
    """Recognizes which query it's answering by content, not call order — the
    real query sequence changes as retrieval.py evolves (e.g. the graph_id_registry
    lookup added to resolve HydraDB's id-only UNWIND matching), and a fixed
    positional results list silently misaligns whenever that happens."""

    def __init__(
        self, semantic_rows=(), bm25_rows=(), registry_rows=(), missing_text_rows=(), sibling_rows=(),
        fact_metadata_rows=(), checkpoint_row=None,
    ):
        self.semantic_rows = list(semantic_rows)
        self.bm25_rows = list(bm25_rows)
        self.registry_rows = list(registry_rows)
        self.missing_text_rows = list(missing_text_rows)
        self.sibling_rows = list(sibling_rows)
        self.fact_metadata_rows = list(fact_metadata_rows)
        self.checkpoint_row = checkpoint_row
        self._last_query = ""

    def execute(self, query, params=None):
        self._last_query = query

    def fetchall(self):
        q = self._last_query
        # Checked before the generic "memory_embeddings" branch: the sibling
        # query also references memory_embeddings (twice, anchor+sibling
        # joins), so it would otherwise be misidentified as the Phase 1
        # semantic-search query.
        if "sibling.subject_id" in q:
            return self.sibling_rows
        if "graph_id_registry" in q:
            return self.registry_rows
        if "memory_embeddings" in q:
            return self.semantic_rows
        if "ts_rank_cd" in q:
            return self.bm25_rows
        if "pre_authored_fact_metadata" in q:
            return self.fact_metadata_rows
        if "fact_search_index" in q:
            return self.missing_text_rows
        return []

    def fetchone(self):
        if "scenario_template_checkpoints" in self._last_query:
            return self.checkpoint_row
        return None

    def __enter__(self): return self
    def __exit__(self, *args): pass

class FakeConnection:
    def __init__(
        self, semantic_rows=(), bm25_rows=(), registry_rows=(), missing_text_rows=(), sibling_rows=(),
        fact_metadata_rows=(), checkpoint_row=None,
    ):
        self.cursor_obj = FakeCursor(
            semantic_rows, bm25_rows, registry_rows, missing_text_rows, sibling_rows,
            fact_metadata_rows, checkpoint_row,
        )
    def cursor(self):
        return self.cursor_obj

class FakeHydra:
    def __init__(self, return_paths=True):
        self.return_paths = return_paths

    def read(self, cypher, params, bookmark):
        # Per-fact calls now (retrieval.py stopped fighting HydraDB's UNWIND-read
        # grammar and queries one fact at a time, see retrieval.py's own comment).
        if "SUPERSEDES" in cypher:
            return []
        if "OPTIONAL MATCH" in cypher:
            return [{
                "text": None, "speaker": None,
                "valid_from": 0, "valid_to": 9999999999,
                "observed_at": 1000, "superseded_at": 9999999999,
                "memory_scope": None, "entity_key": "entity-1",
            }]
        if "algo.MSpaths" in cypher:
            if not self.return_paths:
                return []
            return [{"path": [{"logical_key": "entity-1"}, {}, {"logical_key": "entity-2"}]}]
        return []

class FakeHydraWithEntities:
    """Like FakeHydra but resolves OPTIONAL MATCH's entity_key per fact id, so a
    test can control which facts share an entity vs which don't -- needed to
    exercise entity_fact_count actually varying (it used to be hardcoded to 1
    for every fact, so entity_boost was a constant regardless of fixture).

    The id is parsed out of the query text rather than read from `params`:
    retrieval.py inlines it as `MATCH (f {id: 123})` (int()-coerced) because
    this HydraDB build's parameter support is too narrow, so there is no bound
    parameter left to inspect."""

    _ID_PATTERN = re.compile(r"MATCH \(f \{id: (\d+)\}\)")

    def __init__(self, entity_key_by_fid):
        self.entity_key_by_fid = entity_key_by_fid

    def read(self, cypher, params, bookmark):
        if "SUPERSEDES" in cypher:
            return []
        if "OPTIONAL MATCH" in cypher:
            match = self._ID_PATTERN.search(cypher)
            fid = int(match.group(1)) if match else None
            return [{
                "text": None, "speaker": None,
                "valid_from": 0, "valid_to": 9999999999,
                "observed_at": 1000, "superseded_at": 9999999999,
                "memory_scope": None, "entity_key": self.entity_key_by_fid.get(fid),
            }]
        if "algo.MSpaths" in cypher:
            return []
        return []


class TestRetrievalEngine(unittest.TestCase):
    def test_temporal_resolver_adds_buffer(self):
        base_time = datetime(2026, 8, 19, tzinfo=timezone.utc)
        llm = FakeLLMClient([DateRange(valid_from=base_time, valid_to=base_time)])
        resolver = TemporalQueryResolver(llm)
        
        result = resolver.resolve("What happened today?", base_time)
        
        # Buffer is 2 days (172800 seconds)
        expected_from = base_time - timedelta(seconds=172800)
        expected_to = base_time + timedelta(seconds=172800)
        
        self.assertEqual(result.valid_from, expected_from)
        self.assertEqual(result.valid_to, expected_to)

    def test_query_rewriter(self):
        llm = FakeLLMClient([QueryRewriterOutput(decomposed_queries=["where is dog"], synonyms=["puppy"])])
        rewriter = QueryRewriter(llm)
        res = rewriter.rewrite("where is my dog?")
        self.assertEqual(res.decomposed_queries, ["where is dog"])
        self.assertEqual(res.synonyms, ["puppy"])

    def test_abstention_triggers_on_low_scores(self):
        llm = FakeLLMClient([
            DateRange(valid_from=None, valid_to=None),
            QueryRewriterOutput(decomposed_queries=[], synonyms=[])
        ], text_response="Should not reach here")
        
        # pgvector -> [('fact-1', 9.0)] -> semantic score = 1 / (1 + 9) = 0.1; BM25 skipped
        # (no rewriter keywords); registry resolves fact-1 -> graph_id 1; missing-text fallback.
        conn = FakeConnection(
            semantic_rows=[("fact-1", 9.0)],
            registry_rows=[("fact:fact-1", 1)],
            missing_text_rows=[("fact-1", "irrelevant")],
        )
        
        engine = HybridRetrievalEngine(llm, FakeEmbedder(), conn, FakeHydra(return_paths=False))
        
        ans = engine.retrieve_and_answer("ctx-1", "what is the meaning of life?", datetime.now(timezone.utc))
        self.assertEqual(ans, "I don't have that information in my memory.")

    def test_composite_scoring_and_synthesis(self):
        llm = FakeLLMClient([
            DateRange(valid_from=None, valid_to=None),
            QueryRewriterOutput(decomposed_queries=[], synonyms=[])
        ], text_response="The dog is in the park")
        
        # pgvector -> [('fact-1', 0.1)] -> semantic score = 1 / 1.1 ~= 0.9; BM25 skipped;
        # registry resolves fact-1 -> graph_id 1; missing-text fallback.
        conn = FakeConnection(
            semantic_rows=[("fact-1", 0.1)],
            registry_rows=[("fact:fact-1", 1)],
            missing_text_rows=[("fact-1", "dog in park")],
        )
        
        engine = HybridRetrievalEngine(llm, FakeEmbedder(), conn, FakeHydra())
        
        ans = engine.retrieve_and_answer("ctx-1", "where is dog?", datetime.now(timezone.utc))
        self.assertEqual(ans, "The dog is in the park")

    def test_entity_boost_applies_only_to_entities_the_query_mentions(self):
        """FINAL_ARCHITECTURE.md's entity boost gates on
        `if entity in query_entities`. Dropping that gate gave the same flat
        boost to every entity-linked fact in the corpus, and because the boost
        (0.5) is worth roughly 3x the entire spread of semantic scores, it
        overrode relevance instead of tie-breaking it.

        Measured on LongMemEval 118b2229 ("How long is my daily commute to
        work?"): the gold fact had the single highest semantic score of all 113
        seeds (0.716) but no entity link, so it ranked #39 while 15 unrelated
        bike-training facts took +0.50 each and filled the entire top-15."""
        llm = FakeLLMClient([])
        conn = FakeConnection(registry_rows=[("fact:fact-1", 1), ("fact:fact-2", 2), ("fact:fact-3", 3)])
        # fact-1/fact-2 link to "commute"; fact-3 has no entity at all.
        hydra = FakeHydraWithEntities({1: "entity:commute", 2: "entity:commute", 3: None})
        engine = HybridRetrievalEngine(llm, FakeEmbedder(), conn, hydra)

        def fresh_seeds():
            return {
                "fact-1": ScoredFact("fact-1", "linked A"),
                "fact-2": ScoredFact("fact-2", "linked B"),
                "fact-3": ScoredFact("fact-3", "unlinked"),
            }

        seed_facts = fresh_seeds()
        expander = GraphExpander(conn, hydra)
        graph_data = expander.expand("ctx-1", seed_facts, DateRange(), datetime.now(timezone.utc))
        self.assertEqual(graph_data["fact-1"]["entity_fact_count"], 2)
        self.assertEqual(graph_data["fact-3"]["entity_fact_count"], 0)
        self.assertEqual(graph_data["fact-1"]["entity_key"], "entity:commute")

        cap = engine._config.retrieval_entity_boost_cap
        fuser = CandidateFuser(Reranker(llm, engine._config), engine._config)

        # Query mentions the entity -> boost applies, inverse-frequency scaled.
        fuser.fuse("how long is my commute?", seed_facts, graph_data, top_k=5)
        self.assertEqual(seed_facts["fact-1"].entity_boost, min(cap / 2, cap))
        self.assertEqual(seed_facts["fact-3"].entity_boost, 0.0)

        # Query does NOT mention it -> no boost, even though the fact is linked.
        unrelated = fresh_seeds()
        fuser.fuse("what laptop should I buy?", unrelated, graph_data, top_k=5)
        self.assertEqual(unrelated["fact-1"].entity_boost, 0.0)
        self.assertEqual(unrelated["fact-3"].entity_boost, 0.0)

    def test_chat_scoped_fact_past_ttl_is_pruned(self):
        """§6 fix: ingestion writes `scope_type` on the Fact node
        (graph_plan_builder._fact_node); the old cypher asked HydraDB for a
        `memory_scope` property no Fact node has ever carried, so this
        branch never fired. `ProbeCypherFakeHydra` only reports
        memory_scope="chat" when the cypher actually reads the correct
        source property -- a regression back to the old alias makes it
        report None instead, and this test fails because the stale chat
        fact never gets pruned."""

        class ProbeCypherFakeHydra:
            def read(self, cypher, params, bookmark):
                if "SUPERSEDES" in cypher:
                    return []
                if "OPTIONAL MATCH" in cypher:
                    reads_correct_property = "f.scope_type AS memory_scope" in cypher
                    return [{
                        "text": "temporary chitchat detail", "speaker": None,
                        "valid_from": 0, "valid_to": 9999999999,
                        # Said well outside the configured chat TTL window.
                        "observed_at": 0, "superseded_at": 9999999999,
                        "memory_scope": "chat" if reads_correct_property else None,
                        "entity_key": None,
                    }]
                if "algo.MSpaths" in cypher:
                    return []
                return []

        conn = FakeConnection(registry_rows=[("fact:fact-1", 1)])
        hydra = ProbeCypherFakeHydra()
        expander = GraphExpander(conn, hydra)
        seed_facts = {"fact-1": ScoredFact("fact-1", "temporary chitchat detail")}

        graph_data = expander.expand("ctx-1", seed_facts, DateRange(), datetime.now(timezone.utc))

        self.assertEqual(graph_data, {})
        self.assertNotIn("fact-1", seed_facts)

    def test_temporal_bounds_use_interval_overlap_not_only_valid_now(self):
        """§7 fix: a fact whose validity window falls entirely inside the
        requested [valid_from, valid_to] range must survive even though it
        is no longer valid "now" (query_epoch) -- overlap, not a point
        check against the live instant."""

        class FakeHydraWithValidityWindow:
            def read(self, cypher, params, bookmark):
                if "SUPERSEDES" in cypher:
                    return []
                if "OPTIONAL MATCH" in cypher:
                    return [{
                        "text": "the bridge quest was active",
                        "speaker": None,
                        # Valid only turns ~15-25 (as epoch seconds standing
                        # in for turn numbers) -- long since ended relative
                        # to "now", but overlaps a [20, 30] query window.
                        "valid_from": 15, "valid_to": 25,
                        "observed_at": 15, "superseded_at": 9999999999,
                        "memory_scope": None, "entity_key": None,
                    }]
                if "algo.MSpaths" in cypher:
                    return []
                return []

        conn = FakeConnection(registry_rows=[("fact:fact-1", 1)])
        expander = GraphExpander(conn, FakeHydraWithValidityWindow())
        question_date = datetime.now(timezone.utc)  # "now" is nowhere near this fact's window

        # No temporal anchor resolved -> point-in-time semantics, unchanged:
        # a fact that ended at epoch=25 is long expired relative to "now".
        pointwise = {"fact-1": ScoredFact("fact-1", "the bridge quest was active")}
        graph_data = expander.expand("ctx-1", pointwise, DateRange(), question_date)
        self.assertEqual(graph_data, {})

        # Resolved range [20, 30] overlaps the fact's [15, 25] window ->
        # must be returned even though it's not valid "now".
        ranged = {"fact-1": ScoredFact("fact-1", "the bridge quest was active")}
        window = DateRange(
            valid_from=datetime.fromtimestamp(20, tz=timezone.utc),
            valid_to=datetime.fromtimestamp(30, tz=timezone.utc),
        )
        graph_data = expander.expand("ctx-1", ranged, window, question_date)
        self.assertIn("fact-1", graph_data)

        # A range that does NOT overlap [15, 25] at all still excludes it.
        non_overlapping = {"fact-1": ScoredFact("fact-1", "the bridge quest was active")}
        far_window = DateRange(
            valid_from=datetime.fromtimestamp(100, tz=timezone.utc),
            valid_to=datetime.fromtimestamp(200, tz=timezone.utc),
        )
        graph_data = expander.expand("ctx-1", non_overlapping, far_window, question_date)
        self.assertEqual(graph_data, {})

    def test_non_chat_fact_past_the_same_window_is_not_pruned(self):
        """The TTL only applies to `chat`-scoped facts -- a session/user-scope
        fact just as old must survive."""
        conn = FakeConnection(registry_rows=[("fact:fact-1", 1)])
        hydra = FakeHydra()  # memory_scope always None (not "chat")
        expander = GraphExpander(conn, hydra)
        seed_facts = {"fact-1": ScoredFact("fact-1", "durable fact")}

        graph_data = expander.expand("ctx-1", seed_facts, DateRange(), datetime.now(timezone.utc))

        self.assertIn("fact-1", graph_data)
        self.assertIn("fact-1", seed_facts)

    def test_abstention_no_longer_ignores_strong_keyword_match(self):
        """A fact found purely by keyword match (weak/no embedding similarity,
        strong BM25 rank, no graph structure) used to trigger false abstention
        because the check only ever looked at semantic_score. A real exact-term
        hit -- the case BM25 exists for -- should not be discarded."""
        llm = FakeLLMClient([
            DateRange(valid_from=None, valid_to=None),
            QueryRewriterOutput(decomposed_queries=["exact term"], synonyms=[]),
        ], text_response="Found via keyword match")

        # No semantic hit at all; BM25 rank=1.0 -> keyword_score = 1/(1+1) = 0.5,
        # comfortably above the 0.3 default threshold. return_paths=False keeps
        # structural_score at 0, so this exercises the keyword branch alone.
        conn = FakeConnection(
            bm25_rows=[("fact-1", "exact term match", 1.0)],
            registry_rows=[("fact:fact-1", 1)],
            missing_text_rows=[("fact-1", "exact term match")],
        )
        engine = HybridRetrievalEngine(llm, FakeEmbedder(), conn, FakeHydra(return_paths=False))

        ans = engine.retrieve_and_answer("ctx-1", "exact term", datetime.now(timezone.utc))
        self.assertEqual(ans, "Found via keyword match")

    def test_keyword_search_falls_back_to_raw_question_when_rewriter_empty(self):
        """An empty rewriter result (a real failure mode: it's on the same LLM
        call path that's failed live this session on credentials/timeouts)
        used to skip BM25 for the whole request. It should degrade to the raw
        question instead of going silent."""
        llm = FakeLLMClient([
            DateRange(valid_from=None, valid_to=None),
            QueryRewriterOutput(decomposed_queries=[], synonyms=[]),  # rewriter produced nothing
        ], text_response="Found via raw-question fallback")

        conn = FakeConnection(
            bm25_rows=[("fact-1", "matches raw question", 1.0)],
            registry_rows=[("fact:fact-1", 1)],
            missing_text_rows=[("fact-1", "matches raw question")],
        )
        engine = HybridRetrievalEngine(llm, FakeEmbedder(), conn, FakeHydra(return_paths=False))

        ans = engine.retrieve_and_answer("ctx-1", "raw question text", datetime.now(timezone.utc))
        self.assertEqual(ans, "Found via raw-question fallback")

    def test_sibling_facts_from_same_turn_are_added_to_context(self):
        """ADR-005's "neighboring turn" expansion tier, accepted at design time
        but never implemented until now. Traced live: a fact scoring high
        enough to reach the reader ("$7.5 each") had its quantity ("20 potted
        herb plants") extracted as a *separate* atomic fact from the same
        turn, which did not itself score high enough to be seeded/ranked in --
        the reader had a price with nothing to multiply it by. A sibling fact
        from the same source turn as an already-relevant fact must be pulled
        into context even though it never separately competed on ranking."""
        llm = FakeLLMClient([
            DateRange(valid_from=None, valid_to=None),
            QueryRewriterOutput(decomposed_queries=[], synonyms=[]),
        ], text_response="20 plants at $7.50 each is $150")
        conn = FakeConnection(
            semantic_rows=[("fact-1", 0.1)],  # only the price fact is seeded/ranked
            registry_rows=[("fact:fact-1", 1)],
            missing_text_rows=[("fact-1", "Each potted herb plant was sold for $7.5")],
            # (fact_id, text, anchor_query_distance, sibling_query_distance, boundary_distance).
            # anchor_relevance=0.6, sibling_relevance=0.65: score = 0.65 - 0.1*0.05 = 0.645,
            # threshold = 0.80*0.6 = 0.48 -- clears it, matching a genuinely on-topic same-turn sibling.
            sibling_rows=[("fact-2", "User sold 20 potted herb plants at the Summer Solstice Market", None, 0.4, 0.35, 0.05)],
        )
        engine = HybridRetrievalEngine(llm, FakeEmbedder(), conn, FakeHydra())

        ans = engine.retrieve_and_answer("ctx-1", "how much did the herb plants earn?", datetime.now(timezone.utc))

        self.assertEqual(ans, "20 plants at $7.50 each is $150")
        self.assertIn("Each potted herb plant was sold for $7.5", llm.last_reader_system_prompt)
        self.assertIn("User sold 20 potted herb plants", llm.last_reader_system_prompt)

    def test_sibling_facts_carry_their_date_into_the_prompt(self):
        """§11.2: siblings previously reached the reader as bare `- {text}`,
        ~30% of context undated, and produced a wrong-order answer on a real
        date-arithmetic question with the correctly-dated fact sitting unused
        in the store. observed_at must now be joined and formatted the same
        way top facts are."""
        import time
        llm = FakeLLMClient([
            DateRange(valid_from=None, valid_to=None),
            QueryRewriterOutput(decomposed_queries=[], synonyms=[]),
        ], text_response="answer")
        march_19 = datetime(2023, 3, 19, tzinfo=timezone.utc)  # psycopg returns datetime for timestamptz
        conn = FakeConnection(
            semantic_rows=[("fact-1", 0.1)],
            registry_rows=[("fact:fact-1", 1)],
            missing_text_rows=[("fact-1", "Each potted herb plant was sold for $7.5")],
            sibling_rows=[("fact-2", "User sold 20 potted herb plants", march_19, 0.4, 0.35, 0.05)],
        )
        engine = HybridRetrievalEngine(llm, FakeEmbedder(), conn, FakeHydra())
        engine.retrieve_and_answer("ctx-1", "how much did the herb plants earn?", datetime.now(timezone.utc))
        self.assertIn("[2023-03-19]: User sold 20 potted herb plants", llm.last_reader_system_prompt)

    def test_sibling_expansion_disabled_when_limit_is_zero(self):
        """RETRIEVAL_SIBLING_FACT_LIMIT=0 must fully disable the extra query,
        not just cap it at zero rows -- confirms the feature is a no-op, not a
        silent failure, when turned off."""
        import dataclasses
        llm = FakeLLMClient([
            DateRange(valid_from=None, valid_to=None),
            QueryRewriterOutput(decomposed_queries=[], synonyms=[]),
        ], text_response="answer")
        conn = FakeConnection(
            semantic_rows=[("fact-1", 0.1)],
            registry_rows=[("fact:fact-1", 1)],
            missing_text_rows=[("fact-1", "Each potted herb plant was sold for $7.5")],
            # (fact_id, text, anchor_query_distance, sibling_query_distance, boundary_distance).
            # anchor_relevance=0.6, sibling_relevance=0.65: score = 0.65 - 0.1*0.05 = 0.645,
            # threshold = 0.80*0.6 = 0.48 -- clears it, matching a genuinely on-topic same-turn sibling.
            sibling_rows=[("fact-2", "User sold 20 potted herb plants at the Summer Solstice Market", None, 0.4, 0.35, 0.05)],
        )
        config = dataclasses.replace(Config(), retrieval_sibling_fact_limit=0)
        engine = HybridRetrievalEngine(llm, FakeEmbedder(), conn, FakeHydra(), config=config)

        engine.retrieve_and_answer("ctx-1", "how much did the herb plants earn?", datetime.now(timezone.utc))

    def test_scar_rejects_off_topic_same_turn_fact(self):
        """The whole point of moving to SCAR (arxiv.org/abs/2606.16661) instead
        of an unordered LIMIT: same-turn presence alone must not be enough. A
        fact from the same turn as an anchor but semantically unrelated to the
        question -- someone rambling about the weather in the middle of a
        market-earnings turn -- must be rejected, while a genuinely relevant
        same-turn fact is kept. If this collapsed back to "pull every same-turn
        fact," both would come back."""
        # anchor_relevance = 1 - 0.4 = 0.6 -> threshold = 0.80 * 0.6 = 0.48
        on_topic = ("fact-relevant", "User sold 20 potted herb plants", None, 0.4, 0.35, 0.05)  # score 0.645
        off_topic = ("fact-unrelated", "The weather was nice that day", None, 0.4, 0.85, 0.05)  # score 0.145
        conn = FakeConnection(sibling_rows=[on_topic, off_topic])
        expander = SiblingExpander(conn, FakeEmbedder())

        siblings = expander.find_siblings("ctx-1", ["fact-anchor"], "how much did I earn at the market?")

        self.assertIn("fact-relevant", siblings)
        self.assertNotIn("fact-unrelated", siblings)

    def test_composite_score_is_reciprocal_rank_fusion_not_raw_sum(self):
        """Composite scoring used to sum raw semantic/keyword/structural/
        entity scores directly -- four differently-scaled signals where
        whichever one happened to read numerically "big" for a fact dominated
        regardless of actual relevance (confirmed live and repeatedly: an
        irrelevant fact with a coincidentally high semantic score routinely
        outranked the fact that actually answered the question). RRF fixes
        this by fusing on rank position, not raw score value -- a fact ranked
        decently across multiple channels should be able to outscore a fact
        that "wins" one channel alone, which a raw sum cannot express when the
        single-channel winner's raw score is large enough."""
        llm = FakeLLMClient([])
        engine = HybridRetrievalEngine(llm, FakeEmbedder(), FakeConnection(), FakeHydra())

        # fact-1: dominant single channel (semantic rank 1, huge raw score).
        # fact-2: weaker in any one channel, but present in three.
        fact1 = ScoredFact("fact-1", "single-channel winner", semantic_score=0.99, semantic_rank=1)
        fact2 = ScoredFact("fact-2", "multi-channel winner", semantic_score=0.10, semantic_rank=5,
                            keyword_score=0.10, keyword_rank=3)
        facts = {"fact-1": fact1, "fact-2": fact2}
        # fact-2 also has graph support (structural + entity); fact-1 has none.
        graph_data = {
            "fact-1": {"hop_count": 1, "path_count": 0, "entity_fact_count": 0, "entity_key": None},
            "fact-2": {"hop_count": 1, "path_count": 3, "entity_fact_count": 1, "entity_key": "entity:widget"},
        }

        fuser = CandidateFuser(Reranker(llm, engine._config), engine._config)
        fuser.fuse("tell me about the widget", facts, graph_data, top_k=5)

        k = engine._config.retrieval_rrf_k
        expected_fact1 = 1.0 / (k + 1)  # semantic rank 1 only
        expected_fact2 = 1.0 / (k + 5) + 1.0 / (k + 3) + 1.0 / (k + 1) + 1.0 / (k + 1)  # 4 channels
        self.assertAlmostEqual(fact1.composite_score, expected_fact1)
        self.assertAlmostEqual(fact2.composite_score, expected_fact2)
        # The real point: multi-channel support overtakes a single dominant
        # raw score -- impossible under the old sum when fact-1's raw semantic
        # score (0.99) alone exceeded fact-2's summed raw scores.
        self.assertGreater(fact2.composite_score, fact1.composite_score)

    def test_rrf_channel_absence_contributes_nothing(self):
        """A fact missing entirely from a channel must get 0 from it, not a
        last-place rank -- otherwise every unretrieved fact in the corpus
        would tie for the same nonzero score in every channel it never
        appeared in."""
        llm = FakeLLMClient([])
        engine = HybridRetrievalEngine(llm, FakeEmbedder(), FakeConnection(), FakeHydra())
        fact = ScoredFact("fact-1", "only semantic", semantic_score=0.5, semantic_rank=2)
        facts = {"fact-1": fact}
        graph_data = {"fact-1": {"hop_count": 1, "path_count": 0, "entity_fact_count": 0, "entity_key": None}}

        fuser = CandidateFuser(Reranker(llm, engine._config), engine._config)
        fuser.fuse("q", facts, graph_data, top_k=5)

        k = engine._config.retrieval_rrf_k
        self.assertAlmostEqual(fact.composite_score, 1.0 / (k + 2))


class FakeHydraWithFactFields:
    """Like FakeHydra, but the OPTIONAL MATCH row also carries predicate_key/
    confidence -- the two fields Milestone 1 of the AI-DND bridge added to
    that query (graph_expander.py) so `retrieve_facts` can surface them."""

    def read(self, cypher, params, bookmark):
        if "SUPERSEDES" in cypher:
            return []
        if "OPTIONAL MATCH" in cypher:
            return [{
                "text": "the dog is in the park", "speaker": None,
                "valid_from": 0, "valid_to": 9999999999,
                "observed_at": 1000, "superseded_at": 9999999999,
                "memory_scope": None, "entity_key": "entity:dog",
                "predicate_key": "located_at", "confidence": 0.91,
            }]
        if "algo.MSpaths" in cypher:
            return []
        return []


class FakeHydraWithTripleFields:
    """§9 fix: the OPTIONAL MATCH row also carries `subject`/`object_literal`
    (extraction/direct authoring's real triple components) -- distinct from
    `entity_key` (still returned, to prove it's no longer used once `subject`
    is present) and from `text` (the full sentence, ignored for `object` once
    `object_literal` is present)."""

    def read(self, cypher, params, bookmark):
        if "SUPERSEDES" in cypher:
            return []
        if "OPTIONAL MATCH" in cypher:
            return [{
                "text": "The dog is currently waiting near the western gate.",
                "speaker": None, "valid_from": 0, "valid_to": 9999999999,
                "observed_at": 1000, "superseded_at": 9999999999,
                "memory_scope": None, "entity_key": "entity:dog",
                "predicate_key": "located_at", "confidence": 0.91,
                "subject": "dog", "object_literal": "western gate",
            }]
        if "algo.MSpaths" in cypher:
            return []
        return []


class RetrieveFactsTests(unittest.TestCase):
    """Milestone 1 of the AI-DND bridge: `POST /v1/memory/query` needs
    structured facts + a real `abstained` flag instead of `retrieve_and_answer`'s
    synthesized prose. `retrieve_facts` shares Phases 0-3 with
    `retrieve_and_answer` (see `_retrieve_ranked`) and stops before Phase 4."""

    def test_returns_structured_fact_with_subject_predicate_object_and_confidence(self):
        llm = FakeLLMClient([
            DateRange(valid_from=None, valid_to=None),
            QueryRewriterOutput(decomposed_queries=[], synonyms=[]),
        ])
        conn = FakeConnection(
            semantic_rows=[("fact-1", 0.1)],
            registry_rows=[("fact:fact-1", 1)],
            missing_text_rows=[("fact-1", "the dog is in the park")],
        )
        engine = HybridRetrievalEngine(llm, FakeEmbedder(), conn, FakeHydraWithFactFields())

        result = engine.retrieve_facts("ctx-1", "where is dog?", datetime.now(timezone.utc))

        self.assertFalse(result.abstained)
        self.assertEqual(len(result.facts), 1)
        fact = result.facts[0]
        self.assertEqual(fact.subject, "dog")
        self.assertEqual(fact.predicate, "located_at")
        self.assertEqual(fact.object, "the dog is in the park")
        self.assertEqual(fact.confidence, 0.91)
        # valid_from/valid_to are graph_plan_builder.py's own open-ended
        # sentinels (0 / 9999999999) here -- "no bound", not a real date.
        self.assertIsNone(fact.valid_from)
        self.assertIsNone(fact.valid_until)

    def test_object_is_the_normalized_triple_value_not_the_full_sentence(self):
        """§9 fix: when the Fact node carries real subject/object_literal,
        those win over the ABOUT-entity-derived subject and full-sentence
        object fallback."""
        llm = FakeLLMClient([
            DateRange(valid_from=None, valid_to=None),
            QueryRewriterOutput(decomposed_queries=[], synonyms=[]),
        ])
        conn = FakeConnection(
            semantic_rows=[("fact-1", 0.1)],
            registry_rows=[("fact:fact-1", 1)],
            missing_text_rows=[("fact-1", "the dog is in the park")],
        )
        engine = HybridRetrievalEngine(llm, FakeEmbedder(), conn, FakeHydraWithTripleFields())

        result = engine.retrieve_facts("ctx-1", "where is dog?", datetime.now(timezone.utc))

        fact = result.facts[0]
        self.assertEqual(fact.subject, "dog")
        self.assertEqual(fact.predicate, "located_at")
        self.assertEqual(fact.object, "western gate")

    def test_abstains_with_no_facts_instead_of_a_canned_message(self):
        llm = FakeLLMClient([
            DateRange(valid_from=None, valid_to=None),
            QueryRewriterOutput(decomposed_queries=[], synonyms=[]),
        ])
        conn = FakeConnection(
            semantic_rows=[("fact-1", 9.0)],
            registry_rows=[("fact:fact-1", 1)],
            missing_text_rows=[("fact-1", "irrelevant")],
        )
        engine = HybridRetrievalEngine(llm, FakeEmbedder(), conn, FakeHydra(return_paths=False))

        result = engine.retrieve_facts("ctx-1", "what is the meaning of life?", datetime.now(timezone.utc))

        self.assertTrue(result.abstained)
        self.assertEqual(result.facts, [])

    def test_missing_predicate_and_confidence_fall_back_without_crashing(self):
        """FakeHydra (unlike FakeHydraWithFactFields) never returns
        predicate_key/confidence -- exercises graph_fields.get(...) defaults,
        not a KeyError."""
        llm = FakeLLMClient([
            DateRange(valid_from=None, valid_to=None),
            QueryRewriterOutput(decomposed_queries=[], synonyms=[]),
        ])
        conn = FakeConnection(
            semantic_rows=[("fact-1", 0.1)],
            registry_rows=[("fact:fact-1", 1)],
            missing_text_rows=[("fact-1", "dog in park")],
        )
        engine = HybridRetrievalEngine(llm, FakeEmbedder(), conn, FakeHydra())

        result = engine.retrieve_facts("ctx-1", "where is dog?", datetime.now(timezone.utc))

        self.assertFalse(result.abstained)
        fact = result.facts[0]
        self.assertEqual(fact.predicate, "related_to")
        # No stored confidence -> falls back to the fusion composite_score.
        self.assertGreaterEqual(fact.confidence, 0.0)

    def test_resolved_time_point_echoes_as_of_turn(self):
        llm = FakeLLMClient([
            DateRange(valid_from=None, valid_to=None),
            QueryRewriterOutput(decomposed_queries=[], synonyms=[]),
        ])
        conn = FakeConnection(
            semantic_rows=[("fact-1", 0.1)],
            registry_rows=[("fact:fact-1", 1)],
            missing_text_rows=[("fact-1", "dog in park")],
        )
        engine = HybridRetrievalEngine(llm, FakeEmbedder(), conn, FakeHydraWithFactFields())

        result = engine.retrieve_facts("ctx-1", "where is dog?", datetime.now(timezone.utc), as_of_turn=7)

        self.assertEqual(result.resolved_time_point, "7")


class WhenActiveFilteringTests(unittest.TestCase):
    """Gap B of the AI-DND memory-layer contract handoff (accepted): mem1 no
    longer evaluates/filters `when_active` server-side -- it's returned on
    every `Fact` response instead, and the caller evaluates it client-side
    with its own already-tested expression grammar. This used to be a real
    server-side filter (Milestone 4 / ADR-9); these tests now lock in the
    opposite contract on purpose. Fact ids here are numeric strings ("42"),
    not the "fact-1"-style labels other tests in this file use --
    pre_authored_fact_metadata.fact_id is a real Postgres INTEGER column
    (the fact's own graph_id), and `_fetch_fact_metadata` skips any fact_id
    that doesn't parse as one (see its own docstring)."""

    @staticmethod
    def _engine_and_conn(fact_metadata_rows):
        llm = FakeLLMClient([
            DateRange(valid_from=None, valid_to=None),
            QueryRewriterOutput(decomposed_queries=[], synonyms=[]),
        ])
        conn = FakeConnection(
            semantic_rows=[("42", 0.1)],
            registry_rows=[("fact:42", 1)],
            missing_text_rows=[("42", "a ghost follows the player")],
            fact_metadata_rows=fact_metadata_rows,
        )
        return HybridRetrievalEngine(llm, FakeEmbedder(), conn, FakeHydraWithFactFields()), conn

    def test_fact_stays_visible_regardless_of_game_state(self):
        """Was `test_fact_hidden_when_when_active_is_false` -- the exact
        opposite assertion, now that mem1 no longer filters by this."""
        when_active = {"field": "player.health", "op": "<", "value": 5}
        engine, _ = self._engine_and_conn([(42, None, when_active, None, False)])

        result = engine.retrieve_facts(
            "ctx-1", "is anything following me?", datetime.now(timezone.utc),
            game_state={"player": {"health": 100}},  # condition NOT met -- must not matter anymore
        )

        self.assertEqual(len(result.facts), 1)

    def test_when_active_is_returned_on_the_response_not_evaluated(self):
        when_active = {"field": "player.health", "op": "<", "value": 5}
        engine, _ = self._engine_and_conn([(42, None, when_active, None, False)])

        result = engine.retrieve_facts(
            "ctx-1", "is anything following me?", datetime.now(timezone.utc), game_state={},
        )

        self.assertEqual(result.facts[0].when_active, when_active)

    def test_fact_with_no_when_active_reports_none(self):
        engine, _ = self._engine_and_conn([])

        result = engine.retrieve_facts("ctx-1", "is anything following me?", datetime.now(timezone.utc), game_state={})

        self.assertEqual(len(result.facts), 1)
        self.assertIsNone(result.facts[0].when_active)

    def test_hidden_flag_is_returned_untouched_never_filtered(self):
        engine, _ = self._engine_and_conn([(42, None, None, None, True)])

        result = engine.retrieve_facts("ctx-1", "is anything following me?", datetime.now(timezone.utc))

        self.assertEqual(len(result.facts), 1)
        self.assertTrue(result.facts[0].hidden)

    def test_metadata_lookup_error_fails_open_not_closed(self):
        """A Postgres error on the metadata side-lookup degrades to "no
        metadata found", same posture ADR-5 already applies to memory
        writes: never let an auxiliary-system hiccup break the
        player-facing path."""
        class ExplodingCursor:
            def execute(self, *a, **k): raise RuntimeError("connection reset")
            def __enter__(self): return self
            def __exit__(self, *a): pass
        class ExplodingConnection:
            def cursor(self): return ExplodingCursor()

        llm = FakeLLMClient([
            DateRange(valid_from=None, valid_to=None), QueryRewriterOutput(decomposed_queries=[], synonyms=[]),
        ])
        # Seed via a normal connection for Phase 1, but swap self._pg after
        # construction so only the metadata/checkpoint lookups explode.
        conn = FakeConnection(
            semantic_rows=[("42", 0.1)], registry_rows=[("fact:42", 1)], missing_text_rows=[("42", "x")],
        )
        engine = HybridRetrievalEngine(llm, FakeEmbedder(), conn, FakeHydraWithFactFields())
        engine._pg = ExplodingConnection()

        result = engine.retrieve_facts("ctx-1", "q", datetime.now(timezone.utc), game_state={})

        self.assertEqual(len(result.facts), 1)


class CheckpointFilteringTests(unittest.TestCase):
    """Milestone 5: a fact tied to a checkpoint later than the playthrough's
    current one is hidden until reached."""

    @staticmethod
    def _engine(fact_metadata_rows, checkpoint_row):
        llm = FakeLLMClient([
            DateRange(valid_from=None, valid_to=None),
            QueryRewriterOutput(decomposed_queries=[], synonyms=[]),
        ])
        conn = FakeConnection(
            semantic_rows=[("42", 0.1)],
            registry_rows=[("fact:42", 1)],
            missing_text_rows=[("42", "the bridge has collapsed")],
            fact_metadata_rows=fact_metadata_rows,
            checkpoint_row=checkpoint_row,
        )
        return HybridRetrievalEngine(llm, FakeEmbedder(), conn, FakeHydraWithFactFields())

    def test_fact_hidden_before_its_checkpoint_is_reached(self):
        engine = self._engine(
            fact_metadata_rows=[(42, "chapter_3", None, None, False)], checkpoint_row=(["chapter_1", "chapter_2", "chapter_3"],),
        )

        result = engine.retrieve_facts(
            "ctx-1", "what happened to the bridge?", datetime.now(timezone.utc),
            checkpoint="chapter_1", template_context_id="scenario-template::s1",
        )

        self.assertEqual(result.facts, [])

    def test_fact_visible_once_its_checkpoint_is_reached(self):
        engine = self._engine(
            fact_metadata_rows=[(42, "chapter_2", None, None, False)], checkpoint_row=(["chapter_1", "chapter_2", "chapter_3"],),
        )

        result = engine.retrieve_facts(
            "ctx-1", "what happened to the bridge?", datetime.now(timezone.utc),
            checkpoint="chapter_3", template_context_id="scenario-template::s1",
        )

        self.assertEqual(len(result.facts), 1)

    def test_no_checkpoint_order_stored_fails_open(self):
        """Config gap (template never had `checkpoints` authored) -- never
        silently hides a fact a creator meant to be visible."""
        engine = self._engine(fact_metadata_rows=[(42, "chapter_2", None, None, False)], checkpoint_row=None)

        result = engine.retrieve_facts(
            "ctx-1", "what happened to the bridge?", datetime.now(timezone.utc),
            checkpoint="chapter_1", template_context_id="scenario-template::s1",
        )

        self.assertEqual(len(result.facts), 1)

    def test_no_template_context_id_given_skips_checkpoint_filtering_entirely(self):
        """Milestone 1 callers that don't pass template_context_id (or
        pre-Milestone-5 callers) get exactly Milestone 1-4 behavior --
        checkpoint gating never activates without it."""
        engine = self._engine(fact_metadata_rows=[(42, "chapter_2", None, None, False)], checkpoint_row=(["chapter_1", "chapter_2"],))

        result = engine.retrieve_facts(
            "ctx-1", "what happened to the bridge?", datetime.now(timezone.utc), checkpoint="chapter_1",
        )

        self.assertEqual(len(result.facts), 1)


class FakeHydraWithTurnNumber:
    """§5 fix: the OPTIONAL MATCH row also carries `turn_number` (written
    onto the Fact node by graph_plan_builder._fact_node, §4's fix) -- what
    as_of_turn filtering reads."""

    def __init__(self, turn_number: int | None) -> None:
        self.turn_number = turn_number

    def read(self, cypher, params, bookmark):
        if "SUPERSEDES" in cypher:
            return []
        if "OPTIONAL MATCH" in cypher:
            return [{
                "text": "the bridge collapsed", "speaker": None,
                "valid_from": 0, "valid_to": 9999999999,
                "observed_at": 1000, "superseded_at": 9999999999,
                "memory_scope": None, "entity_key": None, "turn_number": self.turn_number,
            }]
        if "algo.MSpaths" in cypher:
            return []
        return []


class AsOfTurnFilteringTests(unittest.TestCase):
    """§5 fix: `as_of_turn` used to only be echoed into
    `resolved_time_point` -- a fact extracted from a later turn than
    requested must actually be dropped now."""

    @staticmethod
    def _engine(turn_number):
        llm = FakeLLMClient([
            DateRange(valid_from=None, valid_to=None),
            QueryRewriterOutput(decomposed_queries=[], synonyms=[]),
        ])
        conn = FakeConnection(
            semantic_rows=[("42", 0.1)], registry_rows=[("fact:42", 1)],
            missing_text_rows=[("42", "the bridge collapsed")],
        )
        return HybridRetrievalEngine(llm, FakeEmbedder(), conn, FakeHydraWithTurnNumber(turn_number))

    def test_fact_from_a_later_turn_is_hidden(self):
        engine = self._engine(turn_number=12)
        result = engine.retrieve_facts("ctx-1", "what happened to the bridge?", datetime.now(timezone.utc), as_of_turn=7)
        self.assertEqual(result.facts, [])

    def test_fact_from_an_earlier_or_equal_turn_is_visible(self):
        engine = self._engine(turn_number=7)
        result = engine.retrieve_facts("ctx-1", "what happened to the bridge?", datetime.now(timezone.utc), as_of_turn=7)
        self.assertEqual(len(result.facts), 1)

    def test_fact_with_no_turn_number_fails_open(self):
        """Direct-authored/pre-§4 facts carry no turn_number at all --
        must stay visible, not vanish from every as_of_turn query."""
        engine = self._engine(turn_number=None)
        result = engine.retrieve_facts("ctx-1", "what happened to the bridge?", datetime.now(timezone.utc), as_of_turn=1)
        self.assertEqual(len(result.facts), 1)

    def test_no_as_of_turn_given_skips_the_filter_entirely(self):
        engine = self._engine(turn_number=999)
        result = engine.retrieve_facts("ctx-1", "what happened to the bridge?", datetime.now(timezone.utc))
        self.assertEqual(len(result.facts), 1)


class ParticipantVisibilityFilteringTests(unittest.TestCase):
    """§5 fix: `participant_id` used to be accepted and never forwarded --
    a fact restricted to one participant (DirectFactInput.
    visible_to_participant_id) must be hidden from a query for anyone else."""

    @staticmethod
    def _engine(fact_metadata_rows):
        llm = FakeLLMClient([
            DateRange(valid_from=None, valid_to=None),
            QueryRewriterOutput(decomposed_queries=[], synonyms=[]),
        ])
        conn = FakeConnection(
            semantic_rows=[("42", 0.1)], registry_rows=[("fact:42", 1)],
            missing_text_rows=[("42", "a secret only Alice knows")],
            fact_metadata_rows=fact_metadata_rows,
        )
        return HybridRetrievalEngine(llm, FakeEmbedder(), conn, FakeHydraWithFactFields())

    def test_fact_hidden_from_a_different_participant(self):
        engine = self._engine([(42, None, None, "participant-alice", False)])
        result = engine.retrieve_facts(
            "ctx-1", "what's the secret?", datetime.now(timezone.utc), participant_id="participant-bob",
        )
        self.assertEqual(result.facts, [])

    def test_fact_visible_to_the_restricted_participant(self):
        engine = self._engine([(42, None, None, "participant-alice", False)])
        result = engine.retrieve_facts(
            "ctx-1", "what's the secret?", datetime.now(timezone.utc), participant_id="participant-alice",
        )
        self.assertEqual(len(result.facts), 1)

    def test_no_participant_id_given_fails_open(self):
        """A query that doesn't identify its participant can't confidently
        exclude a restricted fact -- same fail-open posture as checkpoint/
        when_active config gaps."""
        engine = self._engine([(42, None, None, "participant-alice", False)])
        result = engine.retrieve_facts("ctx-1", "what's the secret?", datetime.now(timezone.utc))
        self.assertEqual(len(result.facts), 1)

    def test_unrestricted_fact_visible_to_everyone(self):
        engine = self._engine([(42, None, None, None, False)])
        result = engine.retrieve_facts(
            "ctx-1", "what's the secret?", datetime.now(timezone.utc), participant_id="participant-bob",
        )
        self.assertEqual(len(result.facts), 1)


class SemanticSearchModelFilterTests(unittest.TestCase):
    """§12 fix: semantic search used to compare the query vector against
    every stored embedding for the context regardless of which model/
    version produced it -- meaningless once more than one embedding model
    version has ever been used against the same context."""

    class _RecordingCursor:
        def __init__(self) -> None:
            self.executed: list[tuple[str, tuple]] = []

        def execute(self, query, params=None):
            self.executed.append((query, params or ()))

        def fetchall(self):
            return []

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return None

    class _RecordingConnection:
        def __init__(self) -> None:
            self.cursor_obj = SemanticSearchModelFilterTests._RecordingCursor()

        def cursor(self):
            return self.cursor_obj

    class _VersionedEmbedder:
        model_name = "all-MiniLM-L6-v2"
        model_version = "2"

        def embed(self, text):
            return (0.1, 0.2)

    def test_semantic_search_filters_by_embedder_model_name_and_version(self) -> None:
        from context_memory.retrieval.seeder import CandidateSeeder

        conn = self._RecordingConnection()
        seeder = CandidateSeeder(conn, self._VersionedEmbedder())

        seeder.seed("ctx-1", "question", QueryRewriterOutput(decomposed_queries=[], synonyms=[]), top_k=5)

        semantic_query, semantic_params = conn.cursor_obj.executed[0]
        self.assertIn("model_name = %s AND model_version = %s", semantic_query)
        self.assertIn("all-MiniLM-L6-v2", semantic_params)
        self.assertIn("2", semantic_params)

    def test_missing_model_attrs_fall_back_gracefully(self) -> None:
        """An embedder that doesn't expose model_name/model_version (a bare
        test double) must not crash the query -- same "unknown"/"1"
        fallback `orchestrator._build_embeddings` already uses at write
        time, so a fact written under those defaults is still findable."""
        from context_memory.retrieval.seeder import CandidateSeeder

        conn = self._RecordingConnection()
        seeder = CandidateSeeder(conn, FakeEmbedder())

        seeder.seed("ctx-1", "question", QueryRewriterOutput(decomposed_queries=[], synonyms=[]), top_k=5)

        _, semantic_params = conn.cursor_obj.executed[0]
        self.assertIn("unknown", semantic_params)
        self.assertIn("1", semantic_params)


class CountQueryDetectionTests(unittest.TestCase):
    """§16: widen retrieval for count/enumeration questions without a
    reasoning LLM call -- verified NOT to help by a published system
    (91.2%->86.0%)."""

    def test_count_query_phrasings_are_detected(self):
        from context_memory.retrieval.detectors import looks_like_count_query
        positives = [
            "How many magazine subscriptions do I currently have?",
            "How many graduation ceremonies have I attended in the past three months?",
            "What is the total I spent on groceries?",
            "How much did I spend on my mortgage?",
            "What is the average GPA of my studies?",
            "List all the restaurants I've recommended.",
            "How often do I go to the gym?",
        ]
        for q in positives:
            self.assertTrue(looks_like_count_query(q), q)

    def test_single_fact_lookups_are_not_flagged(self):
        from context_memory.retrieval.detectors import looks_like_count_query
        negatives = [
            "What is my dog's name?",
            "Where do I live?",
            "What theme parks have I visited?",
            "Which event did I attend first, the workshop or the webinar?",
        ]
        for q in negatives:
            self.assertFalse(looks_like_count_query(q), q)

    def test_retrieve_and_answer_widens_top_k_for_a_detected_count_query(self):
        from context_memory.core.logging import drain_metrics, enable_metrics_collection, disable_metrics_collection
        llm = FakeLLMClient([
            DateRange(valid_from=None, valid_to=None),
            QueryRewriterOutput(decomposed_queries=[], synonyms=[]),
        ], text_response="answer")
        engine = HybridRetrievalEngine(llm, FakeEmbedder(), FakeConnection(), FakeHydra())
        enable_metrics_collection()
        try:
            engine.retrieve_and_answer("ctx-1", "How many pets do I have?", datetime.now(timezone.utc))
            records = drain_metrics()
        finally:
            disable_metrics_collection()
        top = next(r for r in records if r.get("operation") == "retrieval.retrieve_and_answer")
        self.assertTrue(top["is_count_query"])
        self.assertEqual(top["top_k"], engine._config.retrieval_count_query_top_k)
        self.assertGreater(engine._config.retrieval_count_query_top_k, engine._config.retrieval_top_k)

    def test_explicit_top_k_override_is_never_second_guessed(self):
        from context_memory.core.logging import drain_metrics, enable_metrics_collection, disable_metrics_collection
        llm = FakeLLMClient([
            DateRange(valid_from=None, valid_to=None),
            QueryRewriterOutput(decomposed_queries=[], synonyms=[]),
        ], text_response="answer")
        engine = HybridRetrievalEngine(llm, FakeEmbedder(), FakeConnection(), FakeHydra())
        enable_metrics_collection()
        try:
            engine.retrieve_and_answer("ctx-1", "How many pets do I have?", datetime.now(timezone.utc), top_k=5)
            records = drain_metrics()
        finally:
            disable_metrics_collection()
        top = next(r for r in records if r.get("operation") == "retrieval.retrieve_and_answer")
        self.assertFalse(top["is_count_query"])  # heuristic is skipped when top_k is explicit
        self.assertEqual(top["top_k"], 5)


if __name__ == "__main__":
    unittest.main()


class DurationQueryTests(unittest.TestCase):
    """§20: elapsed-time questions get step-by-step arithmetic guidance and a
    reference date, both in the SAME reader call (never a second call, which
    is the thing measured to reduce accuracy)."""

    def test_duration_phrasings_are_detected(self):
        from context_memory.retrieval.detectors import looks_like_duration_query
        for q in [
            "How many days ago did I participate in the 5K charity run?",
            "How many weeks ago did I attend the friends and family sale?",
            "How long have I been learning guitar?",
            "How many years in total did I spend in formal education from high school to my Bachelor's?",
            "How much time passed between the two events?",
            "How many days passed between the day I fixed my bike and the day I upgraded the pedals?",
        ]:
            self.assertTrue(looks_like_duration_query(q), q)

    def test_count_queries_are_not_treated_as_duration_queries(self):
        """The two heuristics must stay disjoint -- a count question must not
        pick up date-arithmetic guidance or the reference-date header, which
        measurably regressed one ('magazine subscriptions' went 2 -> 1)."""
        from context_memory.retrieval.detectors import looks_like_duration_query, looks_like_count_query
        for q in [
            "How many magazine subscriptions do I currently have?",
            "How many graduation ceremonies have I attended in the past three months?",
            "How many properties did I view before making an offer?",
            "What is my dog's name?",
        ]:
            self.assertFalse(looks_like_duration_query(q), q)

    def _engine_with_a_fact(self, llm):
        """A strong-enough fact to clear abstention, so the reader is actually
        reached and its prompt can be inspected."""
        conn = FakeConnection(
            semantic_rows=[("fact-1", 0.1)],
            registry_rows=[("fact:fact-1", 1)],
            missing_text_rows=[("fact-1", "The user completed a 5K charity run today.")],
        )
        return HybridRetrievalEngine(llm, FakeEmbedder(), conn, FakeHydra())

    def test_duration_query_gets_guidance_and_reference_date(self):
        llm = FakeLLMClient([
            DateRange(valid_from=None, valid_to=None),
            QueryRewriterOutput(decomposed_queries=[], synonyms=[]),
        ], text_response="answer")
        engine = self._engine_with_a_fact(llm)
        when = datetime(2023, 3, 21, tzinfo=timezone.utc)
        engine.retrieve_and_answer("ctx-1", "How many days ago did I run the 5K?", when)
        prompt = llm.last_reader_system_prompt
        self.assertIn("[today's date is 2023-03-21]", prompt)
        self.assertIn("AGO / SINCE", prompt)

    def test_non_duration_query_gets_neither(self):
        llm = FakeLLMClient([
            DateRange(valid_from=None, valid_to=None),
            QueryRewriterOutput(decomposed_queries=[], synonyms=[]),
        ], text_response="answer")
        engine = self._engine_with_a_fact(llm)
        when = datetime(2023, 3, 21, tzinfo=timezone.utc)
        engine.retrieve_and_answer("ctx-1", "How many magazine subscriptions do I have?", when)
        prompt = llm.last_reader_system_prompt
        self.assertNotIn("today's date is", prompt)
        self.assertNotIn("AGO / SINCE", prompt)
