"""Unit tests for response_streamer.py's pure SSE-formatting functions."""

from sse_starlette.sse import EventSourceResponse

from app.turn.steps.response_streamer import (
    build_sse_response,
    degraded_event,
    done_event,
    narration_event,
)


def test_narration_event_carries_chunk_as_data() -> None:
    event = narration_event("Hello, adventurer.")

    assert event.event == "narration"
    assert event.data == "Hello, adventurer."


def test_done_event_has_done_type() -> None:
    event = done_event()

    assert event.event == "done"


def test_degraded_event_carries_message() -> None:
    event = degraded_event("Your turn couldn't be saved.")

    assert event.event == "degraded"
    assert event.data == "Your turn couldn't be saved."


async def test_build_sse_response_wraps_events_without_consuming_them() -> None:
    async def events():
        yield narration_event("chunk")
        yield done_event()

    response = await build_sse_response(events())

    assert isinstance(response, EventSourceResponse)
