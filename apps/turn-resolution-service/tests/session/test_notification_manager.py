"""Unit tests for notification_manager.py's in-process pub/sub."""

import asyncio
import uuid

from app.session import notification_manager


async def test_notify_next_turn_delivers_to_target_participant() -> None:
    playthrough_id, participant_id = uuid.uuid4(), uuid.uuid4()
    queue = notification_manager.subscribe(playthrough_id, participant_id)
    try:
        await notification_manager.notify_next_turn(playthrough_id, participant_id)
        event_name, _ = await asyncio.wait_for(queue.get(), timeout=1)
        assert event_name == "your_turn"
    finally:
        notification_manager.unsubscribe(playthrough_id, participant_id)


async def test_notify_next_turn_does_not_reach_other_participant() -> None:
    playthrough_id = uuid.uuid4()
    target_id, other_id = uuid.uuid4(), uuid.uuid4()
    target_queue = notification_manager.subscribe(playthrough_id, target_id)
    other_queue = notification_manager.subscribe(playthrough_id, other_id)
    try:
        await notification_manager.notify_next_turn(playthrough_id, target_id)
        assert not target_queue.empty()
        assert other_queue.empty()
    finally:
        notification_manager.unsubscribe(playthrough_id, target_id)
        notification_manager.unsubscribe(playthrough_id, other_id)


async def test_notify_next_turn_is_a_noop_when_nobody_subscribed() -> None:
    playthrough_id, participant_id = uuid.uuid4(), uuid.uuid4()
    # No subscribe() call — must not raise.
    await notification_manager.notify_next_turn(playthrough_id, participant_id)


async def test_unsubscribe_stops_further_delivery() -> None:
    playthrough_id, participant_id = uuid.uuid4(), uuid.uuid4()
    queue = notification_manager.subscribe(playthrough_id, participant_id)
    notification_manager.unsubscribe(playthrough_id, participant_id)

    await notification_manager.notify_next_turn(playthrough_id, participant_id)

    assert queue.empty()


async def test_notify_playthrough_ended_delivers_to_all_participants_in_playthrough() -> (
    None
):
    playthrough_id = uuid.uuid4()
    other_playthrough_id = uuid.uuid4()

    queue_a = notification_manager.subscribe(playthrough_id, uuid.uuid4())
    queue_b = notification_manager.subscribe(playthrough_id, uuid.uuid4())
    queue_other = notification_manager.subscribe(other_playthrough_id, uuid.uuid4())

    try:
        await notification_manager.notify_playthrough_ended(playthrough_id, "Victory")

        event_a, outcome_a = await asyncio.wait_for(queue_a.get(), timeout=1)
        assert event_a == "playthrough_ended"
        assert outcome_a == "Victory"

        event_b, outcome_b = await asyncio.wait_for(queue_b.get(), timeout=1)
        assert event_b == "playthrough_ended"
        assert outcome_b == "Victory"

        assert queue_other.empty()
    finally:
        notification_manager._subscribers.clear()


async def test_notify_playthrough_ended_tolerates_concurrent_mutation() -> None:
    playthrough_id = uuid.uuid4()
    participant_a = uuid.uuid4()
    participant_b = uuid.uuid4()
    queue_a = notification_manager.subscribe(playthrough_id, participant_a)
    queue_b = notification_manager.subscribe(playthrough_id, participant_b)

    original_put = queue_a.put_nowait

    def put_and_mutate(item: tuple[str, str]) -> None:
        original_put(item)
        # Concurrently subscribe a new participant and unsubscribe an existing one
        notification_manager.subscribe(playthrough_id, uuid.uuid4())
        notification_manager.unsubscribe(playthrough_id, participant_b)

    queue_a.put_nowait = put_and_mutate  # type: ignore[assignment]

    try:
        await notification_manager.notify_playthrough_ended(playthrough_id, "Defeat")
        assert not queue_a.empty()
        assert not queue_b.empty()
    finally:
        notification_manager._subscribers.clear()


async def test_notify_playthrough_ended_tolerates_queue_full() -> None:
    playthrough_id = uuid.uuid4()
    full_queue: asyncio.Queue[tuple[str, str]] = asyncio.Queue(maxsize=1)
    full_queue.put_nowait(("existing", "data"))

    normal_participant = uuid.uuid4()
    normal_queue = notification_manager.subscribe(playthrough_id, normal_participant)

    full_participant = uuid.uuid4()
    notification_manager._subscribers[(playthrough_id, full_participant)] = full_queue

    try:
        await notification_manager.notify_playthrough_ended(playthrough_id, "Ended")
        event, _ = await asyncio.wait_for(normal_queue.get(), timeout=1)
        assert event == "playthrough_ended"
    finally:
        notification_manager._subscribers.clear()


async def test_notify_next_turn_tolerates_queue_full() -> None:
    playthrough_id, participant_id = uuid.uuid4(), uuid.uuid4()
    full_queue: asyncio.Queue[tuple[str, str]] = asyncio.Queue(maxsize=1)
    full_queue.put_nowait(("existing", "data"))
    notification_manager._subscribers[(playthrough_id, participant_id)] = full_queue

    try:
        # Must not raise QueueFull
        await notification_manager.notify_next_turn(playthrough_id, participant_id)
    finally:
        notification_manager.unsubscribe(playthrough_id, participant_id)
