from __future__ import annotations

import unittest
from unittest.mock import patch

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from context_memory.core.journal import JournalContext, StepJournal, correlation_scope
from context_memory.core.tracing import configure_tracing


def _local_tracer():
    """A tracer backed by its own in-memory exporter, independent of the
    process-wide OTel provider -- avoids the well-known constraint that
    `trace.set_tracer_provider` only takes effect once per process, which
    would make tests order-dependent if they shared the real global one."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider.get_tracer("test"), exporter


class ConfigureTracingTests(unittest.TestCase):
    def test_returns_false_with_no_endpoint_configured(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            import context_memory.core.tracing as tracing_module

            tracing_module._configured = False
            self.assertFalse(configure_tracing())
            tracing_module._configured = False  # leave clean for other tests


class CorrelationScopeSpanTests(unittest.TestCase):
    def test_opens_root_span_with_correlation_and_context_attributes(self) -> None:
        tracer, exporter = _local_tracer()
        with patch("context_memory.core.journal.get_tracer", return_value=tracer):
            with correlation_scope(
                JournalContext(context_id="ctx-1", session_id="sess-1")
            ) as correlation_id:
                pass
        spans = exporter.get_finished_spans()
        self.assertEqual(len(spans), 1)
        span = spans[0]
        self.assertEqual(span.name, "mem1.request")
        self.assertEqual(span.attributes["mem1.correlation_id"], correlation_id)
        self.assertEqual(span.attributes["mem1.context_id"], "ctx-1")
        self.assertEqual(span.attributes["mem1.session_id"], "sess-1")

    def test_nested_scope_does_not_open_a_second_root_span(self) -> None:
        tracer, exporter = _local_tracer()
        with patch("context_memory.core.journal.get_tracer", return_value=tracer):
            with correlation_scope(JournalContext(context_id="ctx-1")):
                with correlation_scope(JournalContext(context_id="ctx-2")):
                    pass
        self.assertEqual(len(exporter.get_finished_spans()), 1)


class FakeCursor:
    def execute(self, *args, **kwargs) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return None


class FakeConnection:
    def cursor(self):
        return FakeCursor()

    def transaction(self):
        from contextlib import nullcontext

        return nullcontext()


class FakePool:
    """`StepJournal` acquires a connection per call via `pool.connection()`
    -- this just yields the same fake connection every time."""

    def __init__(self, connection: object) -> None:
        self._connection = connection

    def connection(self):
        from contextlib import nullcontext

        return nullcontext(self._connection)


class StepJournalSpanTests(unittest.TestCase):
    def test_llm_step_emits_chat_span_with_gen_ai_attributes(self) -> None:
        tracer, exporter = _local_tracer()
        journal = StepJournal(FakePool(FakeConnection()))
        with patch("context_memory.core.journal.get_tracer", return_value=tracer):
            journal.record(
                step_type="llm.text_completion",
                call_role="reader",
                idempotency_key="key-1",
                request_payload={},
                response_payload={"text": "hi"},
                outcome="ok",
                elapsed_ms=42.0,
                model_name="qwen.qwen3-32b",
                context=JournalContext(context_id="ctx-1"),
            )
        spans = exporter.get_finished_spans()
        self.assertEqual(len(spans), 1)
        span = spans[0]
        self.assertEqual(span.name, "chat qwen.qwen3-32b")
        self.assertEqual(span.attributes["gen_ai.operation.name"], "chat")
        self.assertEqual(span.attributes["gen_ai.provider.name"], "gemini")
        self.assertEqual(span.attributes["gen_ai.request.model"], "qwen.qwen3-32b")
        self.assertEqual(span.attributes["mem1.call_role"], "reader")
        self.assertEqual(span.status.status_code, StatusCode.OK)

    def test_error_outcome_sets_error_status(self) -> None:
        tracer, exporter = _local_tracer()
        journal = StepJournal(FakePool(FakeConnection()))
        with patch("context_memory.core.journal.get_tracer", return_value=tracer):
            journal.record(
                step_type="llm.text_completion",
                call_role="reader",
                idempotency_key="key-1",
                request_payload={},
                response_payload=None,
                outcome="error",
                elapsed_ms=5.0,
                error_message="provider down",
            )
        span = exporter.get_finished_spans()[0]
        self.assertEqual(span.status.status_code, StatusCode.ERROR)
        self.assertEqual(span.status.description, "provider down")

    def test_non_llm_step_omits_gen_ai_attributes(self) -> None:
        tracer, exporter = _local_tracer()
        journal = StepJournal(FakePool(FakeConnection()))
        with patch("context_memory.core.journal.get_tracer", return_value=tracer):
            journal.record(
                step_type="rollback.apply",
                call_role="rollback",
                idempotency_key="key-1",
                request_payload={},
                response_payload=None,
                outcome="ok",
                elapsed_ms=1.0,
            )
        span = exporter.get_finished_spans()[0]
        self.assertEqual(span.name, "rollback.apply")
        self.assertNotIn("gen_ai.operation.name", span.attributes)

    def test_span_emission_failure_never_raises(self) -> None:
        journal = StepJournal(FakePool(FakeConnection()))
        with patch(
            "context_memory.core.journal.get_tracer",
            side_effect=RuntimeError("exporter down"),
        ):
            step_id = journal.record(
                step_type="llm.text_completion",
                call_role="reader",
                idempotency_key="key-1",
                request_payload={},
                response_payload={"text": "hi"},
                outcome="ok",
                elapsed_ms=1.0,
            )
        self.assertIsNotNone(
            step_id
        )  # journaling still succeeded despite tracing failing


if __name__ == "__main__":
    unittest.main()
