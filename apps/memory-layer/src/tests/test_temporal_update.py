from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from context_memory.core.resolution import FactState, TemporalRelation
from context_memory.ingestion.fakes import DeterministicTemporalUpdateModel
from context_memory.ingestion.temporal_update import TemporalUpdateClassifier


class TemporalUpdateTests(unittest.TestCase):
    def fact(
        self,
        fact_id: str,
        observed_at: datetime,
        *,
        subject: int = 7,
        predicate: str = "breed",
        valid_from: datetime | None = None,
    ) -> FactState:
        return FactState(
            fact_id, subject, predicate, "Max is a dog", observed_at, valid_from
        )

    def setUp(self) -> None:
        self.start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.prior = self.fact("prior", self.start, valid_from=self.start)

    def test_correction_closes_knowledge_not_world_validity(self) -> None:
        new = self.fact("new", self.start + timedelta(days=2))
        model = DeterministicTemporalUpdateModel(
            {("new", "prior"): TemporalRelation.CORRECTION}
        )
        decision = TemporalUpdateClassifier(model).classify(
            new_fact=new, prior_fact=self.prior
        )
        self.assertEqual(decision.relation, TemporalRelation.CORRECTION)
        self.assertEqual(decision.prior_superseded_at, new.observed_at)
        self.assertIsNone(decision.prior_valid_to)

    def test_state_change_closes_world_validity_at_supported_time(self) -> None:
        change_time = self.start + timedelta(days=4)
        new = self.fact("new", self.start + timedelta(days=5), valid_from=change_time)
        model = DeterministicTemporalUpdateModel(
            {("new", "prior"): TemporalRelation.STATE_CHANGE}
        )
        decision = TemporalUpdateClassifier(model).classify(
            new_fact=new, prior_fact=self.prior
        )
        self.assertEqual(decision.prior_valid_to, change_time)

    def test_different_subject_or_predicate_never_calls_model(self) -> None:
        new = self.fact("new", self.start + timedelta(days=2), subject=8)
        model = DeterministicTemporalUpdateModel(
            {("new", "prior"): TemporalRelation.CORRECTION}
        )
        decision = TemporalUpdateClassifier(model).classify(
            new_fact=new, prior_fact=self.prior
        )
        self.assertEqual(decision.relation, TemporalRelation.NO_UPDATE)
        self.assertEqual(model.calls, [])

    def test_out_of_order_fact_cannot_supersede_known_newer_fact(self) -> None:
        earlier = self.fact("earlier", self.start - timedelta(days=1))
        model = DeterministicTemporalUpdateModel(
            {("earlier", "prior"): TemporalRelation.STATE_CHANGE}
        )
        decision = TemporalUpdateClassifier(model).classify(
            new_fact=earlier, prior_fact=self.prior
        )
        self.assertEqual(decision.relation, TemporalRelation.NO_UPDATE)
        self.assertEqual(model.calls, [])


class _BatchRecordingModel:
    """Implements classify_updates; records batch sizes so tests can assert on call count."""

    def __init__(self, relations: dict[str, TemporalRelation] | None = None) -> None:
        self._relations = relations or {}
        self.batch_calls: list[int] = []
        self.pairwise_calls: list[tuple[str, str]] = []

    def classify_update(self, *, new_fact, prior_fact):
        self.pairwise_calls.append((new_fact.fact_id, prior_fact.fact_id))
        return self._relations.get(prior_fact.fact_id, TemporalRelation.UNRESOLVED)

    def classify_updates(self, *, new_fact, prior_facts):
        self.batch_calls.append(len(prior_facts))
        return {
            i: self._relations.get(p.fact_id, TemporalRelation.UNRESOLVED)
            for i, p in enumerate(prior_facts)
        }


