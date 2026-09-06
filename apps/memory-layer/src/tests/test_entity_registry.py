from __future__ import annotations

import sys
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from context_memory.ingestion.fakes import DeterministicEntityResolutionModel, InMemoryGraphIdAllocator
from context_memory.ingestion.entity_registry import EntityRegistry
from context_memory.core.resolution import EntityProfile, ResolutionStatus, canonicalize_entity_surface


class EntityResolutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = EntityRegistry(InMemoryGraphIdAllocator())
        self.max = EntityProfile(7, "context-a", "Max", "pet", ("my dog", "the golden retriever"))
        self.registry.register(self.max)

    def test_unicode_canonicalization_is_stable(self) -> None:
        self.assertEqual(canonicalize_entity_surface("  CAFÉ\u00a0Dog "), "café dog")

    def test_exact_canonical_and_alias_do_not_call_model(self) -> None:
        model = DeterministicEntityResolutionModel()
        canonical = self.registry.resolve(context_id="context-a", surface=" max ", model=model)
        alias = self.registry.resolve(context_id="context-a", surface="MY DOG", model=model)
        self.assertEqual(canonical.status, ResolutionStatus.EXACT_CANONICAL)
        self.assertEqual(alias.status, ResolutionStatus.EXACT_ALIAS)
        self.assertEqual(model.calls, [])

    def test_context_isolation_creates_new_entity(self) -> None:
        resolution = self.registry.resolve(context_id="context-b", surface="Max")
        self.assertEqual(resolution.status, ResolutionStatus.NEW_ENTITY)
        self.assertNotEqual(resolution.entity.graph_id, self.max.graph_id)

    def test_bounded_model_resolves_non_exact_reference(self) -> None:
        model = DeterministicEntityResolutionModel({"him": 7})
        result = self.registry.resolve(
            context_id="context-a", surface="him", candidate_ids=(7,), model=model
        )
        self.assertEqual((result.status, result.entity.graph_id), (ResolutionStatus.MODEL_RESOLVED, 7))
        self.assertEqual(model.calls, [("context-a", "him", (7,))])

    def test_model_cannot_select_outside_bounded_candidates(self) -> None:
        model = DeterministicEntityResolutionModel({"him": 999})
        result = self.registry.resolve(
            context_id="context-a", surface="him", candidate_ids=(7,), model=model
        )
        self.assertEqual(result.status, ResolutionStatus.UNRESOLVED)

    def test_in_context_index_isolates_by_context_not_a_global_scan(self) -> None:
        """`_in_context` used to scan every entity this registry has ever
        seen, across every context, filtering by context_id after the
        fact -- measured live as a real, compounding slowdown over a long
        conversation (docs/fixes_and_evaluation_findings.md §6). This
        checks the indexed version gives the identical membership a full
        scan would, for both the context that has entities and one that
        doesn't."""
        self.registry.register(EntityProfile(8, "context-b", "Rex", "pet"))
        self.registry.register(EntityProfile(9, "context-a", "Fido", "pet"))
        in_a = {p.graph_id for p in self.registry._in_context("context-a")}
        in_b = {p.graph_id for p in self.registry._in_context("context-b")}
        in_c = {p.graph_id for p in self.registry._in_context("context-c")}
        self.assertEqual(in_a, {7, 9})  # self.max (7) + Fido (9), not Rex
        self.assertEqual(in_b, {8})
        self.assertEqual(in_c, set())  # never registered, empty, not an error

    def test_idempotent_reregistration_does_not_duplicate_the_index_entry(self) -> None:
        """Replaying `register()` for the same graph_id with an identical
        payload (the documented idempotent-replay contract, orchestrator.py's
        module docstring) must not append a second copy of that id to the
        per-context index."""
        self.registry.register(self.max)  # same profile, same graph_id -- a legal no-op replay
        self.assertEqual(self.registry._profile_ids_by_context["context-a"].count(7), 1)

    def test_grown_alias_is_visible_via_the_index_without_reindexing(self) -> None:
        """`_grow_alias` replaces the `self._profiles[graph_id]` entry in
        place -- the index only needs to track membership, not content, so
        a later `_in_context` call must see the grown aliases without any
        extra bookkeeping."""
        model = DeterministicEntityResolutionModel({"Maxie": 7})
        self.registry.resolve(context_id="context-a", surface="Maxie", candidate_ids=(7,), model=model)
        (profile,) = [p for p in self.registry._in_context("context-a") if p.graph_id == 7]
        self.assertIn("maxie", profile.aliases)

    def test_ambiguous_alias_without_model_is_unresolved(self) -> None:
        self.registry.register(EntityProfile(8, "context-a", "Rex", "pet", ("my dog",)))
        result = self.registry.resolve(context_id="context-a", surface="my dog")
        self.assertEqual(result.status, ResolutionStatus.UNRESOLVED)

