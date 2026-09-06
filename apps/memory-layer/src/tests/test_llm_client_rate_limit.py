from __future__ import annotations

import json
import unittest
from unittest import mock

from google.genai import types
from pydantic import BaseModel

from context_memory.core.llm_client import (
    LLMClient,
    _is_rate_limit_error,
    _rate_limit_delay,
)


class _Schema(BaseModel):
    ok: bool


def _text_response(text: str, finish_reason=types.FinishReason.STOP) -> types.GenerateContentResponse:
    return types.GenerateContentResponse(
        candidates=[types.Candidate(
            content=types.Content(role="model", parts=[types.Part(text=text)]),
            finish_reason=finish_reason,
        )],
        usage_metadata=types.GenerateContentResponseUsageMetadata(
            prompt_token_count=1, candidates_token_count=1, total_token_count=2,
        ),
    )


class _FakeQuotaError(Exception):
    """Mimics `google.genai.errors.APIError`'s real shape (`.code`, `.status`,
    `.details`) -- what `_is_rate_limit_error`/`_rate_limit_delay` actually
    read. The real class can't be constructed without a live httpx response."""

    def __init__(self, message: str, code: int = 429, status: str = "RESOURCE_EXHAUSTED", details=None) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.details = details or {}


_STATED_DELAY_DETAILS = {"error": {"details": [{"retryDelay": "4.995s"}]}}


class _FakeModels:
    """Raises rate-limit errors for the first `fail_times` calls, then
    returns `response` (or calls `response_factory()` fresh each time, for
    tests that need a callable behavior swap mid-test)."""

    def __init__(self, response=None, response_factory=None, fail_times: int = 0, error: Exception | None = None) -> None:
        self.response = response
        self.response_factory = response_factory
        self.fail_times = fail_times
        self.error = error or _FakeQuotaError("rate limited")
        self.calls = 0
        self.last_contents = None
        self.last_config = None

    def generate_content(self, *, model, contents, config):
        self.calls += 1
        self.last_contents = contents
        self.last_config = config
        if self.calls <= self.fail_times:
            raise self.error
        return self.response_factory() if self.response_factory is not None else self.response


class _FakeClient:
    def __init__(self, models: _FakeModels) -> None:
        self.models = models


def _client(models: _FakeModels, **kwargs) -> LLMClient:
    return LLMClient(api_key="k", model_name="m", client=_FakeClient(models), **kwargs)


class RateLimitRetryTests(unittest.TestCase):
    def test_parses_provider_stated_retry_delay(self) -> None:
        # A structured RetryInfo-shaped hint in the error's own `details` --
        # honoring it beats blind backoff.
        error = _FakeQuotaError("rate limited", details=_STATED_DELAY_DETAILS)
        delay = _rate_limit_delay(error, attempt=0)
        self.assertGreaterEqual(delay, 4.995)
        self.assertLess(delay, 5.6)  # stated delay + jitter only

    def test_falls_back_to_exponential_backoff_without_stated_delay(self) -> None:
        delay = _rate_limit_delay(_FakeQuotaError("429 too many requests"), attempt=3)
        self.assertGreaterEqual(delay, 8.0)  # 2**3
        self.assertLess(delay, 9.0)

    def test_delay_is_capped(self) -> None:
        self.assertLessEqual(_rate_limit_delay(_FakeQuotaError("nope"), attempt=20), 60.0)

    def test_identifies_rate_limit_by_code_or_status(self) -> None:
        self.assertTrue(_is_rate_limit_error(_FakeQuotaError("x", code=429, status="RESOURCE_EXHAUSTED")))
        self.assertTrue(_is_rate_limit_error(_FakeQuotaError("x", code=200, status="RESOURCE_EXHAUSTED")))
        self.assertFalse(_is_rate_limit_error(Exception("boom")))

    def test_retries_then_succeeds(self) -> None:
        """A 429 raises out of .generate_content() and so never reached the
        empty-content retry loop -- rate-limited calls previously failed
        outright, silently dropping a turn's facts."""
        models = _FakeModels(response=_text_response(json.dumps({"ok": True})), fail_times=2)
        client = _client(models, rate_limit_max_retries=5)
        with mock.patch("context_memory.core.llm_client.time.sleep") as sleep:
            result = client.structured_completion("sys", "usr", _Schema)
        self.assertTrue(result.ok)
        self.assertEqual(models.calls, 3)
        self.assertEqual(sleep.call_count, 2)

    def test_gives_up_after_max_retries(self) -> None:
        models = _FakeModels(response=_text_response(json.dumps({"ok": True})), fail_times=99)
        client = _client(models, rate_limit_max_retries=2)
        with mock.patch("context_memory.core.llm_client.time.sleep"):
            with self.assertRaises(_FakeQuotaError):
                client.structured_completion("sys", "usr", _Schema)
        self.assertEqual(models.calls, 3)  # initial + 2 retries

    def test_non_rate_limit_error_is_not_retried(self) -> None:
        """Only rate limiting should be retried here; anything else must surface
        immediately rather than being slowly retried against a real provider."""
        models = _FakeModels(response=_text_response(json.dumps({"ok": True})), fail_times=99, error=ValueError("bad request"))
        client = _client(models, rate_limit_max_retries=5)
        with mock.patch("context_memory.core.llm_client.time.sleep") as sleep:
            with self.assertRaises(ValueError):
                client.structured_completion("sys", "usr", _Schema)
        self.assertEqual(models.calls, 1)
        sleep.assert_not_called()

    def test_text_completion_also_retries(self) -> None:
        models = _FakeModels(response=_text_response("ok answer"), fail_times=1)
        client = _client(models, rate_limit_max_retries=3)
        with mock.patch("context_memory.core.llm_client.time.sleep"):
            out = client.text_completion("sys", "usr")
        self.assertEqual(models.calls, 2)
        self.assertIn("ok", out)


