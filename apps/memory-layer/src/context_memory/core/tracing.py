"""Phase 7: OTel tracing. No custom SDK, no parallel instrumentation path --
spans are read off the standard `OTEL_EXPORTER_OTLP_ENDPOINT`/
`OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` env vars the OTel SDK itself already
knows how to read, and are emitted from the two places that already gather
everything a span needs: `journal.correlation_scope` (one span per logical
request/turn) and `journal.StepJournal.record` (one child span per step,
reusing the exact timing/outcome/metadata already assembled for the journal
row). No endpoint configured -> the SDK's own no-op tracer, zero behavior
change, same posture as every other opt-in feature this session.
"""

from __future__ import annotations

import os

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider

_TRACER_NAME = "mem1"
_configured = False


def configure_tracing(service_name: str = "mem1") -> bool:
    """Call once, at process startup (`composition.build_memory_engine`).
    Returns whether a real exporter was configured. Idempotent -- a second
    call is a no-op, so tests/CLI tools that build multiple engines in one
    process never register more than one `TracerProvider`."""
    global _configured
    if _configured:
        return isinstance(trace.get_tracer_provider(), TracerProvider)
    _configured = True

    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT") or os.getenv(
        "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"
    )
    if not endpoint:
        return False

    # Imported lazily -- only touches the exporter/protobuf/requests stack
    # when an endpoint is actually configured.
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)
    return True


def get_tracer() -> trace.Tracer:
    return trace.get_tracer(_TRACER_NAME)