class _FakeSentenceModel:
    """Character-frequency vector, L2-normalized -- crude, but similar
    strings land close in cosine terms and dissimilar ones don't, which is
    all these tests need (verified: 'sherlock holmes' vs 'holmes' -> 0.90
    cosine, vs 'mr. holmes' -> 0.81, vs 'sherlock' -> 0.92, all comfortably
    above EntityNameIndex's 0.75 default; 'david smith' vs 'david smith jr'
    -> 0.92, vs an unrelated name -> 0.38). Same pattern
    `ingestion.fakes.DeterministicEmbedder` uses elsewhere in this suite --
    stays fast and offline instead of downloading/loading a real model just
    to prove embedding-based candidate generation works."""

    def encode(self, text: str, normalize_embeddings: bool = True):
        import numpy as np

        vec = np.zeros(32, dtype=np.float32)
        for ch in text.lower():
            vec[ord(ch) % 32] += 1.0
        norm = np.linalg.norm(vec)
        return vec / norm if norm > 0 else vec

class DuplicateEntityFixTests(unittest.TestCase):
    """The Dave/David gap: confirmed live (see
    docs/fixes_and_evaluation_findings.md §4) that with no `name_index`, a
    non-exact surface's candidate shortlist was always empty, so the LLM
    disambiguator -- even a "perfect" one that would correctly say two
    surfaces match -- was never consulted, and a duplicate entity got
    created silently every time. These tests reproduce that exact scenario
    against the fix (nickname table + embedding blocking,
    `entity_blocking.py`/`ingestion.entity_name_index.EntityNameIndex`) and lock in
    that the fix actually closes it, not just that the pieces exist in
    isolation. `name_index` uses a deterministic fake model (see
    `_FakeSentenceModel`), matching how production always wires a real one
    (`create_pipeline`/`get_engine`, §4.6) -- without it, embedding-based
    cases like Sherlock Holmes/Holmes have no path to the model at all,
    same root cause §4.1 originally diagnosed.
    """

    def setUp(self) -> None:
        from context_memory.ingestion.entity_name_index import EntityNameIndex

        self.registry = EntityRegistry(InMemoryGraphIdAllocator(), name_index=EntityNameIndex(model=_FakeSentenceModel()))

    def test_nickname_style_surface_now_reaches_the_model_and_resolves(self) -> None:
        first = self.registry.resolve(context_id="ctx", surface="Dave", entity_type="person")
        self.assertEqual(first.status, ResolutionStatus.NEW_ENTITY)

        model = DeterministicEntityResolutionModel({"David": first.entity.graph_id})
        second = self.registry.resolve(context_id="ctx", surface="David", entity_type="person", model=model)

        # Confirmed reachable this time -- the whole bug was that this call never happened.
        self.assertEqual(len(model.calls), 1)
        self.assertEqual(second.status, ResolutionStatus.MODEL_RESOLVED)
        self.assertEqual(second.entity.graph_id, first.entity.graph_id)

    def test_sherlock_holmes_from_the_microsoft_graphrag_issue_resolves_to_one_entity(self) -> None:
        """The exact case Microsoft GraphRAG's own dedup issue (#401) left
        unresolved."""
        first = self.registry.resolve(context_id="ctx", surface="Sherlock Holmes", entity_type="person")
        model = DeterministicEntityResolutionModel({"Holmes": first.entity.graph_id, "Mr. Holmes": first.entity.graph_id})

        second = self.registry.resolve(context_id="ctx", surface="Holmes", entity_type="person", model=model)
        self.assertEqual(second.entity.graph_id, first.entity.graph_id)

    def test_genuinely_different_entity_still_creates_new_entity(self) -> None:
        """Blocking must not over-merge -- a clearly different short name
        should still end up as its own entity, not get force-matched."""
        first = self.registry.resolve(context_id="ctx", surface="Dave", entity_type="person")
        model = DeterministicEntityResolutionModel({})  # abstains on everything -- correct behavior for "Dan"
        second = self.registry.resolve(context_id="ctx", surface="Dan", entity_type="person", model=model)
        # 'dave'/'dan' scores below the blocking threshold (see
        # entity_blocking.py's calibration) so this never even reaches the
        # model as a candidate -- confirmed by both the outcome and the fact
        # the model was never asked to distinguish them.
        self.assertEqual(model.calls, [])
        self.assertEqual(second.status, ResolutionStatus.NEW_ENTITY)
        self.assertNotEqual(second.entity.graph_id, first.entity.graph_id)

    def test_bob_robert_root_different_nickname_now_reaches_the_model(self) -> None:
        """The gap the trigram/embedding blocking couldn't close on its own
        ('bob' vs 'robert' shares zero character trigrams) -- covered by
        the curated nickname table (`entity_blocking.NICKNAME_GROUPS`)
        added afterward specifically for this case."""
        first = self.registry.resolve(context_id="ctx", surface="Robert", entity_type="person")
        model = DeterministicEntityResolutionModel({"Bob": first.entity.graph_id})
        second = self.registry.resolve(context_id="ctx", surface="Bob", entity_type="person", model=model)
        self.assertEqual(len(model.calls), 1)
        self.assertEqual(second.status, ResolutionStatus.MODEL_RESOLVED)
        self.assertEqual(second.entity.graph_id, first.entity.graph_id)

    def test_model_resolved_grows_the_alias_so_next_time_is_a_direct_hit(self) -> None:
        first = self.registry.resolve(context_id="ctx", surface="Dave", entity_type="person")
        model = DeterministicEntityResolutionModel({"David": first.entity.graph_id})
        second = self.registry.resolve(context_id="ctx", surface="David", entity_type="person", model=model)
        self.assertIn("david", second.entity.aliases)  # canonicalized form recorded

        third = self.registry.resolve(context_id="ctx", surface="David", entity_type="person", model=model)
        self.assertEqual(third.status, ResolutionStatus.EXACT_ALIAS)
        self.assertEqual(len(model.calls), 1)  # still just the one call from `second` -- `third` never needed the model

    def test_name_index_lets_a_later_turn_find_an_entity_created_by_an_earlier_turn(self) -> None:
        """Without `EntityRegistry._index_profile` keeping the name_index in
        sync, an entity created mid-run would never appear in
        `find_candidates` results for a later turn in the same run."""
        first = self.registry.resolve(context_id="ctx", surface="David Smith", entity_type="person")
        model = DeterministicEntityResolutionModel({"David Smith Jr": first.entity.graph_id})

        # A close-enough repeat surface should surface the earlier entity as
        # a candidate via the (now-populated) name_index, reaching the model.
        second = self.registry.resolve(context_id="ctx", surface="David Smith Jr", entity_type="person", model=model)
        self.assertEqual(len(model.calls), 1)
        self.assertEqual(second.entity.graph_id, first.entity.graph_id)