class SchemaCompactionTests(unittest.TestCase):
    """The schema blob rides on every call and the prior provider (pre-
    migration) reported no prompt caching (verified: identical prompts
    billed at full price twice, no `cached_tokens` field), so nothing
    amortizes it -- under a tokens-per-minute limit its size is throughput,
    not cosmetics."""

    def test_typedef_is_substantially_smaller_than_json_schema(self) -> None:
        from context_memory.core.llm_client import _compact_schema_json, _compact_schema_typedef
        from context_memory.ingestion.model_adapters import _FactExtractionResponse

        raw = json.dumps(_FactExtractionResponse.model_json_schema())
        compact = _compact_schema_json(_FactExtractionResponse)
        typedef = _compact_schema_typedef(_FactExtractionResponse)
        self.assertLess(len(compact), len(raw))
        self.assertLess(len(typedef), len(compact))
        self.assertLess(len(typedef), len(raw) * 0.4)  # measured ~73% reduction

    def test_typedef_renders_enums_optionals_lists_and_nesting(self) -> None:
        from context_memory.core.llm_client import _compact_schema_typedef
        from context_memory.ingestion.model_adapters import _FactExtractionResponse

        out = _compact_schema_typedef(_FactExtractionResponse)
        self.assertIn('action "ADD" | "UPDATE" | "DELETE"', out)   # Literal -> union
        self.assertIn("predicate_key string?", out)                 # Optional -> ?
        self.assertIn("entities string[]", out)                     # list -> []
        self.assertIn("facts ExtractedFactItem[]", out)             # nested model ref
        self.assertIn("class ExtractedFactItem {", out)             # nested block emitted
        # The leading underscore is a Python visibility convention with no
        # meaning to the model; it must not be spent as prompt tokens.
        self.assertNotIn("_ExtractedFactItem", out)

    def test_json_schema_strips_only_noise_keys(self) -> None:
        from context_memory.core.llm_client import _compact_schema_json
        from context_memory.ingestion.model_adapters import _FactExtractionResponse

        compact = json.loads(_compact_schema_json(_FactExtractionResponse))
        item = compact["$defs"]["_ExtractedFactItem"]
        self.assertNotIn("title", item)
        # Constraints the model actually needs must survive.
        self.assertEqual(item["properties"]["action"]["enum"], ["ADD", "UPDATE", "DELETE"])
        self.assertEqual(item["required"], ["text"])

    def test_both_formats_are_cached_per_schema_class(self) -> None:
        from context_memory.core.llm_client import _compact_schema_json, _compact_schema_typedef
        from context_memory.ingestion.model_adapters import _FactExtractionResponse

        self.assertIs(_compact_schema_typedef(_FactExtractionResponse),
                      _compact_schema_typedef(_FactExtractionResponse))
        self.assertIs(_compact_schema_json(_FactExtractionResponse),
                      _compact_schema_json(_FactExtractionResponse))

    def test_schema_format_selects_representation(self) -> None:
        models = _FakeModels(response_factory=lambda: _text_response(json.dumps({"ok": True})))
        client = _client(models, schema_format="typedef")
        client.structured_completion("sys", "usr", _Schema)
        sent = models.last_config.system_instruction
        self.assertIn("class Schema {", sent)
        self.assertNotIn('"properties"', sent)

        models2 = _FakeModels(response_factory=lambda: _text_response(json.dumps({"ok": True})))
        client2 = _client(models2, schema_format="json_schema")
        client2.structured_completion("sys", "usr", _Schema)
        sent2 = models2.last_config.system_instruction
        self.assertIn('"properties"', sent2)


class JsonRecoveryTests(unittest.TestCase):
    """`response_mime_type: application/json` does not guarantee a clean
    body. Observed live pre-migration, deterministically (6/6 calls), from
    a different provider's model: a spurious `{"` prefix, i.e.
    `{"{"facts":[...]}`. Kept as a defensive pass after the Vertex AI
    migration too, since a model can still wrap JSON in a markdown fence
    depending on the prompt."""

    def test_recovers_bedrock_quote_brace_prefix(self) -> None:
        from context_memory.core.llm_client import _recover_json_object
        out = _recover_json_object('{"{"facts":[{"text":"a"}]}')
        self.assertEqual(json.loads(out), {"facts": [{"text": "a"}]})

    def test_recovers_fences_prose_and_double_brace(self) -> None:
        from context_memory.core.llm_client import _recover_json_object
        for raw in (
            '```json\n{"ok":true}\n```',
            'Here you go:\n{"ok":true}',
            '{"ok":true}\nHope that helps!',
            '{{"ok":true}',
        ):
            self.assertEqual(json.loads(_recover_json_object(raw)), {"ok": True}, raw)

    def test_clean_json_is_returned_unchanged(self) -> None:
        from context_memory.core.llm_client import _recover_json_object
        clean = '{"facts":[{"text":"a"}]}'
        self.assertEqual(_recover_json_object(clean), clean)

    def test_unrecoverable_text_falls_through_to_error_path(self) -> None:
        """Must return the input rather than raise, so the caller still reports
        the real provider output instead of a recovery-layer error."""
        from context_memory.core.llm_client import _recover_json_object
        self.assertEqual(_recover_json_object("no json at all"), "no json at all")

    def test_malformed_response_is_parsed_end_to_end(self) -> None:
        models = _FakeModels(response=_text_response('{"{"ok":true}'))
        client = _client(models)
        self.assertTrue(client.structured_completion("sys", "usr", _Schema).ok)


if __name__ == "__main__":
    unittest.main()
