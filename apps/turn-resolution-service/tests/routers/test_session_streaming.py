"""Tests for session SSE streaming, keep-alive heartbeat pings, and disconnect handling."""

import asyncio
from typing import Any

from sse_starlette.sse import EventSourceResponse

from app.config import settings
from app.routers.session import _relay


async def test_relay_yields_events_as_they_arrive() -> None:
    queue: asyncio.Queue[tuple[str, str]] = asyncio.Queue()
    is_disconnected = False

    def on_disconnect() -> None:
        nonlocal is_disconnected
        is_disconnected = True

    stream = _relay(queue, on_disconnect)
    await queue.put(("narration", "A cold wind howls."))

    event = await anext(stream)
    assert event.event == "narration"
    assert event.data == "A cold wind howls."

    await stream.aclose()
    assert is_disconnected is True


async def test_relay_calls_disconnect_callback_on_cancellation() -> None:
    queue: asyncio.Queue[tuple[str, str]] = asyncio.Queue()
    is_disconnected = False

    def on_disconnect() -> None:
        nonlocal is_disconnected
        is_disconnected = True

    stream = _relay(queue, on_disconnect)
    task = asyncio.create_task(anext(stream))
    await asyncio.sleep(0.01)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    assert is_disconnected is True


async def test_eventsource_response_sends_keepalive_pings_on_idle_stream() -> None:
    queue: asyncio.Queue[tuple[str, str]] = asyncio.Queue()
    sent_messages: list[dict[str, Any]] = []

    async def mock_receive() -> dict[str, str]:
        await asyncio.sleep(5)
        return {"type": "http.disconnect"}

    async def mock_send(message: dict[str, Any]) -> None:
        sent_messages.append(message)

    test_ping_interval_seconds = 0.1
    response = EventSourceResponse(
        _relay(queue, lambda: None), ping=test_ping_interval_seconds
    )
    response_task = asyncio.create_task(
        response({"type": "http"}, mock_receive, mock_send)
    )

    await asyncio.sleep(0.35)
    response_task.cancel()
    try:
        await response_task
    except asyncio.CancelledError:
        pass

    assert sent_messages[0]["type"] == "http.response.start"
    ping_messages = [
        msg
        for msg in sent_messages
        if msg.get("type") == "http.response.body" and b": ping" in msg.get("body", b"")
    ]
    assert len(ping_messages) >= 2


def test_session_settings_has_expected_ping_interval() -> None:
    assert settings.sse_ping_interval_seconds == 15
