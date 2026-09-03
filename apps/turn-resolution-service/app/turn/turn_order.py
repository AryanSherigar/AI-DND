"""Shared turn-order derivation math.

Extracted out of request_receiver.py (its original home) so
session/notification_manager.py can compute "whose turn is it now" after a
turn completes without duplicating the turn_order_position cycling logic.
"""

from app.db.models.participant import Participant


def expected_participant(
    participants: list[Participant], turn_count: int
) -> Participant:
    """Return the participant expected to act at the given turn_count.

    Cycles through participants ordered by turn_order_position: the
    participant at position 1 acts on turn_count 0, position 2 on
    turn_count 1, etc.
    """
    ordered = sorted(participants, key=lambda p: p.turn_order_position)
    return ordered[turn_count % len(ordered)]