class BatchedTemporalUpdateTests(unittest.TestCase):
    """§8: one call for N priors instead of N calls."""

    def fact(
        self,
        fact_id: str,
        day: int,
        *,
        subject: int = 7,
        predicate: str = "breed",
        text: str | None = None,
    ) -> FactState:
        return FactState(
            fact_id,
            subject,
            predicate,
            text or f"fact {fact_id}",
            datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(days=day),
        )

    def test_many_priors_become_one_batched_call(self) -> None:
        new = self.fact("new", 30)
        priors = [self.fact(f"p{i}", i) for i in range(12)]
        model = _BatchRecordingModel({"p3": TemporalRelation.STATE_CHANGE})
        decisions = TemporalUpdateClassifier(model).classify_many(
            new_fact=new, prior_facts=priors
        )

        self.assertEqual(model.batch_calls, [12])
        self.assertEqual(model.pairwise_calls, [])
        self.assertEqual(len(decisions), 12)
        self.assertEqual(decisions[3].relation, TemporalRelation.STATE_CHANGE)
        self.assertEqual(decisions[3].prior_superseded_at, new.observed_at)

    def test_deterministically_gated_priors_never_reach_the_model(self) -> None:
        """Out-of-order / different subject / different predicate are free rejections."""
        new = self.fact("new", 10)
        priors = [
            self.fact("later", 20),  # out of order
            self.fact("other_subject", 1, subject=99),  # different subject
            self.fact("other_pred", 1, predicate="color"),
            self.fact("real", 1),  # only this one is genuinely ambiguous
        ]
        model = _BatchRecordingModel()
        decisions = TemporalUpdateClassifier(model).classify_many(
            new_fact=new, prior_facts=priors
        )

        self.assertEqual(model.batch_calls, [1])
        self.assertEqual(len(decisions), 4)
        for i in range(3):
            self.assertEqual(decisions[i].relation, TemporalRelation.NO_UPDATE)

    def test_all_gated_makes_no_model_call_at_all(self) -> None:
        new = self.fact("new", 10)
        priors = [self.fact("later", 20), self.fact("other", 1, subject=99)]
        model = _BatchRecordingModel()
        decisions = TemporalUpdateClassifier(model).classify_many(
            new_fact=new, prior_facts=priors
        )
        self.assertEqual(model.batch_calls, [])
        self.assertEqual(len(decisions), 2)

    def test_missing_index_in_response_degrades_only_that_prior(self) -> None:
        class _PartialModel(_BatchRecordingModel):
            def classify_updates(self, *, new_fact, prior_facts):
                self.batch_calls.append(len(prior_facts))
                return {0: TemporalRelation.CORRECTION}  # omits index 1

        new = self.fact("new", 30)
        priors = [self.fact("p0", 1), self.fact("p1", 2)]
        decisions = TemporalUpdateClassifier(_PartialModel()).classify_many(
            new_fact=new, prior_facts=priors
        )
        self.assertEqual(decisions[0].relation, TemporalRelation.CORRECTION)
        self.assertEqual(decisions[1].relation, TemporalRelation.UNRESOLVED)

    def test_batch_disabled_falls_back_to_pairwise(self) -> None:
        new = self.fact("new", 30)
        priors = [self.fact(f"p{i}", i) for i in range(4)]
        model = _BatchRecordingModel()
        TemporalUpdateClassifier(model, batch_enabled=False).classify_many(
            new_fact=new, prior_facts=priors
        )
        self.assertEqual(model.batch_calls, [])
        self.assertEqual(len(model.pairwise_calls), 4)

    def test_model_without_classify_updates_falls_back_to_pairwise(self) -> None:
        new = self.fact("new", 30)
        priors = [self.fact(f"p{i}", i) for i in range(3)]
        model = DeterministicTemporalUpdateModel()  # has no classify_updates
        decisions = TemporalUpdateClassifier(model).classify_many(
            new_fact=new, prior_facts=priors
        )
        self.assertEqual(len(model.calls), 3)
        self.assertEqual(len(decisions), 3)


class _StubEmbedder:
    """Maps text -> fixed unit vector so cosine similarity is exact and testable."""

    def __init__(self, vectors: dict[str, tuple[float, ...]]) -> None:
        self._vectors = vectors
        self.batch_calls = 0

    def embed_batch(self, texts: list[str]) -> list[tuple[float, ...]]:
        self.batch_calls += 1
        return [self._vectors.get(t, (0.0, 0.0, 1.0)) for t in texts]


