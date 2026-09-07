"""In-process pub/sub for multiplayer turn-order notifications.

Single-process scope only, same design as spectator_manager.py: a persistent
SSE connection per participant, keyed by (playthrough_id, participant_id) in
module-level memory.
"""

import asyncio
import uuid

import structlog

logger = structlog.get_logger()

_subscribers: dict[tuple[uuid.UUID, uuid.UUID], asyncio.Queue] = {}


def subscribe(playthrough_id: uuid.UUID, participant_id: uuid.UUID) -> asyncio.Queue:
    """Register a participant's persistent notification connection."""
    queue: asyncio.Queue = asyncio.Queue()
    _subscribers[(playthrough_id, participant_id)] = queue
    return queue


def unsubscribe(playthrough_id: uuid.UUID, participant_id: uuid.UUID) -> None:
    """Remove a participant's notification connection. Always called on disconnect."""
    _subscribers.pop((playthrough_id, participant_id), None)


async def notify_next_turn(
    playthrough_id: uuid.UUID, next_participant_id: uuid.UUID
) -> None:
    """Tell the next participant it's their turn, if they have an open connection.

    A no-op if that participant never connected — the frontend's turn-order UI
    is derived independently, so this push is a convenience, not a dependency.
    """
    queue = _subscribers.get((playthrough_id, next_participant_id))
    if queue is None:
        return
    try:
        queue.put_nowait(("your_turn", ""))
    except asyncio.QueueFull:
        logger.warning(
            "notification_queue_full_dropping_turn",
            playthrough_id=str(playthrough_id),
            participant_id=str(next_participant_id),
        )


async def notify_playthrough_ended(
    playthrough_id: uuid.UUID, outcome_title: str
) -> None:
    """Tell every connected participant a playthrough just ended.

    Unlike notify_next_turn, this is a genuine broadcast — every participant
    with an open connection needs to know, not just whoever acts next. A
    no-op per participant with no open connection; they discover the ended
    status on their next GET /v1/playthroughs/{id} poll.
    """
    subscribers_snapshot = [
        queue
        for (subscribed_playthrough_id, _), queue in list(_subscribers.items())
        if subscribed_playthrough_id == playthrough_id
    ]
    for queue in subscribers_snapshot:
        try:
            queue.put_nowait(("playthrough_ended", outcome_title))
        except asyncio.QueueFull:
            logger.warning(
                "notification_queue_full_dropping_ended",
                playthrough_id=str(playthrough_id),
                outcome_title=outcome_title,
            )
