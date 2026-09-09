"""Canonical URLs for the 6 built-in default mood tracks.

Exactly one default track per mood -- a fixed, plain constant rather than a
DB table, since the set never grows, is never queried dynamically, and
changing a default later is a one-line edit here plus a reseed, not a data
migration across every scenario's rows.
"""

from app.db.models.scenario_music import MOOD_SLOTS
from app.integrations import storage_client

_DEFAULT_TRACK_OBJECT_KEYS: dict[str, str] = {
    "peaceful": "default-music/peaceful.mp3",
    "mystery": "default-music/mystery.mp3",
    "tension": "default-music/tension.mp3",
    "combat": "default-music/combat.mp3",
    "melancholy": "default-music/melancholy.mp3",
    "triumph": "default-music/triumph.mp3",
}
assert set(_DEFAULT_TRACK_OBJECT_KEYS) == set(MOOD_SLOTS)


def default_track_url(mood: str) -> str:
    """Resolve the canonical URL for a mood's built-in default track."""
    return storage_client.public_url_for(_DEFAULT_TRACK_OBJECT_KEYS[mood])


def all_default_track_urls() -> dict[str, str]:
    """Return the full mood -> canonical-URL map for all 6 moods."""
    return {mood: default_track_url(mood) for mood in MOOD_SLOTS}
