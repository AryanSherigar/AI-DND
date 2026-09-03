"""In-process pub/sub relaying live turn events to spectator SSE connections.

Single-process scope only: keyed by playthrough_id in module-level memory,
not designed for multi-instance deployment. Consistent with this stack's
single-container Cloud Run hackathon scope and with the memory-mock's own
decoupled, in-process design.
"""

import asyncio
import uuid

_subscribers: dict[uuid.UUID, list[asyncio.Queue]] = {}


def subscribe(playthrough_id: uuid.UUID) -> asyncio.Queue:
    """Register a new spectator connection for a playthrough's live events."""
    queue: asyncio.Queue = asyncio.Queue()
    _subscribers.setdefault(playthrough_id, []).append(queue)
    return queue


def unsubscribe(playthrough_id: uuid.UUID, queue: asyncio.Queue) -> None:
    """Remove a spectator connection. Always called on disconnect."""
    subscribers = _subscribers.get(playthrough_id)
    if subscribers and queue in subscribers:
        subscribers.remove(queue)


async def publish(playthrough_id: uuid.UUID, event_name: str, data: str) -> None:
    """Relay a turn event to every spectator currently watching this playthrough."""
    for queue in _subscribers.get(playthrough_id, []):
        await queue.put((event_name, data))
