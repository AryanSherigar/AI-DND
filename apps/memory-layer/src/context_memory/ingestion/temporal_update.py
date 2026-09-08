"""Post-gating decision over one new/prior fact pair: deterministic rejection
first, LLM classification (single or batched) for what's left.

Bare `§N` references below are sections of docs/fixes_and_evaluation_findings.md.
"""

from __future__ import annotations

from collections.abc import Sequence

from context_memory.core.logging import get_logger
from context_memory.core.resolution import (
    FactState,
    TemporalRelation,
    TemporalUpdateDecision,
)
from context_memory.ingestion.ports import BatchTemporalUpdateModel, TemporalUpdateModel

logger = get_logger(__name__)


class TemporalUpdateClassifier:
    _EMBED_CACHE_CAP = 50_000

    def __init__(
        self,
        model: TemporalUpdateModel,
        batch_enabled: bool = True,
        embedder: object | None = None,
        similarity_threshold: float = 0.0,
    ) -> None:
        self._model = model
        self._batch_enabled = batch_enabled
        self._embedder = embedder
        self._similarity_threshold = similarity_threshold
        self._embed_cache: dict[str, tuple[float, ...]] = {}

    def _embed_all(self, texts: list[str]) -> dict[str, tuple[float, ...]]:
        missing = [t for t in dict.fromkeys(texts) if t not in self._embed_cache]
        if missing:
            if len(self._embed_cache) > self._EMBED_CACHE_CAP:
                self._embed_cache.clear()
            try:
                for text, vector in zip(missing, self._embedder.embed_batch(missing)):
                    self._embed_cache[text] = vector
            except Exception as error:
                logger.warning(
                    "temporal-update prefilter embedding failed, skipping filter: %s",
                    error,
                )
                return {}
        return {t: self._embed_cache[t] for t in texts if t in self._embed_cache}

    def _prefilter(
        self, new_fact: FactState, candidates: list[tuple[int, FactState]]
    ) -> tuple[list[tuple[int, FactState]], list[int]]:
        """Drops priors too dissimilar to be a plausible supersession.

        Threshold calibrated on 3540 real recorded comparisons (§8): every
        supersession dropped below 0.15 was verifiably spurious.
        """
        if (
            self._embedder is None
            or self._similarity_threshold <= 0.0
            or not candidates
        ):
            return candidates, []
        vectors = self._embed_all([new_fact.text] + [p.text for _, p in candidates])
        new_vector = vectors.get(new_fact.text)
        if new_vector is None:
            return candidates, []
        kept: list[tuple[int, FactState]] = []
        dropped: list[int] = []
        for index, prior in candidates:
            prior_vector = vectors.get(prior.text)
            if prior_vector is None or (
                sum(a * b for a, b in zip(new_vector, prior_vector))
                >= self._similarity_threshold
            ):
                kept.append((index, prior))
            else:
                dropped.append(index)
        return kept, dropped

    def _gate(
        self, new_fact: FactState, prior_fact: FactState
    ) -> TemporalUpdateDecision | None:
        """Deterministic rejections that need no model call. None = ask the model."""
        if new_fact.observed_at <= prior_fact.observed_at:
            return TemporalUpdateDecision(
                TemporalRelation.NO_UPDATE, "out-of-order or equal observation time"
            )
        if new_fact.subject_entity_id != prior_fact.subject_entity_id:
            return TemporalUpdateDecision(
                TemporalRelation.NO_UPDATE, "different subject entity"
            )
        if new_fact.predicate_key != prior_fact.predicate_key:
            return TemporalUpdateDecision(
                TemporalRelation.NO_UPDATE, "different predicate key"
            )
        return None

    def classify_many(
        self, *, new_fact: FactState, prior_facts: Sequence[FactState]
    ) -> list[TemporalUpdateDecision]:
        """Decisions for every prior, in input order, using one batched model call.

        Falls back to the pairwise path when batching is disabled or the model
        does not implement `classify_updates`.
        """
        decisions: list[TemporalUpdateDecision | None] = []
        to_ask: list[tuple[int, FactState]] = []
        for i, prior_fact in enumerate(prior_facts):
            gated = self._gate(new_fact, prior_fact)
            decisions.append(gated)
            if gated is None:
                to_ask.append((i, prior_fact))

        if not to_ask:
            return [d for d in decisions if d is not None]

        to_ask, prefiltered = self._prefilter(new_fact, to_ask)
        for index in prefiltered:
            decisions[index] = TemporalUpdateDecision(
                TemporalRelation.NO_UPDATE, "below similarity threshold"
            )
        if not to_ask:
            return [
                d
                if d is not None
                else TemporalUpdateDecision(TemporalRelation.UNRESOLVED, "no decision")
                for d in decisions
            ]

        batch = self._batch_enabled and isinstance(
            self._model, BatchTemporalUpdateModel
        )
        if batch:
            relations = self._model.classify_updates(
                new_fact=new_fact, prior_facts=[p for _, p in to_ask]
            )
            for slot, (i, _) in enumerate(to_ask):
                decisions[i] = self._decide(
                    new_fact, relations.get(slot, TemporalRelation.UNRESOLVED)
                )
        else:
            for i, prior_fact in to_ask:
                decisions[i] = self.classify(new_fact=new_fact, prior_fact=prior_fact)
        return [
            d
            if d is not None
            else TemporalUpdateDecision(TemporalRelation.UNRESOLVED, "no decision")
            for d in decisions
        ]

    def classify(
        self, *, new_fact: FactState, prior_fact: FactState
    ) -> TemporalUpdateDecision:
        gated = self._gate(new_fact, prior_fact)
        if gated is not None:
            return gated
        return self._decide(
            new_fact,
            self._model.classify_update(new_fact=new_fact, prior_fact=prior_fact),
        )

    def _decide(
        self, new_fact: FactState, relation: TemporalRelation
    ) -> TemporalUpdateDecision:
        if relation is TemporalRelation.CORRECTION:
            return TemporalUpdateDecision(
                relation,
                "model-confirmed correction",
                prior_superseded_at=new_fact.observed_at,
            )
        if relation is TemporalRelation.STATE_CHANGE:
            effective_at = new_fact.valid_from or new_fact.observed_at
            return TemporalUpdateDecision(
                relation,
                "model-confirmed state change",
                prior_superseded_at=new_fact.observed_at,
                prior_valid_to=effective_at,
            )
        if relation is TemporalRelation.NO_UPDATE:
            return TemporalUpdateDecision(relation, "model found no update")
        return TemporalUpdateDecision(TemporalRelation.UNRESOLVED, "model abstained")
