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
