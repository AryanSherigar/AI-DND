from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone

from context_memory.core.errors import ExtractionProviderError
from context_memory.core.llm_client import LLMClient
from context_memory.core.resolution import EntityProfile, FactState, TemporalRelation
from context_memory.ingestion.model_adapters import (
    LLMEntityResolutionModel,
    LLMTemporalUpdateModel,
)
from google.genai import types


def _gemini_response(content: str | None) -> types.GenerateContentResponse:
    parts = [types.Part(text=content)] if content is not None else []
    return types.GenerateContentResponse(
        candidates=[
            types.Candidate(
                content=types.Content(role="model", parts=parts),
                finish_reason=types.FinishReason.STOP,
            )
        ],
        usage_metadata=None,
    )


class _FakeModels:
    """Fakes `google.genai.Client().models` -- records every call as a
    `{"model", "contents", "config"}` dict so a test can inspect either the
    system prompt (`config.system_instruction`, where the schema/typedef
    gets injected) or the user prompt (`contents[0].parts[0].text`, where
    the actual turn/mention text and any `--- Turn N ---` markers live)."""

    def __init__(self, content: str | None, exception: Exception | None = None) -> None:
        self._content = content
        self._exception = exception
        self.calls: list[dict[str, object]] = []

    def generate_content(
        self, *, model, contents, config
    ) -> types.GenerateContentResponse:
        self.calls.append({"model": model, "contents": contents, "config": config})
        if self._exception is not None:
            raise self._exception
        return _gemini_response(self._content)


class _FakeGenAIClient:
    def __init__(
        self, content: str | None = None, exception: Exception | None = None
    ) -> None:
        self.models = _FakeModels(content, exception)


def _client(
    content: str | None = None, exception: Exception | None = None
) -> LLMClient:
    fake = _FakeGenAIClient(content, exception)
    return LLMClient(api_key="fake-key", model_name="fake-model", client=fake)


def _user_text(call: dict[str, object]) -> str:
    return call["contents"][0].parts[0].text


class EntityResolutionModelTests(unittest.TestCase):
    def candidates(self) -> tuple[EntityProfile, ...]:
        return (
            EntityProfile(1, "context:1", "max the dog", "pet", ("my dog",)),
            EntityProfile(2, "context:1", "max the colleague", "person"),
        )

    def test_bounded_selection_returns_model_choice(self) -> None:
        model = LLMEntityResolutionModel(_client(json.dumps({"selected_graph_id": 1})))
        selected = model.resolve_entity(
            context_id="context:1", surface="my dog", candidates=self.candidates()
        )
        self.assertEqual(selected, 1)

    def test_model_abstains_with_null(self) -> None:
        model = LLMEntityResolutionModel(
            _client(json.dumps({"selected_graph_id": None}))
        )
        selected = model.resolve_entity(
            context_id="context:1", surface="Sam", candidates=self.candidates()
        )
        self.assertIsNone(selected)

    def test_empty_candidates_never_calls_model(self) -> None:
        client = _client(json.dumps({"selected_graph_id": 1}))
        model = LLMEntityResolutionModel(client)
        selected = model.resolve_entity(
            context_id="context:1", surface="Sam", candidates=()
        )
        self.assertIsNone(selected)

    def test_malformed_response_resolves_to_none_not_an_exception(self) -> None:
        model = LLMEntityResolutionModel(_client("not json"))
        selected = model.resolve_entity(
            context_id="context:1", surface="my dog", candidates=self.candidates()
        )
        self.assertIsNone(selected)

    def test_out_of_bounds_id_is_returned_unfiltered_caller_must_reject(self) -> None:
        # The adapter does not enforce the bound itself; EntityRegistry.resolve does.
        # This test documents that boundary explicitly.
        model = LLMEntityResolutionModel(
            _client(json.dumps({"selected_graph_id": 999}))
        )
        selected = model.resolve_entity(
            context_id="context:1", surface="my dog", candidates=self.candidates()
        )
        self.assertEqual(selected, 999)


