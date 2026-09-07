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


async def test_unsubscribe_removes_playthrough_when_empty() -> None:
    playthrough_id = uuid.uuid4()
    queue = spectator_manager.subscribe(playthrough_id)
    assert playthrough_id in spectator_manager._subscribers

    spectator_manager.unsubscribe(playthrough_id, queue)
    assert playthrough_id not in spectator_manager._subscribers


async def test_publish_tolerates_concurrent_disconnect() -> None:
    playthrough_id = uuid.uuid4()
    queue_a = spectator_manager.subscribe(playthrough_id)
    queue_b = spectator_manager.subscribe(playthrough_id)
    queue_c = spectator_manager.subscribe(playthrough_id)

    # When queue_a receives the event, trigger concurrent unsubscription of queue_a and queue_b
    original_put = queue_a.put_nowait

    def put_and_mutate(item: tuple[str, str]) -> None:
        original_put(item)
        spectator_manager.unsubscribe(playthrough_id, queue_a)
        spectator_manager.unsubscribe(playthrough_id, queue_b)

    queue_a.put_nowait = put_and_mutate  # type: ignore[assignment]

    try:
        await spectator_manager.publish(playthrough_id, "narration", "live")
        # Both queue_a and queue_c must have received it, without skipping queue_b or raising
        assert not queue_a.empty()
        assert not queue_c.empty()
    finally:
        spectator_manager.unsubscribe(playthrough_id, queue_c)


async def test_publish_tolerates_queue_full() -> None:
    playthrough_id = uuid.uuid4()
    full_queue: asyncio.Queue[tuple[str, str]] = asyncio.Queue(maxsize=1)
    full_queue.put_nowait(("existing", "data"))
    normal_queue = spectator_manager.subscribe(playthrough_id)

    spectator_manager._subscribers[playthrough_id].insert(0, full_queue)
    try:
        await spectator_manager.publish(playthrough_id, "narration", "new_event")
        assert (await asyncio.wait_for(normal_queue.get(), timeout=1))[0] == "narration"
    finally:
        spectator_manager.unsubscribe(playthrough_id, normal_queue)
        spectator_manager.unsubscribe(playthrough_id, full_queue)
