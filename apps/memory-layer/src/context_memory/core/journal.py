"""Phase 5: the step journal. Records every LLM call with its inputs, outputs,
timing, and an idempotency key, at the one seam every such call already passes
through -- `LLMClient.structured_completion`/`.text_completion`.

`JournaledLLMClient` wraps by composition, not inheritance: it satisfies the
same duck-typed two-method shape every call site already uses, so wrapping
happens once, in `composition.py`, and nothing else in the codebase changes.
"""

from __future__ import annotations

import contextvars
import json
import threading
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Literal

from opentelemetry.semconv._incubating.attributes import gen_ai_attributes
from opentelemetry.trace import Status, StatusCode
from pydantic import BaseModel

from context_memory.core.logging import get_logger
from context_memory.core.tracing import get_tracer

logger = get_logger(__name__)

_correlation_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("correlation_id", default=None)


@dataclass(frozen=True)
class JournalContext:
    """The identifiers a caller threads through `StepJournal.record` beyond
    the step's own request/response. All optional -- background ingestion may
    not know a `turn_index` yet, a bare CLI run may have no `session_id`.

    Phase 9: `scenario_id` is the coarser of two tenancy levels -- which
    game/campaign template a playthrough belongs to. `context_id` already
    *is* the finer level (one playthrough's own memory space -- unchanged
    from how it's used everywhere else in this codebase); `scenario_id`
    adds "every playthrough of scenario X" as a queryable, auditable axis
    without touching fact currency/supersession semantics at all, unlike
    Phase 6's `branch_id` question -- this is pure identity/audit, not a
    second timeline."""

    context_id: str | None = None
    session_id: str | None = None
    turn_index: int | None = None
    scenario_id: str | None = None


_EMPTY_CONTEXT = JournalContext()
_journal_context: contextvars.ContextVar[JournalContext] = contextvars.ContextVar("journal_context", default=_EMPTY_CONTEXT)


def hash_request(*parts: str) -> str:
    """Deterministic idempotency key for a logical step. `\\x1f` (unit
    separator) joins parts rather than a printable character, so no part's own
    content can forge a different key by embedding the join sequence.

    Deliberately NOT extended to include temperature/max_tokens/timeout/
    max_retries alongside the prompts (§10 gap: "request fingerprint omits
    several effective parameters") -- doing so would silently invalidate
    every already-committed replay fixture (`benchmarks/fixtures/*.json`),
    whose stored `idempotency_key` values were computed against this exact
    formula at record time. Journal storage no longer treats this as a
    uniqueness constraint at all (see `StepJournal.record`), which is what
    actually mattered: two calls differing only in one of those parameters
    now both get their own row instead of the second being silently
    dropped, without needing the key itself to change shape."""
    return sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


def current_correlation() -> str | None:
    return _correlation_id.get()


def current_journal_context() -> JournalContext:
    return _journal_context.get()


@contextmanager
def correlation_scope(context: JournalContext | None = None, *, existing: str | None = None) -> Iterator[str]:
    """One correlation id (and one `JournalContext`) per logical request/turn.
    Reuses the ambient values if already inside a scope (e.g. `search_memories`
    called from within `generate_reply`) rather than minting new ones --
    nesting scopes share state, they don't fork it. `JournaledLLMClient` reads
    `current_journal_context()`/`current_correlation()` at call time, since it
    can't accept extra params without breaking the plain `LLMClient` shape it
    stands in for.

    Phase 7: also opens the root OTel span for this request/turn, when a
    real tracer is configured (`tracing.configure_tracing`) -- a no-op
    span otherwise. `StepJournal.record`'s per-step spans become children of
    it automatically: OTel's own Python context propagation rides on the
    same `contextvars` this correlation id already uses, including across
    the `contextvars.copy_context()` hops `engine.py`/`retrieval/engine.py`
    use for background-thread/concurrent-pool work.
    """
    if _correlation_id.get() is not None:
        yield _correlation_id.get()  # type: ignore[misc]
        return
    correlation_id = existing or uuid.uuid4().hex
    correlation_token = _correlation_id.set(correlation_id)
    context_token = _journal_context.set(context or _EMPTY_CONTEXT)
    span_attributes: dict[str, Any] = {"mem1.correlation_id": correlation_id}
    if context is not None:
        if context.context_id:
            span_attributes["mem1.context_id"] = context.context_id
        if context.session_id:
            span_attributes["mem1.session_id"] = context.session_id
        if context.scenario_id:
            span_attributes["mem1.scenario_id"] = context.scenario_id
    try:
        with get_tracer().start_as_current_span("mem1.request", attributes=span_attributes):
            yield correlation_id
    finally:
        _correlation_id.reset(correlation_token)
        _journal_context.reset(context_token)


