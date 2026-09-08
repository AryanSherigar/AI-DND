"""Formats turn pipeline events as Server-Sent Events for the client.

Pure formatting only — this step never calls state_writer or any other step
directly; pipeline.py is the sole sequencer (CLAUDE.md).
"""

import json
from collections.abc import AsyncIterator

from app.config import settings
from app.models.minigame_event import MinigameEventPayload
from app.models.turn_summary import TurnSummaryPayload
from sse_starlette.sse import EventSourceResponse, ServerSentEvent


def narration_event(chunk: str) -> ServerSentEvent:
    """Format one narration chunk as an SSE event."""
    return ServerSentEvent(event="narration", data=chunk)


def mood_event(mood: str) -> ServerSentEvent:
    """Format a mood transition event as an SSE event."""
    return ServerSentEvent(event="mood", data=mood)


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


def turn_summary_event(payload: TurnSummaryPayload) -> ServerSentEvent:
    """Format the master-mode end-of-turn state-delta event as an SSE event,
    emitted after state_writer/end_condition_evaluator, before the terminal
    done event — the frontend defers showing it until that turn's narration
    finishes streaming, regardless of when it arrives."""
    return ServerSentEvent(event="turn_summary", data=payload.model_dump_json())


def minigame_event(payload: MinigameEventPayload) -> ServerSentEvent:
    """Format the triggered minigame's play-time config as an SSE event,
    emitted after turn_summary_event, before playthrough_ended_event/
    done_event. payload never carries win_mutation/lose_mutation/
    tiered_outcomes/timeout_mutation/narrator_instruction_template — those
    stay server-side only (§3.6's "Always" boundary)."""
    return ServerSentEvent(event="minigame", data=payload.model_dump_json())


def scene_image_event(url: str) -> ServerSentEvent:
    """Format a generated 'see'-action scene image URL as an SSE event,
    emitted once (best-effort — only when generation succeeded) after
    narration finishes streaming, before state persistence."""
    return ServerSentEvent(event="scene_image", data=url)


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
    return EventSourceResponse(events, ping=settings.sse_ping_interval_seconds)