class _SlowRecordingModel:
    """Records every call and sleeps a fixed duration per call -- lets a
    test prove calls actually ran concurrently (wall time << sum of sleeps)
    instead of just trusting the implementation."""

    def __init__(self, selections: dict[str, int | None], delay_s: float = 0.15) -> None:
        self._selections = selections
        self._delay_s = delay_s
        self.calls: list[str] = []
        self._lock = threading.Lock()

    def resolve_entity(self, *, context_id: str, surface: str, candidates) -> int | None:
        with self._lock:
            self.calls.append(surface)
        time.sleep(self._delay_s)
        return self._selections.get(surface)

class ResolveManyTests(unittest.TestCase):
    """`EntityRegistry.resolve_many` -- parallelizes the LLM disambiguation
    calls for several mentions from one chunk, keeping candidate generation
    and every registry mutation serial. See
    docs/fixes_and_evaluation_findings.md §4.7."""

    def setUp(self) -> None:
        self.registry = EntityRegistry(InMemoryGraphIdAllocator())

    def test_empty_mentions_returns_empty_list(self) -> None:
        self.assertEqual(self.registry.resolve_many("ctx", []), [])

    def test_all_exact_matches_never_touch_the_model(self) -> None:
        self.registry.register(EntityProfile(7, "ctx", "max", "pet", ("my dog",)))
        model = DeterministicEntityResolutionModel()
        results = self.registry.resolve_many("ctx", [("Max", "pet"), ("my dog", "pet")], model=model)
        self.assertEqual([r.graph_id for r in results], [7, 7])
        self.assertEqual(model.calls, [])

    def test_mixed_exact_and_model_needed_resolve_correctly(self) -> None:
        self.registry.register(EntityProfile(7, "ctx", "max", "pet"))
        model = DeterministicEntityResolutionModel({"Robert": None})  # abstains -- genuinely new
        results = self.registry.resolve_many("ctx", [("Max", "pet"), ("Robert", "person")], model=model)
        self.assertEqual(results[0].graph_id, 7)  # exact match, no call
        self.assertEqual(results[1].canonical_name, "robert")  # new entity minted
        self.assertNotEqual(results[1].graph_id, 7)

    def test_duplicate_identical_surface_in_one_batch_resolves_once(self) -> None:
        self.registry.register(EntityProfile(7, "ctx", "robert", "person"))
        model = DeterministicEntityResolutionModel({"Bob": 7})
        results = self.registry.resolve_many("ctx", [("Bob", "person"), ("Bob", "person"), ("Bob", "person")], model=model)
        self.assertEqual([r.graph_id for r in results], [7, 7, 7])
        self.assertEqual(len(model.calls), 1)  # one call for the repeated surface, not three

    def test_new_entities_get_distinct_graph_ids(self) -> None:
        model = DeterministicEntityResolutionModel({})
        results = self.registry.resolve_many("ctx", [("Alice", "person"), ("Zed", "person")], model=model)
        self.assertNotEqual(results[0].graph_id, results[1].graph_id)

    def test_results_preserve_input_order_and_length(self) -> None:
        # graph_id 999 deliberately out of the allocator's own 0-based
        # counting range -- registering an entity directly (bypassing the
        # allocator, same as every other test in this file does) leaves the
        # allocator unaware id 1 is taken, so a low hand-picked id here can
        # collide with whatever this test's own NEW_ENTITY allocations get
        # assigned next.
        self.registry.register(EntityProfile(999, "ctx", "alpha", "other"))
        model = DeterministicEntityResolutionModel({})
        mentions = [("Alpha", "other"), ("Beta", "other"), ("Alpha", "other"), ("Gamma", "other")]
        results = self.registry.resolve_many("ctx", mentions, model=model)
        self.assertEqual(len(results), 4)
        self.assertEqual(results[0].graph_id, 999)
        self.assertEqual(results[2].graph_id, 999)  # second "Alpha" matches the first, same position semantics
        self.assertNotEqual(results[1].graph_id, results[3].graph_id)  # Beta and Gamma got distinct new ids

    def test_calls_actually_run_concurrently(self) -> None:
        """The whole point of resolve_many -- real wall-clock proof, not
        just trusting the code path was taken. Pre-registers each surface's
        formal-name counterpart so all four mentions genuinely produce a
        non-empty shortlist (via the nickname table) and reach the model --
        with nothing pre-registered, all four would resolve as brand-new
        entities with an empty shortlist and never call the model at all."""
        self.registry.register(EntityProfile(1, "ctx", "robert", "person"))
        self.registry.register(EntityProfile(2, "ctx", "william", "person"))
        self.registry.register(EntityProfile(3, "ctx", "richard", "person"))
        self.registry.register(EntityProfile(4, "ctx", "margaret", "person"))
        model = _SlowRecordingModel({"Bob": 1, "Bill": 2, "Dick": 3, "Peggy": 4}, delay_s=0.15)
        mentions = [("Bob", "person"), ("Bill", "person"), ("Dick", "person"), ("Peggy", "person")]
        t0 = time.perf_counter()
        results = self.registry.resolve_many("ctx", mentions, model=model, max_workers=4)
        elapsed = time.perf_counter() - t0
        self.assertEqual(len(model.calls), 4)
        self.assertEqual([r.graph_id for r in results], [1, 2, 3, 4])
        # Sequential would take >= 4*0.15=0.6s; concurrent should be close to one delay, not four.
        self.assertLess(elapsed, 0.35, f"expected concurrent calls to overlap, took {elapsed:.2f}s")

    def test_two_distinct_surfaces_in_one_batch_do_not_see_each_other_as_candidates(self) -> None:
        """The one documented tradeoff: within a single resolve_many call,
        a genuinely-equivalent nickname pair introduced for the first time
        together does NOT get merged with each other -- both mint new,
        distinct entities, since neither's candidate shortlist (generated
        before either mutates the registry) can see the other."""
        model = DeterministicEntityResolutionModel({"Robert": None, "Bob": None})
        results = self.registry.resolve_many("ctx", [("Robert", "person"), ("Bob", "person")], model=model)
        self.assertIsNotNone(results[0])
        self.assertIsNotNone(results[1])
        self.assertNotEqual(results[0].graph_id, results[1].graph_id)  # NOT merged, even though genuinely equivalent

        # The split is now permanent for THESE two exact surfaces -- a later
        # "Bob" exact-matches its OWN already-registered entity, not
        # "Robert"'s; exact match takes priority over blocking, so it never
        # gets a chance to re-ask the model about the two of them.
        third = self.registry.resolve(context_id="ctx", surface="Bob", model=DeterministicEntityResolutionModel({"Bob": results[0].graph_id}))
        self.assertEqual(third.status, ResolutionStatus.EXACT_CANONICAL)  # "bob" is its OWN canonical name, not an alias
        self.assertEqual(third.entity.graph_id, results[1].graph_id)  # its own entity, still not Robert's

        # What DOES still work: a third, different surface in the same
        # nickname group ("Bobby" -- robert/bob/bobby/rob/robbie) sees BOTH
        # split entities as candidates and the model can correctly link it
        # to one of them -- the two entities never merge with each other,
        # but new references aren't stuck being permanently ambiguous either.
        bobby_model = DeterministicEntityResolutionModel({"Bobby": results[0].graph_id})
        bobby = self.registry.resolve(context_id="ctx", surface="Bobby", model=bobby_model)
        self.assertEqual(bobby.status, ResolutionStatus.MODEL_RESOLVED)
        self.assertEqual(len(bobby_model.calls), 1)
        candidates_offered = bobby_model.calls[0][2]
        self.assertIn(results[0].graph_id, candidates_offered)
        self.assertIn(results[1].graph_id, candidates_offered)