class StepJournal:
    """One table, one adapter -- no backend registry. `record` never raises
    into the caller: a journal outage must never break a real request, the
    same posture `timed_operation` already takes for logging.

    `_lock` serializes access to `_connection`: Phase 0's temporal
    resolver and query rewriter already run concurrently (their own
    `ThreadPoolExecutor`, since Track A), and a psycopg `Connection` is not
    safe for concurrent use from multiple threads without external
    synchronization -- confirmed live, not theoretical: an unserialized
    30-instance oracle run journaled only ~7 of the ~30 real, distinct
    calls per role, with zero raised exceptions to explain the gap (a data
    race, not a crash). One lock around the insert costs nothing an audit
    log's write volume would ever notice."""

    def __init__(self, connection: object) -> None:
        self._connection = connection
        self._lock = threading.Lock()

    def record(
        self,
        *,
        step_type: str,
        call_role: str | None,
        idempotency_key: str,
        request_payload: dict[str, Any],
        response_payload: dict[str, Any] | None,
        outcome: Literal["ok", "error"],
        elapsed_ms: float,
        model_name: str | None = None,
        error_message: str | None = None,
        context: JournalContext | None = None,
    ) -> str | None:
        context = context or current_journal_context()
        correlation_id = current_correlation() or uuid.uuid4().hex
        step_id = uuid.uuid4().hex
        self._emit_span(
            step_type=step_type, call_role=call_role, idempotency_key=idempotency_key,
            model_name=model_name, outcome=outcome, error_message=error_message,
            elapsed_ms=elapsed_ms, context=context, correlation_id=correlation_id,
        )
        try:
            with self._lock, self._connection.transaction():
                with self._connection.cursor() as cursor:
                    # §10 fix: was `ON CONFLICT (step_type, idempotency_key)
                    # DO NOTHING` -- a real unique constraint on the request
                    # FINGERPRINT, not the event. Two genuinely distinct
                    # calls (different correlation_id/request, or the same
                    # prompt legitimately retried twice within one request)
                    # that happen to hash to the same idempotency_key
                    # silently lost every occurrence after the first, with
                    # no error and no trace it happened. `step_id` (the
                    # actual PRIMARY KEY, a fresh uuid4 every call) is
                    # already a real, collision-free event identity -- this
                    # table is append-only now, one row per call, always.
                    # `idempotency_key` stays a queryable fingerprint column
                    # (still indexed, just no longer unique) for finding
                    # "calls that were the same request", not for silently
                    # merging them.
                    cursor.execute(
                        """
                        INSERT INTO journal_steps (
                            step_id, correlation_id, context_id, session_id, turn_index, scenario_id,
                            step_type, call_role, idempotency_key, model_name,
                            request_payload, response_payload, outcome, error_message, elapsed_ms
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (step_id) DO NOTHING
                        """,
                        (
                            step_id, correlation_id, context.context_id, context.session_id, context.turn_index,
                            context.scenario_id,
                            step_type, call_role, idempotency_key, model_name,
                            json.dumps(request_payload, sort_keys=True),
                            json.dumps(response_payload, sort_keys=True) if response_payload is not None else None,
                            outcome, error_message, elapsed_ms,
                        ),
                    )
            return step_id
        except Exception as error:
            logger.warning("journal_steps insert failed for %s (%s): %s", step_type, idempotency_key, error)
            return None

    @staticmethod
    def _emit_span(
        *, step_type: str, call_role: str | None, idempotency_key: str, model_name: str | None,
        outcome: Literal["ok", "error"], error_message: str | None, elapsed_ms: float,
        context: JournalContext, correlation_id: str,
    ) -> None:
        """Reconstructs a span after the fact from data `record()` already
        has -- no separate span-per-call-site instrumentation to keep in
        sync. Tracing failures are swallowed here the same way a journal
        outage is: never break the request for observability."""
        try:
            attributes: dict[str, Any] = {
                "mem1.step_type": step_type, "mem1.correlation_id": correlation_id, "mem1.idempotency_key": idempotency_key,
            }
            if call_role:
                attributes["mem1.call_role"] = call_role
            if context.context_id:
                attributes["mem1.context_id"] = context.context_id
            if context.session_id:
                attributes["mem1.session_id"] = context.session_id
            if context.scenario_id:
                attributes["mem1.scenario_id"] = context.scenario_id
            if model_name:
                attributes[gen_ai_attributes.GEN_AI_REQUEST_MODEL] = model_name
            span_name = step_type
            if step_type.startswith("llm."):
                attributes[gen_ai_attributes.GEN_AI_OPERATION_NAME] = gen_ai_attributes.GenAiOperationNameValues.CHAT.value
                # `GEN_AI_PROVIDER_NAME` isn't exported by this repo's pinned
                # opentelemetry-semantic-conventions floor (0.48b0) -- it's an
                # `_incubating` module, so the constant name isn't stable
                # across versions even though the wire attribute is. Use the
                # literal so this doesn't require bumping the dependency.
                attributes["gen_ai.provider.name"] = "gemini"
                span_name = f"chat {model_name}" if model_name else "chat"

            end_ns = time.time_ns()
            start_ns = end_ns - int(elapsed_ms * 1_000_000)
            span = get_tracer().start_span(span_name, start_time=start_ns, attributes=attributes)
            span.set_status(Status(StatusCode.ERROR, error_message or "") if outcome == "error" else Status(StatusCode.OK))
            span.end(end_time=end_ns)
        except Exception as error:
            logger.warning("span emission failed for %s (%s): %s", step_type, idempotency_key, error)


