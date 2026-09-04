"""Unit tests for response_streamer.py's pure SSE-formatting functions."""

import json

from sse_starlette.sse import EventSourceResponse

from app.models.turn_summary import DiceRoll, StatChange, TurnSummaryPayload
from app.turn.steps.response_streamer import (
    build_sse_response,
    degraded_event,
    done_event,
    narration_event,
    turn_summary_event,
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


def test_turn_summary_event_serializes_payload_as_json() -> None:
    payload = TurnSummaryPayload(
        stat_changes=[
            StatChange(
                path="player.health", label="Health", before=100, after=85, delta=-15.0
            )
        ],
        dice_rolls=[
            DiceRoll(expression="d20", sides=20, modifier=0, roll=14, total=14)
        ],
        active_conditions=["Bleeding Out"],
    )

    event = turn_summary_event(payload)

    assert event.event == "turn_summary"
    data = json.loads(event.data)
    assert data["active_conditions"] == ["Bleeding Out"]
    assert data["stat_changes"][0]["path"] == "player.health"
    assert data["dice_rolls"][0]["total"] == 14
    assert data["inventory_changes"] == []


async def test_build_sse_response_wraps_events_without_consuming_them() -> None:
    async def events():
        yield narration_event("chunk")
        yield done_event()

    response = await build_sse_response(events())

    assert isinstance(response, EventSourceResponse)
