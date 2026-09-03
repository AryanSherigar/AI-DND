"""In-process pub/sub for multiplayer turn-order notifications.

Single-process scope only, same design as spectator_manager.py: a persistent
SSE connection per participant, keyed by (playthrough_id, participant_id) in
module-level memory.
"""

import asyncio
import uuid

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
    if queue:
        await queue.put(("your_turn", ""))