class JournaledLLMClient:
    """Wraps an `LLMClient`-shaped object; records every call to `journal`
    before returning. Composition, not inheritance -- `inner` keeps its own
    already-built SDK client, retry policy, and model config untouched."""

    def __init__(self, inner: Any, journal: StepJournal, call_role: str) -> None:
        self._inner = inner
        self._journal = journal
        self._call_role = call_role

    def structured_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[BaseModel],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        timeout: float | None = None,
        max_retries: int = 1,
    ) -> BaseModel:
        schema_name = response_schema.__name__
        step_type = f"llm.structured_completion[{schema_name}]"
        model_name = getattr(self._inner, "model", None)
        idempotency_key = hash_request(self._call_role, model_name or "", system_prompt, user_prompt, schema_name)
        request_payload = {"system_prompt": system_prompt, "user_prompt": user_prompt, "schema": schema_name}

        start = time.monotonic()
        try:
            result = self._inner.structured_completion(
                system_prompt, user_prompt, response_schema,
                temperature=temperature, max_tokens=max_tokens, timeout=timeout, max_retries=max_retries,
            )
        except Exception as error:
            self._journal.record(
                step_type=step_type, call_role=self._call_role, idempotency_key=idempotency_key,
                request_payload=request_payload, response_payload=None, outcome="error",
                elapsed_ms=(time.monotonic() - start) * 1000, model_name=model_name, error_message=str(error),
            )
            raise
        self._journal.record(
            step_type=step_type, call_role=self._call_role, idempotency_key=idempotency_key,
            request_payload=request_payload, response_payload=result.model_dump(mode="json"), outcome="ok",
            elapsed_ms=(time.monotonic() - start) * 1000, model_name=model_name,
        )
        return result

    def text_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        *,
        max_tokens: int | None = None,
        timeout: float | None = None,
    ) -> str:
        step_type = "llm.text_completion"
        model_name = getattr(self._inner, "model", None)
        idempotency_key = hash_request(self._call_role, model_name or "", system_prompt, user_prompt)
        request_payload = {"system_prompt": system_prompt, "user_prompt": user_prompt}

        start = time.monotonic()
        try:
            result = self._inner.text_completion(
                system_prompt, user_prompt, temperature, max_tokens=max_tokens, timeout=timeout,
            )
        except Exception as error:
            self._journal.record(
                step_type=step_type, call_role=self._call_role, idempotency_key=idempotency_key,
                request_payload=request_payload, response_payload=None, outcome="error",
                elapsed_ms=(time.monotonic() - start) * 1000, model_name=model_name, error_message=str(error),
            )
            raise
        self._journal.record(
            step_type=step_type, call_role=self._call_role, idempotency_key=idempotency_key,
            request_payload=request_payload, response_payload={"text": result}, outcome="ok",
            elapsed_ms=(time.monotonic() - start) * 1000, model_name=model_name,
        )
        return result

    def chat_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> Any:
        step_type = "llm.chat_with_tools"
        model_name = getattr(self._inner, "model", None)
        idempotency_key = hash_request(
            self._call_role, model_name or "", json.dumps(messages, sort_keys=True), json.dumps(tools or [], sort_keys=True)
        )
        request_payload = {"messages": messages, "tools": tools}

        start = time.monotonic()
        try:
            response = self._inner.chat_with_tools(messages, tools, **kwargs)
        except Exception as error:
            self._journal.record(
                step_type=step_type, call_role=self._call_role, idempotency_key=idempotency_key,
                request_payload=request_payload, response_payload=None, outcome="error",
                elapsed_ms=(time.monotonic() - start) * 1000, model_name=model_name, error_message=str(error),
            )
            raise
        message = response.choices[0].message
        response_payload = {
            "content": message.content,
            "tool_calls": [
                {"id": tc.id, "name": tc.function.name, "arguments": tc.function.arguments}
                for tc in (message.tool_calls or [])
            ],
        }
        self._journal.record(
            step_type=step_type, call_role=self._call_role, idempotency_key=idempotency_key,
            request_payload=request_payload, response_payload=response_payload, outcome="ok",
            elapsed_ms=(time.monotonic() - start) * 1000, model_name=model_name,
        )
        return response