class _BatchRecordingEntityModel:
    """Implements resolve_entities; records batch composition so tests can
    assert on call count and index mapping."""

    def __init__(self, selections_by_surface: dict[str, int | None] | None = None) -> None:
        self._selections = selections_by_surface or {}
        self.batch_calls: list[list[str]] = []
        self.pairwise_calls: list[str] = []

    def resolve_entity(self, *, context_id, surface, candidates):
        self.pairwise_calls.append(surface)
        return self._selections.get(surface)

    def resolve_entities(self, *, context_id, mentions):
        self.batch_calls.append([surface for surface, _ in mentions])
        return {i: self._selections.get(surface) for i, (surface, _) in enumerate(mentions)}

class BatchedEntityResolutionTests(unittest.TestCase):
    """§14: one call for several mentions instead of one per mention."""

    def test_multiple_ambiguous_mentions_become_one_batched_call(self) -> None:
        registry = EntityRegistry(InMemoryGraphIdAllocator())
        registry.register(EntityProfile(7, "ctx", "robert", "person"))
        registry.register(EntityProfile(8, "ctx", "bobby", "person"))
        model = _BatchRecordingEntityModel({"Bob": 7, "Rob": 8})
        results = registry.resolve_many("ctx", [("Bob", "person"), ("Rob", "person")], model=model)
        self.assertEqual(len(model.batch_calls), 1)
        self.assertEqual(model.pairwise_calls, [])
        self.assertEqual([r.graph_id if r else None for r in results], [7, 8])

    def test_batch_disabled_falls_back_to_pairwise(self) -> None:
        registry = EntityRegistry(InMemoryGraphIdAllocator(), batch_enabled=False)
        registry.register(EntityProfile(7, "ctx", "robert", "person"))
        registry.register(EntityProfile(8, "ctx", "bobby", "person"))
        model = _BatchRecordingEntityModel({"Bob": 7, "Rob": 8})
        registry.resolve_many("ctx", [("Bob", "person"), ("Rob", "person")], model=model)
        self.assertEqual(model.batch_calls, [])
        self.assertEqual(sorted(model.pairwise_calls), ["Bob", "Rob"])

    def test_model_without_resolve_entities_falls_back_to_pairwise(self) -> None:
        registry = EntityRegistry(InMemoryGraphIdAllocator())
        registry.register(EntityProfile(7, "ctx", "robert", "person"))
        model = DeterministicEntityResolutionModel({"Bob": 7})  # no resolve_entities
        results = registry.resolve_many("ctx", [("Bob", "person")], model=model)
        self.assertEqual(results[0].graph_id, 7)

    def test_missing_index_in_batch_response_resolves_to_none_not_a_crash(self) -> None:
        """Second mention is ambiguous, not exact -- two profiles share the
        same string "sam", so `_exact_match` abstains and it genuinely
        reaches the model via `_ambiguous_exact_matches`'s shortlist seed."""
        class _PartialModel(_BatchRecordingEntityModel):
            def resolve_entities(self, *, context_id, mentions):
                self.batch_calls.append([s for s, _ in mentions])
                return {0: 7}  # omits index 1

        registry = EntityRegistry(InMemoryGraphIdAllocator())
        registry.register(EntityProfile(7, "ctx", "robert", "person"))
        registry.register(EntityProfile(20, "ctx", "sam", "person"))
        registry.register(EntityProfile(21, "ctx", "sam", "person"))
        model = _PartialModel()
        results = registry.resolve_many("ctx", [("Bob", "person"), ("Sam", "person")], model=model)
        self.assertEqual(len(model.batch_calls), 1)
        self.assertEqual(results[0].graph_id, 7)
        # index 1 got no answer -> treated as unresolved, same contract as
        # resolve_entity() returning None -- neither ambiguous candidate wins
        self.assertNotIn(results[1].graph_id if results[1] else None, (20, 21))