class BatchedEntityResolutionModelTests(unittest.TestCase):
    """§14: one call resolving several mentions instead of one per mention."""

    def candidates(self) -> tuple[EntityProfile, ...]:
        return (
            EntityProfile(1, "context:1", "max the dog", "pet", ("my dog",)),
            EntityProfile(2, "context:1", "max the colleague", "person"),
        )

    def test_happy_path_maps_selections_back_to_the_right_mention(self) -> None:
        response_json = json.dumps(
            {
                "results": [
                    {"idx": 0, "selected_graph_id": 1},
                    {"idx": 1, "selected_graph_id": None},
                ]
            }
        )
        model = LLMEntityResolutionModel(_client(response_json))
        mentions = [("my dog", self.candidates()), ("Sam", self.candidates())]
        results = model.resolve_entities(context_id="context:1", mentions=mentions)
        self.assertEqual(results[0], 1)
        self.assertIsNone(results[1])

    def test_missing_index_omitted_from_result_not_defaulted(self) -> None:
        response_json = json.dumps({"results": [{"idx": 0, "selected_graph_id": 1}]})
        model = LLMEntityResolutionModel(_client(response_json))
        mentions = [("my dog", self.candidates()), ("Sam", self.candidates())]
        results = model.resolve_entities(context_id="context:1", mentions=mentions)
        self.assertEqual(results, {0: 1})

    def test_malformed_response_returns_empty_dict_without_raising(self) -> None:
        model = LLMEntityResolutionModel(_client("not json"))
        mentions = [("my dog", self.candidates())]
        results = model.resolve_entities(context_id="context:1", mentions=mentions)
        self.assertEqual(results, {})

    def test_empty_mentions_short_circuits_without_a_call(self) -> None:
        fake = _FakeGenAIClient(json.dumps({"results": []}))
        client = LLMClient(api_key="fake-key", model_name="fake-model", client=fake)
        model = LLMEntityResolutionModel(client)
        model.resolve_entities(context_id="context:1", mentions=[])
        self.assertEqual(len(fake.models.calls), 0)

    def test_batch_prompt_numbers_mentions_and_max_tokens_scales_with_count(
        self,
    ) -> None:
        from context_memory.core.config import Config

        fake = _FakeGenAIClient(json.dumps({"results": []}))
        client = LLMClient(api_key="fake-key", model_name="fake-model", client=fake)
        config = Config()
        model = LLMEntityResolutionModel(client, config)
        mentions = [("my dog", self.candidates()), ("Sam", self.candidates())]
        model.resolve_entities(context_id="context:1", mentions=mentions)
        call = fake.models.calls[-1]
        self.assertIn("--- Mention 0 ---", _user_text(call))
        self.assertIn("--- Mention 1 ---", _user_text(call))
        expected = (
            config.entity_resolution_max_tokens
            + config.entity_resolution_batch_tokens_per_mention * 2
        )
        self.assertEqual(call["config"].max_output_tokens, expected)


