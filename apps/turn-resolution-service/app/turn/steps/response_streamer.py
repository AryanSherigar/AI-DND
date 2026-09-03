"""Formats turn pipeline events as Server-Sent Events for the client.

Pure formatting only — this step never calls state_writer or any other step
directly; pipeline.py is the sole sequencer (CLAUDE.md).
"""

import json
from collections.abc import AsyncIterator

from sse_starlette.sse import EventSourceResponse, ServerSentEvent


def narration_event(chunk: str) -> ServerSentEvent:
    """Format one narration chunk as an SSE event."""
    return ServerSentEvent(event="narration", data=chunk)


def playthrough_ended_event(
    outcome_tag: str, outcome_title: str, outcome_text: str
) -> ServerSentEvent:
    """Format the end-of-playthrough outcome as an SSE event, emitted once,
    before the terminal done event, on the turn that matched an end condition."""
    return ServerSentEvent(
        event="playthrough_ended",
        data=json.dumps(
            {
                "outcome_tag": outcome_tag,
                "outcome_title": outcome_title,
                "outcome_text": outcome_text,
            }
        ),
    )


def done_event() -> ServerSentEvent:
    """Format the terminal success event, emitted only once the turn is persisted."""
    return ServerSentEvent(event="done", data="")


def degraded_event(message: str) -> ServerSentEvent:
    """Format a graceful-degradation event, emitted in place of done on failure."""
    return ServerSentEvent(event="degraded", data=message)


async def build_sse_response(
    events: AsyncIterator[ServerSentEvent],
) -> EventSourceResponse:
    """Wrap an already-formatted event stream in an EventSourceResponse.

    Events are forwarded as they arrive — never buffered — per CLAUDE.md's
    SSE streaming rule.
    """
    return EventSourceResponse(events)
