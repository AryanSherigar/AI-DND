"""3-tier, precision-biased entity resolution: exact canonical/alias match,
then curated-nickname/embedding-similarity blocking, then bounded LLM
disambiguation over the shortlist.

Bare `§N` references below are sections of docs/fixes_and_evaluation_findings.md.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from collections.abc import Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Protocol

from context_memory.core.logging import get_logger, record_event
from context_memory.core.resolution import (
    EntityProfile,
    EntityResolution,
    ResolutionStatus,
    canonicalize_entity_surface,
)
from context_memory.ingestion.entity_blocking import (
    find_nickname_candidates,
    is_stable_for_fuzzy_matching,
)
from context_memory.ingestion.entity_hydration import HydratedEntity
from context_memory.ingestion.ports import (
    BatchEntityResolutionModel,
    EntityNameIndex,
    EntityResolutionModel,
    GraphIdAllocator,
)

logger = get_logger(__name__)


class EntityHydrator(Protocol):
    """Bulk-reads a context's existing entities+aliases from durable storage
    for `EntityRegistry`'s lazy per-context hydration. `HydraEntityHydrator`
    (`ingestion.entity_hydration`) is the production implementation."""

    def fetch(self, context_id: str) -> Sequence[HydratedEntity]: ...


class EntityRegistry:
    def __init__(
        self,
        allocator: GraphIdAllocator,
        name_index: EntityNameIndex | None = None,
        model: EntityResolutionModel | None = None,
        batch_enabled: bool = True,
        hydrator: EntityHydrator | None = None,
        max_hydrated_contexts: int = 2000,
    ) -> None:
        self._allocator = allocator
        self._name_index = name_index
        self._model = model
        self._hydrator = hydrator
        self._max_hydrated_contexts = max_hydrated_contexts
        # LRU-ordered "have I hydrated this context in this process" marker.
        # Eviction here only drops the marker (a context re-hydrates, harmless
        # extra read) -- it never drops `_profiles`/`_profile_ids_by_context`
        # content, since that could be actively mid-ingestion and a re-read
        # could lag an in-flight write for that same context. See
        # `_mark_hydrated`.
        self._hydrated_contexts: OrderedDict[str, None] = OrderedDict()
        self._hydration_locks: dict[str, threading.Lock] = {}
        self._hydration_locks_guard = threading.Lock()
        # §14: resolve_many batches mentions into one call when the model
        # supports resolve_entities() and this is True (default). Plain bool,
        # not a Config object, matching TemporalUpdateClassifier's pattern.
        self._batch_enabled = batch_enabled
        self._profiles: dict[int, EntityProfile] = {}
        # Secondary index: context_id -> graph_ids registered under it, in
        # registration order. `_in_context` used to do
        # `[p for p in self._profiles.values() if p.context_id == context_id]`
        # -- an O(every entity this registry has ever seen, across every
        # context) scan on every single `resolve()`/`resolve_many()` call,
        # since this registry is constructed once and reused for a whole
        # multi-instance run (both `create_pipeline` and `get_engine`).
        # Measured live on a real 530-turn instance (docs/fixes_and_
        # evaluation_findings.md §6): per-chunk graph-plan cost roughly
        # doubled to tripled over the course of one conversation (649ms
        # avg in the first fifth of turns -> 1581ms avg in the last fifth)
        # as the accumulated entity count grew -- and would keep
        # compounding *across* instances in the same run, since nothing
        # ever resets `self._profiles` between them. This index turns
        # `_in_context` into an O(entities actually in this context) lookup
        # instead, independent of everything else this registry has seen.
        self._profile_ids_by_context: dict[str, list[int]] = {}

    def register(self, profile: EntityProfile) -> None:
        existing = self._profiles.get(profile.graph_id)
        if existing is not None and existing != profile:
            raise ValueError(
                f"graph ID {profile.graph_id} has conflicting entity content"
            )
        is_new = profile.graph_id not in self._profiles
        self._profiles[profile.graph_id] = profile
        if is_new:
            self._profile_ids_by_context.setdefault(profile.context_id, []).append(
                profile.graph_id
            )
        self._index_profile(profile)

    def _index_profile(self, profile: EntityProfile) -> None:
        """Keeps the embedding-based candidate index (`self._name_index`,
        `ingestion.entity_name_index.EntityNameIndex`) in sync with what this
        registry actually knows. Without this, an index only ever populated
        from outside this class stays empty for every entity created
        *during* this ingestion run -- meaning a later turn in the same run
        referencing an entity from an earlier turn ("David" on turn 5,
        after "Dave" was created on turn 1) could never find it as a
        candidate, defeating the whole point of wiring the index in.
        Indexed by canonical name only (one embedding per entity, matching
        `EntityNameIndex`'s one-embedding-per-entity_id structure) -- alias
        forms are covered separately by the string-similarity blocking pass
        in `resolve()`, which reads `profile.aliases` directly and needs no
        separate index. Best-effort: a failure here degrades this one
        entity to exact-match-only resolution, never blocks the write
        that's actually being ingested.
        """
        if self._name_index is None:
            return
        try:
            self._name_index.add(
                entity_id=str(profile.graph_id),
                name=profile.canonical_name,
                entity_type=profile.entity_type,
                haystack_id=profile.context_id,
            )
        except Exception as error:
            logger.warning(
                "EntityNameIndex indexing failed for entity %s (%r): %s",
                profile.graph_id,
                profile.canonical_name,
                error,
            )

    def _grow_alias(self, graph_id: int, canonical_surface: str) -> EntityProfile:
        """Called only after a model has explicitly confirmed
        `canonical_surface` refers to the entity at `graph_id`
        (`MODEL_RESOLVED`) -- records that surface as a permanent alias so
        the *next* time it comes up, exact-alias matching resolves it
        directly without needing the model (or blocking) again. This is the
        registry's own controlled mutation of a profile it already owns,
        not an external write -- `register()`'s conflict check exists to
        catch a *different* caller trying to overwrite immutable content
        under the same graph_id, which this isn't, so this bypasses it
        deliberately rather than routing through `register()`.
        """
        existing = self._profiles[graph_id]
        if (
            canonical_surface == existing.canonical_name
            or canonical_surface in existing.aliases
        ):
            return existing  # already known under this exact form, nothing to grow
        grown = EntityProfile(
            graph_id=existing.graph_id,
            context_id=existing.context_id,
            canonical_name=existing.canonical_name,
            entity_type=existing.entity_type,
            aliases=(*existing.aliases, canonical_surface),
        )
        self._profiles[graph_id] = grown
        return grown

    def resolve_entity(
        self, context_id: str, surface: str, entity_type: str = "other"
    ) -> EntityProfile | None:
        """Helper adapter matching GraphPlanBuilder.ResolveEntity callable."""
        res = self.resolve(
            context_id=context_id, surface=surface, entity_type=entity_type
        )
        return res.entity

    def _in_context(self, context_id: str) -> list[EntityProfile]:
        # Re-fetched from `self._profiles` per id, not cached in the index
        # itself, so a grown-alias profile (`_grow_alias` replaces the dict
        # entry in place, same graph_id, same context_id) is always the
        # latest version -- the index only ever needs to track *membership*,
        # never the profile content itself.
        self._ensure_hydrated(context_id)
        return [
            self._profiles[gid]
            for gid in self._profile_ids_by_context.get(context_id, ())
        ]

    def _ensure_hydrated(self, context_id: str) -> None:
        """Runs at most once per `context_id` per process (see
        `_mark_hydrated`) -- always called before any `register()`/
        `_grow_alias()` for that context, since both are only reachable
        through `resolve()`/`resolve_many()`, which call `_in_context()`
        first. NOTE: only covers entities a *prior* process instance wrote --
        a different concurrent process writing new aliases for this context
        after this process already hydrated it is not picked up (matches
        today's single-instance deployment; see docs/BEGINNER_BUILD_FLOW.md
        item 51)."""
        if self._hydrator is None:
            return
        if context_id in self._hydrated_contexts:
            self._hydrated_contexts.move_to_end(context_id)
            return
        with self._lock_for(context_id):
            if context_id in self._hydrated_contexts:
                self._hydrated_contexts.move_to_end(context_id)
                return
            self._hydrate(context_id)
            self._mark_hydrated(context_id)

    def _lock_for(self, context_id: str) -> threading.Lock:
        with self._hydration_locks_guard:
            return self._hydration_locks.setdefault(context_id, threading.Lock())

    def _mark_hydrated(self, context_id: str) -> None:
        self._hydrated_contexts[context_id] = None
        if len(self._hydrated_contexts) > self._max_hydrated_contexts:
            oldest_context_id, _ = self._hydrated_contexts.popitem(last=False)
            with self._hydration_locks_guard:
                self._hydration_locks.pop(oldest_context_id, None)

    def _hydrate(self, context_id: str) -> None:
        try:
            hydrated = self._hydrator.fetch(context_id)
        except Exception as error:
            logger.warning(
                "EntityRegistry hydration failed for context %s (%r); resolving as cold context",
                context_id,
                error,
            )
            return
        if not hydrated:
            return
        # Bypasses `register()` deliberately: hydration only ever runs
        # before this context has any profiles registered in this process
        # (see `_ensure_hydrated`'s docstring), so `register()`'s conflict
        # check has nothing to protect against, and its per-entity
        # `name_index.add()` call would just duplicate the bulk encode
        # `rebuild_from_entities` does below.
        for entity in hydrated:
            profile = EntityProfile(
                entity.graph_id,
                context_id,
                entity.canonical_name,
                entity.entity_type,
                entity.aliases,
            )
            self._profiles[profile.graph_id] = profile
            self._profile_ids_by_context.setdefault(context_id, []).append(
                profile.graph_id
            )
        if self._name_index is not None:
            indexed = self._name_index.rebuild_from_entities(
                (str(e.graph_id), e.canonical_name, e.entity_type, context_id)
                for e in hydrated
            )
            logger.info(
                "EntityRegistry hydrated context %s: %d entities, %d indexed",
                context_id,
                len(hydrated),
                indexed,
            )

    def _exact_match(
        self, canonical: str, in_context: list[EntityProfile]
    ) -> EntityResolution | None:
        """Canonical/alias exact match only -- never touches the model,
        never mutates the registry. Shared by `resolve()` and
        `resolve_many()` so both apply the identical short-circuit."""
        canonicals = [
            profile
            for profile in in_context
            if canonicalize_entity_surface(profile.canonical_name) == canonical
        ]
        if len(canonicals) == 1:
            return EntityResolution(
                ResolutionStatus.EXACT_CANONICAL, canonicals[0], "exact canonical match"
            )
        aliases = [
            profile
            for profile in in_context
            if canonical in {canonicalize_entity_surface(a) for a in profile.aliases}
        ]
        if len(aliases) == 1:
            return EntityResolution(
                ResolutionStatus.EXACT_ALIAS, aliases[0], "exact alias match"
            )
        return None

    def _ambiguous_exact_matches(
        self, canonical: str, in_context: list[EntityProfile]
    ) -> list[EntityProfile]:
        """Every profile whose canonical name or an alias exactly equals
        `canonical` -- used only when `_exact_match` found *more than one*
        (2+ profiles genuinely share the identical string, so neither
        counts as "the" unambiguous match). These must always reach the
        shortlist regardless of what blocking finds -- an exact string
        match that happens to be ambiguous is a stronger signal than any
        similarity heuristic, and blocking was never the mechanism meant to
        carry it. Caught live: disabling trigram blocking (§4.7) exposed
        that this case had been reaching the shortlist only *incidentally*,
        via trigram's own 100%-similarity self-match on the identical
        string -- not a real blocking decision, a side effect of the
        signal that got removed. Fixed at the source instead of
        re-enabling trigram to paper over it."""
        canonicals = [
            p
            for p in in_context
            if canonicalize_entity_surface(p.canonical_name) == canonical
        ]
        aliases = [
            p
            for p in in_context
            if canonical in {canonicalize_entity_surface(a) for a in p.aliases}
        ]
        seen: dict[int, EntityProfile] = {}
        for profile in [*canonicals, *aliases]:
            seen[profile.graph_id] = profile
        return list(seen.values())

    def _generate_shortlist(
        self,
        context_id: str,
        surface: str,
        canonical: str,
        entity_type: str,
        in_context: list[EntityProfile],
        candidate_ids: Iterable[int],
    ) -> dict[int, EntityProfile]:
        """Candidate generation ("blocking") -- two signals feed the same
        bounded shortlist the LLM disambiguator judges: curated nickname
        equivalence and embedding similarity. A caller-supplied
        `candidate_ids` bypasses both (an explicit candidate set is already
        a stronger signal than blocking would produce). Read-only -- touches
        neither the model nor the registry, safe to call for many mentions
        before any of them are dispatched (see `resolve_many`).

        Trigram/fuzzy string blocking (`entity_blocking.find_fuzzy_candidates`)
        is deliberately NOT called here, despite being built and calibrated
        for exactly this purpose -- measured live (§4.7) that it accounted
        for 99.1% of all blocking events (427/431) on a real instance, and
        checking it against this module's own calibration set found it
        doesn't uniquely catch anything: "Sherlock Holmes"/"Holmes" is
        caught by embedding similarity alone (0.82-0.90, comfortably above
        threshold), "Dave"/"David" and "Bob"/"Robert" are caught by the
        nickname table alone. What it *was* catching, on real content, was
        near-noise: generic single/multi-word topic nouns ("trust", "news",
        "misinformation", "reliable sources") sharing incidental character
        overlap -- not names at all. Root cause: `entity_type` is hardcoded
        to "other" for every entity at extraction time (no schema field
        currently asks the LLM to classify person/place/organization vs.
        topic), so there's no cheap way to gate fuzzy string matching to
        only the surfaces it was designed for. The function itself is kept,
        tested, and importable -- this is a wiring change, not a deletion --
        for exactly that entity-type-aware gate if it gets built later.
        """
        candidate_ids = list(candidate_ids)
        nickname_hits = embedding_hits = 0
        if not candidate_ids:
            # Nickname lookup is exact-table lookup, not a similarity
            # heuristic, so it runs regardless of the fuzzy-matching
            # stability gate below -- a short name like "Bob" is exactly
            # the case this table exists for, unlike embedding similarity
            # where short surfaces are genuinely unreliable.
            nickname_ids = find_nickname_candidates(canonical, in_context)
            nickname_hits = len(nickname_ids)
            for gid in nickname_ids:
                if gid not in candidate_ids:
                    candidate_ids.append(gid)
            if is_stable_for_fuzzy_matching(canonical) and self._name_index:
                semantic_candidates = self._name_index.find_candidates(
                    query_name=surface, entity_type=entity_type, haystack_id=context_id
                )
                embedding_hits = len(semantic_candidates)
                for c in semantic_candidates:
                    # EntityNameIndex returns string IDs; only usable here when they're graph IDs.
                    try:
                        gid = int(c["entity_id"])
                    except ValueError:
                        continue
                    if gid not in candidate_ids:
                        candidate_ids.append(gid)

        if candidate_ids:
            # Diagnostic only -- which blocking signal(s) actually produced
            # this shortlist. Feeds the same opt-in metrics sink §3.12 built
            # (zero cost unless a caller enabled it), so a real run's
            # metrics.jsonl can answer "is blocking too loose" with counts
            # instead of a guess -- this is exactly how the 618-call volume
            # at real scale got measured in the first place (§4.6/4.7).
            record_event(
                "entity_resolution.blocking",
                {
                    "canonical": canonical,
                    "nickname_hits": nickname_hits,
                    "embedding_hits": embedding_hits,
                    "total_candidates": len(candidate_ids),
                },
            )

        shortlist: dict[int, EntityProfile] = {}
        for graph_id in candidate_ids:
            profile = self._profiles.get(graph_id)
            if profile is not None and profile.context_id == context_id:
                shortlist[graph_id] = profile
        return shortlist

    def resolve(
        self,
        *,
        context_id: str,
        surface: str,
        entity_type: str = "other",
        candidate_ids: Iterable[int] = (),
        model: EntityResolutionModel | None = None,
    ) -> EntityResolution:
        effective_model = model if model is not None else self._model
        canonical = canonicalize_entity_surface(surface)
        in_context = self._in_context(context_id)

        exact = self._exact_match(canonical, in_context)
        if exact is not None:
            return exact
        candidate_ids = list(candidate_ids) or [
            p.graph_id for p in self._ambiguous_exact_matches(canonical, in_context)
        ]

        shortlist = self._generate_shortlist(
            context_id, surface, canonical, entity_type, in_context, candidate_ids
        )
        if shortlist:
            if effective_model is None:
                return EntityResolution(
                    ResolutionStatus.UNRESOLVED,
                    None,
                    "ambiguous candidate set requires model",
                )
            selected_id = effective_model.resolve_entity(
                context_id=context_id,
                surface=surface,
                candidates=tuple(shortlist.values()),
            )
            selected = shortlist.get(selected_id) if selected_id is not None else None
            if selected is None:
                return EntityResolution(
                    ResolutionStatus.UNRESOLVED,
                    None,
                    "model abstained or selected outside bounded candidates",
                )
            grown = self._grow_alias(selected.graph_id, canonical)
            return EntityResolution(
                ResolutionStatus.MODEL_RESOLVED,
                grown,
                "model selected bounded candidate",
            )
        graph_id = self._allocator.allocate_graph_id(
            "entity", context_id, f"entity:{canonical}"
        )
        profile = EntityProfile(graph_id, context_id, canonical, entity_type)
        self.register(profile)
        return EntityResolution(
            ResolutionStatus.NEW_ENTITY, profile, "no candidate in active context"
        )

    def resolve_many(
        self,
        context_id: str,
        mentions: Sequence[tuple[str, str]],
        *,
        model: EntityResolutionModel | None = None,
        max_workers: int = 8,
    ) -> list[EntityProfile | None]:
        """Resolves several entity mentions from the SAME chunk together,
        parallelizing only the LLM disambiguation calls -- candidate
        generation and every registry mutation stay fully serial. Built
        because `entity_resolution.disambiguate` was measured live as 83%
        of ingest time at real scale (618 calls for 100 turns), and a
        single chunk with several ambiguous mentions was paying for each
        call sequentially even though the calls don't depend on each other
        (see docs/fixes_and_evaluation_findings.md §4.7).

        `mentions` is `(surface, entity_type)` pairs in source order;
        returns resolved profiles (or `None` for unresolved) in the same
        order and length.

        Safety, and the one real tradeoff accepted to get it: mentions are
        first grouped by canonicalized surface -- repeats of the identical
        surface within this batch resolve once and reuse the result,
        correct because they refer to the same mention. Every *distinct*
        surface's candidate shortlist is generated up front, against the
        registry exactly as it stood when this call started (nothing
        mutates it until the apply phase at the end) -- so unlike calling
        `resolve()` sequentially per mention, one distinct surface in this
        batch will NOT see another distinct surface in the SAME batch as a
        candidate even if they're genuinely the same entity (e.g. "Bob" and
        "Robert" both appearing for the first time in one turn) -- both mint
        their own separate entity. Checked, not assumed: this split is
        *not* self-correcting for those two exact surfaces afterward -- a
        later "Bob" exact-matches its own already-registered entity (exact
        match is checked before blocking ever runs again), never "Robert"'s.
        What does still work: a later, *different* surface in the same
        nickname-equivalence group (e.g. "Bobby") sees both split entities
        as candidates and the model can correctly attach it to one of them
        -- new references aren't stuck being ambiguous, the two existing
        entities just never retroactively merge with each other. A real,
        narrower version of the same recall tradeoff already accepted for
        cross-chunk write batching (orchestrator.py, §3.9), bounded to one
        chunk's mentions. Exact canonical/alias matches are entirely
        unaffected either way -- they never needed the model and never had
        this problem, resolved immediately in phase 1 below before any
        candidate generation runs at all.
        """
        if not mentions:
            return []

        effective_model = model if model is not None else self._model
        in_context = self._in_context(context_id)

        # Phase 1: exact matches first -- never mutate the registry, so
        # doing every one of these before any candidate generation doesn't
        # change what phase 2 sees.
        resolved_by_index: list[EntityProfile | None] = [None] * len(mentions)
        canonical_by_index: list[str] = []
        pending_indices_by_surface: dict[str, list[int]] = {}
        entity_type_by_surface: dict[str, str] = {}
        surface_for_prompt_by_canonical: dict[str, str] = {}

        for i, (surface, entity_type) in enumerate(mentions):
            canonical = canonicalize_entity_surface(surface)
            canonical_by_index.append(canonical)
            exact = self._exact_match(canonical, in_context)
            if exact is not None:
                resolved_by_index[i] = exact.entity
                continue
            pending_indices_by_surface.setdefault(canonical, []).append(i)
            entity_type_by_surface.setdefault(canonical, entity_type)
            surface_for_prompt_by_canonical.setdefault(canonical, surface)

        if not pending_indices_by_surface:
            return resolved_by_index

        # Phase 2: generate each distinct pending surface's shortlist --
        # still entirely read-only, still against the same untouched
        # snapshot `in_context` from phase 1. An ambiguous exact match (2+
        # profiles already share this identical string) always seeds the
        # shortlist directly -- see `_ambiguous_exact_matches`'s docstring
        # for why this can't be left to blocking to rediscover.
        shortlists: dict[str, dict[int, EntityProfile]] = {
            canonical: self._generate_shortlist(
                context_id,
                surface_for_prompt_by_canonical[canonical],
                canonical,
                entity_type_by_surface[canonical],
                in_context,
                [
                    p.graph_id
                    for p in self._ambiguous_exact_matches(canonical, in_context)
                ],
            )
            for canonical in pending_indices_by_surface
        }

        # Phase 3: resolve every distinct surface with a non-empty shortlist.
        # Each call only reads its own already-fixed shortlist; nothing here
        # touches `self._profiles`. Batched into one call when the model
        # supports it and batching is enabled (§14) -- cuts request count,
        # the actual pressure point under concurrency; falls back to firing
        # one concurrent call per surface otherwise (unchanged from before).
        to_call = [
            canonical for canonical, shortlist in shortlists.items() if shortlist
        ]
        model_results: dict[str, EntityProfile | None] = {}
        if to_call and effective_model is not None:
            if self._batch_enabled and isinstance(
                effective_model, BatchEntityResolutionModel
            ):
                batch_mentions = [
                    (
                        surface_for_prompt_by_canonical[canonical],
                        tuple(shortlists[canonical].values()),
                    )
                    for canonical in to_call
                ]
                selected = effective_model.resolve_entities(
                    context_id=context_id, mentions=batch_mentions
                )
                for slot, canonical in enumerate(to_call):
                    selected_id = selected.get(slot)
                    model_results[canonical] = (
                        shortlists[canonical].get(selected_id)
                        if selected_id is not None
                        else None
                    )
            else:

                def _call_model(canonical: str) -> EntityProfile | None:
                    shortlist = shortlists[canonical]
                    selected_id = effective_model.resolve_entity(
                        context_id=context_id,
                        surface=surface_for_prompt_by_canonical[canonical],
                        candidates=tuple(shortlist.values()),
                    )
                    return (
                        shortlist.get(selected_id) if selected_id is not None else None
                    )

                with ThreadPoolExecutor(max_workers=max_workers) as pool:
                    future_to_canonical = {
                        pool.submit(_call_model, canonical): canonical
                        for canonical in to_call
                    }
                    for future in as_completed(future_to_canonical):
                        canonical = future_to_canonical[future]
                        model_results[canonical] = future.result()

        # Phase 4: apply mutations serially, in a stable order (first
        # occurrence in `mentions`, not completion order) so replay/
        # idempotency behavior never depends on network timing.
        for canonical in sorted(
            pending_indices_by_surface, key=lambda c: pending_indices_by_surface[c][0]
        ):
            shortlist = shortlists[canonical]
            if not shortlist:
                graph_id = self._allocator.allocate_graph_id(
                    "entity", context_id, f"entity:{canonical}"
                )
                profile = EntityProfile(
                    graph_id, context_id, canonical, entity_type_by_surface[canonical]
                )
                self.register(profile)
                resolved_profile: EntityProfile | None = profile
            else:
                selected = model_results.get(canonical)
                resolved_profile = (
                    self._grow_alias(selected.graph_id, canonical)
                    if selected is not None
                    else None
                )
            for i in pending_indices_by_surface[canonical]:
                resolved_by_index[i] = resolved_profile

        return resolved_by_index
