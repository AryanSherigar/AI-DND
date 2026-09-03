"""Unit tests for spectator_manager.py's in-process pub/sub."""

import asyncio
import uuid

from app.session import spectator_manager


async def test_publish_delivers_to_subscriber_on_same_playthrough() -> None:
    playthrough_id = uuid.uuid4()
    queue = spectator_manager.subscribe(playthrough_id)
    try:
        await spectator_manager.publish(playthrough_id, "narration", "hello")
        event_name, data = await asyncio.wait_for(queue.get(), timeout=1)
        assert event_name == "narration"
        assert data == "hello"
    finally:
        spectator_manager.unsubscribe(playthrough_id, queue)


async def test_publish_reaches_multiple_subscribers() -> None:
    playthrough_id = uuid.uuid4()
    queue_a = spectator_manager.subscribe(playthrough_id)
    queue_b = spectator_manager.subscribe(playthrough_id)
    try:
        await spectator_manager.publish(playthrough_id, "done", "")
        assert (await asyncio.wait_for(queue_a.get(), timeout=1))[0] == "done"
        assert (await asyncio.wait_for(queue_b.get(), timeout=1))[0] == "done"
    finally:
        spectator_manager.unsubscribe(playthrough_id, queue_a)
        spectator_manager.unsubscribe(playthrough_id, queue_b)


async def test_publish_does_not_reach_other_playthroughs() -> None:
    playthrough_id = uuid.uuid4()
    other_playthrough_id = uuid.uuid4()
    queue = spectator_manager.subscribe(playthrough_id)
    try:
        await spectator_manager.publish(other_playthrough_id, "narration", "elsewhere")
        assert queue.empty()
    finally:
        spectator_manager.unsubscribe(playthrough_id, queue)


async def test_unsubscribe_stops_further_delivery() -> None:
    playthrough_id = uuid.uuid4()
    queue = spectator_manager.subscribe(playthrough_id)
    spectator_manager.unsubscribe(playthrough_id, queue)

    await spectator_manager.publish(playthrough_id, "narration", "too late")

    assert queue.empty()