class TemporalUpdateModelTests(unittest.TestCase):
    def facts(self) -> tuple[FactState, FactState]:
        prior = FactState(
            "fact:1",
            1,
            "lives_in",
            "Max lives in Boston",
            datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        new = FactState(
            "fact:2",
            1,
            "lives_in",
            "Max lives in Seattle",
            datetime(2026, 2, 1, tzinfo=timezone.utc),
        )
        return new, prior

    def test_correction_relation_parses(self) -> None:
        new, prior = self.facts()
        model = LLMTemporalUpdateModel(_client(json.dumps({"relation": "correction"})))
        self.assertEqual(
            model.classify_update(new_fact=new, prior_fact=prior),
            TemporalRelation.CORRECTION,
        )

    def test_state_change_relation_parses(self) -> None:
        new, prior = self.facts()
        model = LLMTemporalUpdateModel(
            _client(json.dumps({"relation": "state_change"}))
        )
        self.assertEqual(
            model.classify_update(new_fact=new, prior_fact=prior),
            TemporalRelation.STATE_CHANGE,
        )

    def test_invalid_json_resolves_to_unresolved(self) -> None:
        new, prior = self.facts()
        model = LLMTemporalUpdateModel(_client("{not valid json"))
        self.assertEqual(
            model.classify_update(new_fact=new, prior_fact=prior),
            TemporalRelation.UNRESOLVED,
        )

    def test_invalid_enum_value_resolves_to_unresolved(self) -> None:
        new, prior = self.facts()
        model = LLMTemporalUpdateModel(
            _client(json.dumps({"relation": "made_up_value"}))
        )
        self.assertEqual(
            model.classify_update(new_fact=new, prior_fact=prior),
            TemporalRelation.UNRESOLVED,
        )


from context_memory.core.models import ContextRecord
from context_memory.ingestion.model_adapters import (
    LLMExtractor,
)


class LLMExtractorTests(unittest.TestCase):
    def test_extract_facts_happy_path(self) -> None:
        response_json = json.dumps(
            {
                "facts": [
                    {
                        "text": "User adopted a dog named Max",
                        "action": "ADD",
                        "predicate_key": "pet_name",
                        "entities": ["Max"],
                        "confidence": 0.98,
                        "exact_quote": "dog named Max",
                    }
                ]
            }
        )
        extractor = LLMExtractor(_client(response_json))
        record = ContextRecord(
            record_id="rec:001",
            session_id="session:001",
            actor_role="user",
            occurred_at=datetime.now(timezone.utc),
            content_type="text/plain",
            content="I just adopted a dog named Max from the shelter.",
        )
        drafts = extractor.extract(record)
        self.assertEqual(len(drafts), 1)
        self.assertEqual(drafts[0].text, "User adopted a dog named Max")
        self.assertEqual(drafts[0].action, "ADD")
        self.assertEqual(drafts[0].predicate_key, "pet_name")
        self.assertEqual(drafts[0].entities[0].surface, "Max")
        self.assertEqual(drafts[0].confidence, 0.98)
        self.assertEqual(
            record.content[drafts[0].source_start : drafts[0].source_end],
            "dog named Max",
        )

    def test_extract_facts_carries_subject_and_object_as_real_triple_components(
        self,
    ) -> None:
        """§9 fix: subject/object are normalized values distinct from `text`
        (the full sentence, kept as evidence regardless)."""
        response_json = json.dumps(
            {
                "facts": [
                    {
                        "text": "The dog is currently waiting near the western gate.",
                        "predicate_key": "located_at",
                        "entities": ["dog"],
                        "subject": "dog",
                        "object": "western gate",
                    }
                ]
            }
        )
        extractor = LLMExtractor(_client(response_json))
        record = ContextRecord(
            record_id="rec:003",
            session_id="session:001",
            actor_role="user",
            occurred_at=datetime.now(timezone.utc),
            content_type="text/plain",
            content="The dog is currently waiting near the western gate.",
        )
        drafts = extractor.extract(record)
        self.assertEqual(drafts[0].subject, "dog")
        self.assertEqual(drafts[0].object, "western gate")
        self.assertEqual(
            drafts[0].text, "The dog is currently waiting near the western gate."
        )

    def test_extract_facts_blank_subject_and_object_degrade_to_none(self) -> None:
        response_json = json.dumps(
            {"facts": [{"text": "User likes tea", "subject": "  ", "object": ""}]}
        )
        extractor = LLMExtractor(_client(response_json))
        record = ContextRecord(
            record_id="rec:004",
            session_id="session:001",
            actor_role="user",
            occurred_at=datetime.now(timezone.utc),
            content_type="text/plain",
            content="User likes tea",
        )
        drafts = extractor.extract(record)
        self.assertIsNone(drafts[0].subject)
        self.assertIsNone(drafts[0].object)

    def test_extract_malformed_response_raises_instead_of_silently_returning_empty(
        self,
    ) -> None:
        """§2 fix: was `self.assertEqual(drafts, ())` -- a provider/parse
        failure is now indistinguishable from success at this boundary only
        if it raises; a silent `()` return is reserved for a genuinely valid
        empty result (see test_extract_facts_happy_path's sibling below)."""
        extractor = LLMExtractor(_client("{malformed json"))
        record = ContextRecord(
            record_id="rec:002",
            session_id="session:001",
            actor_role="user",
            occurred_at=datetime.now(timezone.utc),
            content_type="text/plain",
            content="Hello there!",
        )
        with self.assertRaises(ExtractionProviderError):
            extractor.extract(record)

    def test_extract_genuinely_empty_facts_list_still_returns_empty(self) -> None:
        """The call itself succeeds and the model legitimately found nothing
        -- must stay a normal `()`, not raise."""
        extractor = LLMExtractor(_client(json.dumps({"facts": []})))
        record = ContextRecord(
            record_id="rec:002b",
            session_id="session:001",
            actor_role="user",
            occurred_at=datetime.now(timezone.utc),
            content_type="text/plain",
            content="Hello there!",
        )
        self.assertEqual(extractor.extract(record), ())

    def test_extraction_max_tokens_tiers_by_content_length(self) -> None:
        """Multi-stage max_tokens gateway: the extractor picks its budget
        from `Config.extraction_max_tokens_for`, not one flat number, and it
        actually reaches the underlying call -- not just computed and
        discarded."""
        from context_memory.core.config import Config

        fake = _FakeGenAIClient(json.dumps({"facts": []}))
        client = LLMClient(api_key="fake-key", model_name="fake-model", client=fake)
        config = Config()
        extractor = LLMExtractor(client, config)

        def make_record(content: str) -> ContextRecord:
            return ContextRecord(
                record_id="rec:tier",
                session_id="session:001",
                actor_role="user",
                occurred_at=datetime.now(timezone.utc),
                content_type="text/plain",
                content=content,
            )

        cases = [
            (50, config.extractor_max_tokens_tier_short),  # short: <=300 chars
            (800, config.extractor_max_tokens_tier_medium),  # medium: <=1200 chars
            (2500, config.extractor_max_tokens_tier_long),  # long: <=3000 chars
            (5000, config.extractor_max_tokens_tier_xlong),  # xlong: >3000 chars
        ]
        for length, expected_max_tokens in cases:
            extractor.extract(make_record("x" * length))
            actual = fake.models.calls[-1]["config"].max_output_tokens
            self.assertEqual(
                actual,
                expected_max_tokens,
                f"content_length={length} should get max_tokens={expected_max_tokens}, got {actual}",
            )

        # A genuine ascending gateway, not four arbitrary numbers.
        self.assertLess(
            config.extractor_max_tokens_tier_short,
            config.extractor_max_tokens_tier_medium,
        )
        self.assertLess(
            config.extractor_max_tokens_tier_medium,
            config.extractor_max_tokens_tier_long,
        )
        self.assertLess(
            config.extractor_max_tokens_tier_long,
            config.extractor_max_tokens_tier_xlong,
        )

    def test_extraction_max_tokens_for_boundaries_are_inclusive(self) -> None:
        from context_memory.core.config import Config

        config = Config()
        self.assertEqual(
            config.extraction_max_tokens_for(
                config.extractor_max_tokens_tier_short_chars
            ),
            config.extractor_max_tokens_tier_short,
        )
        self.assertEqual(
            config.extraction_max_tokens_for(
                config.extractor_max_tokens_tier_short_chars + 1
            ),
            config.extractor_max_tokens_tier_medium,
        )
        self.assertEqual(
            config.extraction_max_tokens_for(
                config.extractor_max_tokens_tier_medium_chars
            ),
            config.extractor_max_tokens_tier_medium,
        )
        self.assertEqual(
            config.extraction_max_tokens_for(
                config.extractor_max_tokens_tier_medium_chars + 1
            ),
            config.extractor_max_tokens_tier_long,
        )
        self.assertEqual(
            config.extraction_max_tokens_for(
                config.extractor_max_tokens_tier_long_chars
            ),
            config.extractor_max_tokens_tier_long,
        )
        self.assertEqual(
            config.extraction_max_tokens_for(
                config.extractor_max_tokens_tier_long_chars + 1
            ),
            config.extractor_max_tokens_tier_xlong,
        )


class LLMExtractorBatchTests(unittest.TestCase):
    """extract_batch (docs/fixes_and_evaluation_findings.md §7): packs several
    turns into one call. Correctness bar is different from extract() -- the
    new failure mode is a fact landing against the WRONG turn_index, not just
    an empty/malformed response, so these tests check per-turn isolation, not
    just the happy path."""

    def _record(self, record_id: str, content: str) -> ContextRecord:
        return ContextRecord(
            record_id=record_id,
            session_id="session:001",
            actor_role="user",
            occurred_at=datetime.now(timezone.utc),
            content_type="text/plain",
            content=content,
        )

    def test_happy_path_maps_facts_back_to_the_right_record(self) -> None:
        response_json = json.dumps(
            {
                "turns": [
                    {
                        "turn_index": 0,
                        "facts": [
                            {
                                "text": "User owns a dog named Max",
                                "predicate_key": "pet_name",
                                "entities": ["Max"],
                                "confidence": 0.98,
                                "exact_quote": "dog named Max",
                            },
                        ],
                    },
                    {
                        "turn_index": 1,
                        "facts": [
                            {
                                "text": "User works as a teacher",
                                "predicate_key": "occupation",
                                "entities": ["teacher"],
                                "confidence": 0.95,
                                "exact_quote": "I'm a teacher",
                            },
                        ],
                    },
                ]
            }
        )
        extractor = LLMExtractor(_client(response_json))
        records = [
            self._record("rec:a", "I have a dog named Max."),
            self._record("rec:b", "I'm a teacher at the local school."),
        ]
        results = extractor.extract_batch(records)
        self.assertEqual(len(results["rec:a"]), 1)
        self.assertEqual(results["rec:a"][0].text, "User owns a dog named Max")
        self.assertEqual(len(results["rec:b"]), 1)
        self.assertEqual(results["rec:b"][0].text, "User works as a teacher")
        # Source span is computed against THAT record's own content, not the
        # other one's -- this is the concrete check that per-turn isolation held.
        self.assertEqual(
            records[0].content[
                results["rec:a"][0].source_start : results["rec:a"][0].source_end
            ],
            "dog named Max",
        )
        self.assertEqual(
            records[1].content[
                results["rec:b"][0].source_start : results["rec:b"][0].source_end
            ],
            "I'm a teacher",
        )

    def test_missing_turn_index_degrades_that_one_record_only(self) -> None:
        """Model returns entries for turn 0 but skips turn 1 entirely -- turn 1
        should come back empty, and turn 0 must still be unaffected."""
        response_json = json.dumps(
            {
                "turns": [
                    {
                        "turn_index": 0,
                        "facts": [
                            {
                                "text": "User owns a dog named Max",
                                "entities": ["Max"],
                                "exact_quote": "dog named Max",
                            },
                        ],
                    },
                ]
            }
        )
        extractor = LLMExtractor(_client(response_json))
        records = [
            self._record("rec:a", "I have a dog named Max."),
            self._record("rec:b", "I'm a teacher at the local school."),
        ]
        results = extractor.extract_batch(records)
        self.assertEqual(len(results["rec:a"]), 1)
        self.assertEqual(results["rec:b"], ())

    def test_malformed_batch_response_raises_instead_of_returning_empty_for_every_record(
        self,
    ) -> None:
        """§2 fix: was asserting a silent `{"rec:a": (), "rec:b": ()}` --
        indistinguishable from every turn in the batch genuinely having no
        facts. A call failure covering the whole batch now raises."""
        extractor = LLMExtractor(_client("{malformed json"))
        records = [self._record("rec:a", "hello"), self._record("rec:b", "world")]
        with self.assertRaises(ExtractionProviderError):
            extractor.extract_batch(records)

    def test_whitespace_only_records_are_skipped_but_still_present_in_the_result(
        self,
    ) -> None:
        # ContextRecord requires non-empty content, so "blank" here means
        # whitespace-only -- still non-empty per the contract, but treated as
        # having no durable content by extract_batch's own strip() check.
        extractor = LLMExtractor(_client(json.dumps({"turns": []})))
        records = [self._record("rec:a", "  "), self._record("rec:b", "\n\t")]
        results = extractor.extract_batch(records)
        self.assertEqual(results, {"rec:a": (), "rec:b": ()})

    def test_all_whitespace_batch_short_circuits_without_a_call(self) -> None:
        fake = _FakeGenAIClient(json.dumps({"turns": []}))
        client = LLMClient(api_key="fake-key", model_name="fake-model", client=fake)
        extractor = LLMExtractor(client)
        records = [self._record("rec:a", "  "), self._record("rec:b", " ")]
        extractor.extract_batch(records)
        self.assertEqual(len(fake.models.calls), 0)

    def test_batch_prompt_numbers_turns_and_max_tokens_sums_per_turn_tiers(
        self,
    ) -> None:
        from context_memory.core.config import Config

        fake = _FakeGenAIClient(json.dumps({"turns": []}))
        client = LLMClient(api_key="fake-key", model_name="fake-model", client=fake)
        config = Config()
        extractor = LLMExtractor(client, config)
        records = [self._record("rec:a", "x" * 50), self._record("rec:b", "x" * 800)]
        extractor.extract_batch(records)
        call = fake.models.calls[-1]
        self.assertIn("--- Turn 0 ---", _user_text(call))
        self.assertIn("--- Turn 1 ---", _user_text(call))
        expected = (
            config.extractor_max_tokens_tier_short
            + config.extractor_max_tokens_tier_medium
        )
        self.assertEqual(call["config"].max_output_tokens, expected)


if __name__ == "__main__":
    unittest.main()
