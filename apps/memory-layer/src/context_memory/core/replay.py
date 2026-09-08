"""Phase 8: replay half of the step journal. `ReplayingLLMClient` is the
`LLMClient`-shaped stand-in `Deterministic*`/`InMemory*`/`RecordingGraphTransport`
fakes in `ingestion/fakes.py` don't have a counterpart for -- it drives real
adapter code (`LLMExtractor`, `AnswerReader`, `QueryRewriter`, ...) against
*actually-recorded* provider output instead of a hand-authored fixture, so a
production run's real behavior becomes a deterministic, no-LLM regression
test without hand-reconstructing what the model said.

Fixture format (see `export_journal_fixture`/`load_journal_fixture`): a
plain JSON object, portable and diffable, no live Postgres/journal needed
to replay from one -- exactly the "layer-isolated" no-LLM test the harness
plan calls for.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from context_memory.core.journal import hash_request


class ReplayMissError(RuntimeError):
    """No recorded step matches this call. Never falls through to a live
    call -- a silent fallback would defeat the whole point of "zero LLM
    calls, guaranteed," turning a hard regression-test failure into a
    passing test that quietly hit the network instead."""


class ReplayedError(RuntimeError):
    """§10 fix: a recorded step whose real run ended in an error is now
    genuinely replayable -- this carries the original `error_message`
    forward instead of `ReplayMissError` masking "we recorded a failure" as
    "we never recorded this call at all". Regression tests that need to
    exercise error-handling paths (a retryable extraction failure, a
    provider timeout) can now do so against a real recorded failure,
    exactly the same way a success replays against a real recorded
    response."""


@dataclass(frozen=True)
class RecordedStep:
    step_type: str
    call_role: str | None
    idempotency_key: str
    model_name: str | None
    response_payload: dict[str, Any] | None
    outcome: str
    # §10 fix: populated for outcome="error" steps, which used to be
    # dropped by export_journal_fixture entirely.
    error_message: str | None = None


def load_journal_fixture(path: str | Path) -> dict[tuple[str, str], list[RecordedStep]]:
    """Loads a fixture written by `export_journal_fixture` (or
    `scripts/export_journal_fixture.py`) into `(step_type, idempotency_key)
    -> [RecordedStep, ...]`, oldest first (the file's own `created_at`
    order, preserved by `export_journal_fixture`'s `ORDER BY`).

    §10 fix: a list, not a single `RecordedStep` -- two calls sharing a
    fingerprint (a prompt legitimately retried twice in one request) used
    to collapse into whichever the dict-comprehension saw last. Journal
    storage stopped deduplicating by fingerprint for the same reason (see
    `StepJournal.record`'s comment); replay's lookup side has to stop
    doing it too, or a fixture accurately recording two distinct calls
    would still only ever replay one of them. `ReplayingLLMClient._lookup`
    consumes this list front-to-back, one call in program order per
    recorded occurrence."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    fixture: dict[tuple[str, str], list[RecordedStep]] = {}
    for row in raw["steps"]:
        step = RecordedStep(
            step_type=row["step_type"],
            call_role=row.get("call_role"),
            idempotency_key=row["idempotency_key"],
            model_name=row.get("model_name"),
            response_payload=row.get("response_payload"),
            outcome=row["outcome"],
            error_message=row.get("error_message"),
        )
        fixture.setdefault((step.step_type, step.idempotency_key), []).append(step)
    return fixture


def export_journal_fixture(
    connection: object, *, correlation_id: str, path: str | Path
) -> int:
    """Exports every `journal_steps` row for one recorded request/turn
    (`correlation_id`) to a fixture file. Returns the row count written.
    This is the "production failures become regression tests without
    manual reconstruction" half -- point it at the correlation_id of a real
    run (from a trace, or `journal_steps` directly) and commit the result.

    §10 fix: was `AND outcome = 'ok'` -- a recorded failure (a provider
    timeout, a malformed structured response) never made it into the
    fixture at all, so replay could only ever reproduce a run's happy
    path, never the error handling around it. Every step is exported now;
    `ReplayingLLMClient` re-raises a recorded error deterministically
    (`ReplayedError`) instead of silently having nothing to replay it with.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT step_type, call_role, idempotency_key, model_name, response_payload, outcome, error_message "
            "FROM journal_steps WHERE correlation_id = %s ORDER BY created_at",
            (correlation_id,),
        )
        rows = cursor.fetchall()
    steps = [
        {
            "step_type": step_type,
            "call_role": call_role,
            "idempotency_key": idempotency_key,
            "model_name": model_name,
            "response_payload": response_payload,
            "outcome": outcome,
            "error_message": error_message,
        }
        for step_type, call_role, idempotency_key, model_name, response_payload, outcome, error_message in rows
    ]
    Path(path).write_text(
        json.dumps(
            {"correlation_id": correlation_id, "steps": steps}, indent=2, sort_keys=True
        ),
        encoding="utf-8",
    )
    return len(steps)


class ReplayingLLMClient:
    """Stands in for one specific role's `LLMClient` (e.g. "the reader
    client"), backed by a loaded fixture instead of a network connection.
    `model` mirrors a real client's own attribute -- `JournaledLLMClient`'s
    `getattr(self._inner, "model", None)` reads it the same way, so a
    `ReplayingLLMClient` composes with journaling unchanged if ever needed."""

    def __init__(
        self,
        fixture: dict[tuple[str, str], list[RecordedStep]],
        call_role: str,
        model: str,
    ) -> None:
        self._fixture = fixture
        self._call_role = call_role
        self.model = model

    def _lookup(self, step_type: str, idempotency_key: str) -> RecordedStep:
        """§10 fix: pops the OLDEST unconsumed occurrence for this exact
        (step_type, idempotency_key) -- a second identical call within one
        replay run gets the second recording, not a repeat of the first.
        A recorded `outcome="error"` step is a real match (this exact call
        WAS made and DID fail) -- raises `ReplayedError` with the original
        message rather than `ReplayMissError`, which means "never recorded
        at all"."""
        steps = self._fixture.get((step_type, idempotency_key))
        if not steps:
            raise ReplayMissError(
                f"no recorded {step_type} step for idempotency_key={idempotency_key!r}"
            )
        step = steps.pop(0)
        if step.outcome != "ok":
            raise ReplayedError(
                step.error_message
                or f"recorded {step_type} step failed with no error_message"
            )
        return step

    def structured_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[BaseModel],
        **_: Any,
    ) -> BaseModel:
        schema_name = response_schema.__name__
        step_type = f"llm.structured_completion[{schema_name}]"
        idempotency_key = hash_request(
            self._call_role, self.model, system_prompt, user_prompt, schema_name
        )
        step = self._lookup(step_type, idempotency_key)
        return response_schema.model_validate(step.response_payload)

    def text_completion(
        self, system_prompt: str, user_prompt: str, *_: Any, **__: Any
    ) -> str:
        step_type = "llm.text_completion"
        idempotency_key = hash_request(
            self._call_role, self.model, system_prompt, user_prompt
        )
        step = self._lookup(step_type, idempotency_key)
        payload = step.response_payload or {}
        return payload.get("text", "")

    def chat_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        **_: Any,
    ) -> Any:
        """§10 fix: tool calls were entirely unreplayable before this --
        `ReplayingLLMClient` had no method at all, so anything driving a
        tool-calling loop against a fixture hit an `AttributeError` instead
        of a clean, diagnosable replay miss. Reconstructs the minimal
        response shape `JournaledLLMClient.chat_with_tools`'s callers read
        (`response.choices[0].message.content`/`.tool_calls[].function.
        name`/`.arguments`) from the journaled `response_payload`."""
        step_type = "llm.chat_with_tools"
        idempotency_key = hash_request(
            self._call_role,
            self.model,
            json.dumps(messages, sort_keys=True),
            json.dumps(tools or [], sort_keys=True),
        )
        step = self._lookup(step_type, idempotency_key)
        payload = step.response_payload or {}
        return _ReplayedChatResponse(payload)


class _ReplayedFunctionCall:
    def __init__(self, name: str, arguments: str) -> None:
        self.name = name
        self.arguments = arguments


class _ReplayedToolCall:
    def __init__(self, raw: dict[str, Any]) -> None:
        self.id = raw.get("id")
        self.function = _ReplayedFunctionCall(
            raw.get("name", ""), raw.get("arguments", "")
        )


class _ReplayedMessage:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.content = payload.get("content")
        self.tool_calls = [
            _ReplayedToolCall(tc) for tc in (payload.get("tool_calls") or [])
        ]


class _ReplayedChoice:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.message = _ReplayedMessage(payload)


class _ReplayedChatResponse:
    """Just enough of the OpenAI SDK's `ChatCompletion` shape for
    `chat_with_tools` callers to read -- see `JournaledLLMClient.
    chat_with_tools`'s `response_payload` construction for the exact
    fields this reconstructs."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self.choices = [_ReplayedChoice(payload)]