class SimilarityPrefilterTests(unittest.TestCase):
    """§8: drop priors too dissimilar to plausibly be a supersession."""

    def fact(
        self,
        fact_id: str,
        day: int,
        text: str,
        *,
        subject: int = 7,
        predicate: str = "p",
    ) -> FactState:
        return FactState(
            fact_id,
            subject,
            predicate,
            text,
            datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(days=day),
        )

    def setUp(self) -> None:
        # related ~cos 1.0 with new; unrelated is orthogonal (cos 0.0)
        self.vectors = {
            "new fact": (1.0, 0.0, 0.0),
            "related prior": (1.0, 0.0, 0.0),
            "unrelated prior": (0.0, 1.0, 0.0),
        }

    def test_dissimilar_priors_never_reach_the_model(self) -> None:
        new = self.fact("new", 30, "new fact")
        priors = [
            self.fact("rel", 1, "related prior"),
            self.fact("unrel", 2, "unrelated prior"),
        ]
        model = _BatchRecordingModel({"rel": TemporalRelation.STATE_CHANGE})
        classifier = TemporalUpdateClassifier(
            model, embedder=_StubEmbedder(self.vectors), similarity_threshold=0.15
        )
        decisions = classifier.classify_many(new_fact=new, prior_facts=priors)

        self.assertEqual(model.batch_calls, [1])  # only the related prior was sent
        self.assertEqual(decisions[0].relation, TemporalRelation.STATE_CHANGE)
        self.assertEqual(decisions[1].relation, TemporalRelation.NO_UPDATE)
        self.assertEqual(decisions[1].reason, "below similarity threshold")

    def test_a_genuine_supersession_survives_the_filter(self) -> None:
        """The failure that would actually hurt: filtering out a real update."""
        new = self.fact("new", 30, "new fact")
        priors = [self.fact("rel", 1, "related prior")]
        model = _BatchRecordingModel({"rel": TemporalRelation.CORRECTION})
        classifier = TemporalUpdateClassifier(
            model, embedder=_StubEmbedder(self.vectors), similarity_threshold=0.15
        )
        decisions = classifier.classify_many(new_fact=new, prior_facts=priors)
        self.assertEqual(decisions[0].relation, TemporalRelation.CORRECTION)

    def test_all_dissimilar_means_zero_model_calls(self) -> None:
        new = self.fact("new", 30, "new fact")
        priors = [
            self.fact("u1", 1, "unrelated prior"),
            self.fact("u2", 2, "unrelated prior"),
        ]
        model = _BatchRecordingModel()
        classifier = TemporalUpdateClassifier(
            model, embedder=_StubEmbedder(self.vectors), similarity_threshold=0.15
        )
        decisions = classifier.classify_many(new_fact=new, prior_facts=priors)
        self.assertEqual(model.batch_calls, [])
        self.assertEqual(
            [d.relation for d in decisions], [TemporalRelation.NO_UPDATE] * 2
        )

    def test_threshold_zero_disables_the_filter(self) -> None:
        new = self.fact("new", 30, "new fact")
        priors = [self.fact("u1", 1, "unrelated prior")]
        model = _BatchRecordingModel()
        classifier = TemporalUpdateClassifier(
            model, embedder=_StubEmbedder(self.vectors), similarity_threshold=0.0
        )
        classifier.classify_many(new_fact=new, prior_facts=priors)
        self.assertEqual(model.batch_calls, [1])

    def test_embedding_failure_degrades_to_no_filtering(self) -> None:
        class _BrokenEmbedder:
            def embed_batch(self, texts):
                raise RuntimeError("model unavailable")

        new = self.fact("new", 30, "new fact")
        priors = [self.fact("u1", 1, "unrelated prior")]
        model = _BatchRecordingModel()
        classifier = TemporalUpdateClassifier(
            model, embedder=_BrokenEmbedder(), similarity_threshold=0.15
        )
        decisions = classifier.classify_many(new_fact=new, prior_facts=priors)
        self.assertEqual(model.batch_calls, [1])  # filter skipped, not fatal
        self.assertEqual(len(decisions), 1)

    def test_embeddings_are_cached_across_calls(self) -> None:
        new = self.fact("new", 30, "new fact")
        priors = [self.fact("rel", 1, "related prior")]
        embedder = _StubEmbedder(self.vectors)
        classifier = TemporalUpdateClassifier(
            _BatchRecordingModel(), embedder=embedder, similarity_threshold=0.15
        )
        classifier.classify_many(new_fact=new, prior_facts=priors)
        classifier.classify_many(new_fact=new, prior_facts=priors)
        self.assertEqual(embedder.batch_calls, 1)  # second call served from cache
