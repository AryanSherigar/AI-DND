from __future__ import annotations

import unittest

from context_memory.core.config import Config


class PerRoleReasoningEffortTests(unittest.TestCase):
    """`Config.get_entity_resolution_client`'s own reasoning_effort,
    separate from the global `llm_reasoning_effort` -- added because two
    models behind the same endpoint can accept disjoint reasoning-effort
    enums (confirmed live: `qwen.qwen3-32b` accepts "none",
    `openai.gpt-oss-20b` rejects it and only accepts low/medium/high)."""

    def test_empty_override_falls_back_to_global_reasoning_effort(self) -> None:
        config = Config(
            llm_reasoning_effort="low", entity_resolution_reasoning_effort=""
        )
        client = config.get_entity_resolution_client()
        self.assertEqual(client.reasoning_effort, "low")

    def test_role_specific_override_wins_over_global(self) -> None:
        config = Config(
            llm_reasoning_effort="low", entity_resolution_reasoning_effort="none"
        )
        client = config.get_entity_resolution_client()
        self.assertEqual(client.reasoning_effort, "none")

    def test_other_role_clients_are_unaffected_by_entity_resolution_override(
        self,
    ) -> None:
        config = Config(
            llm_reasoning_effort="low", entity_resolution_reasoning_effort="none"
        )
        extractor_client = config.get_extractor_client()
        reader_client = config.get_reader_client()
        self.assertEqual(extractor_client.reasoning_effort, "low")
        self.assertEqual(reader_client.reasoning_effort, "low")

    def test_entity_resolution_model_is_independently_overridable_from_extractor_model(
        self,
    ) -> None:
        config = Config(
            extractor_model="openai.gpt-oss-20b",
            entity_resolution_model="qwen.qwen3-32b",
        )
        entity_client = config.get_entity_resolution_client()
        extractor_client = config.get_extractor_client()
        self.assertEqual(entity_client.model, "qwen.qwen3-32b")
        self.assertEqual(extractor_client.model, "openai.gpt-oss-20b")

    def test_temporal_resolver_and_query_rewriter_have_their_own_reasoning_effort_override(
        self,
    ) -> None:
        config = Config(
            llm_reasoning_effort="low",
            temporal_resolver_reasoning_effort="none",
            query_rewriter_reasoning_effort="none",
        )
        self.assertEqual(config.get_temporal_resolver_client().reasoning_effort, "none")
        self.assertEqual(config.get_query_rewriter_client().reasoning_effort, "none")
        # Unrelated roles stay on the global default.
        self.assertEqual(config.get_reader_client().reasoning_effort, "low")

    def test_temporal_resolver_and_query_rewriter_models_are_independently_overridable(
        self,
    ) -> None:
        config = Config(
            extractor_model="openai.gpt-oss-20b",
            temporal_resolver_model="qwen.qwen3-32b",
            query_rewriter_model="qwen.qwen3-32b",
        )
        self.assertEqual(config.get_temporal_resolver_client().model, "qwen.qwen3-32b")
        self.assertEqual(config.get_query_rewriter_client().model, "qwen.qwen3-32b")
        self.assertEqual(config.get_extractor_client().model, "openai.gpt-oss-20b")


class HarnessSnapshotTests(unittest.TestCase):
    """Phase 8: the config recorded with every eval run -- directly
    prevents the §4 bug class (a benchmark score measured with a different
    rerank model than production silently uses)."""

    def test_reflects_the_actual_configured_models(self) -> None:
        config = Config(
            reader_model="openai.gpt-oss-20b", rerank_model="qwen.qwen3-32b"
        )
        snapshot = config.harness_snapshot()
        self.assertEqual(snapshot["reader_model"], "openai.gpt-oss-20b")
        self.assertEqual(snapshot["rerank_model"], "qwen.qwen3-32b")

    def test_every_role_model_is_present(self) -> None:
        snapshot = Config().harness_snapshot()
        for key in (
            "extractor_model",
            "entity_resolution_model",
            "temporal_update_model",
            "reader_model",
            "temporal_resolver_model",
            "query_rewriter_model",
            "rerank_model",
        ):
            self.assertIn(key, snapshot)

    def test_is_json_serializable(self) -> None:
        import json

        json.dumps(Config().harness_snapshot())  # must not raise


if __name__ == "__main__":
    unittest.main()
