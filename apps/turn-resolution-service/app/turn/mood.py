"""Mood taxonomy and tag extraction for adaptive audio narration."""

import re
from enum import StrEnum

MAX_MOOD_BUFFER_LENGTH = 60
_TAG_PATTERN = re.compile(
    r"^\s*[*_`]*(?:\[\s*mood\s*:\s*([a-zA-Z_\-]+)\s*\]|mood\s*:\s*([a-zA-Z_\-]+)\s*(?:\r?\n))\s*[*_`]*\s*(?:\r?\n)?\s*",
    re.IGNORECASE,
)


class MoodTag(StrEnum):
    """Canonical 5-mood RPG sound palette."""

    PEACEFUL = "peaceful"
    MYSTERY = "mystery"
    TENSION = "tension"
    COMBAT = "combat"
    MELANCHOLY = "melancholy"


DEFAULT_MOOD = MoodTag.PEACEFUL

CANONICAL_MOODS: frozenset[str] = frozenset(m.value for m in MoodTag)

MOOD_SYNONYMS: dict[str, MoodTag] = {
    "calm": MoodTag.PEACEFUL,
    "exploration": MoodTag.PEACEFUL,
    "serene": MoodTag.PEACEFUL,
    "peace": MoodTag.PEACEFUL,
    "eerie": MoodTag.MYSTERY,
    "creepy": MoodTag.MYSTERY,
    "strange": MoodTag.MYSTERY,
    "curious": MoodTag.MYSTERY,
    "suspense": MoodTag.TENSION,
    "danger": MoodTag.TENSION,
    "ominous": MoodTag.TENSION,
    "dread": MoodTag.TENSION,
    "action": MoodTag.COMBAT,
    "battle": MoodTag.COMBAT,
    "fight": MoodTag.COMBAT,
    "boss": MoodTag.COMBAT,
    "sorrow": MoodTag.MELANCHOLY,
    "sad": MoodTag.MELANCHOLY,
    "grief": MoodTag.MELANCHOLY,
    "tragic": MoodTag.MELANCHOLY,
}


def normalize_mood(raw_text: str) -> MoodTag:
    """Normalize raw text or synonym into a canonical MoodTag."""
    cleaned = raw_text.strip().lower().replace("[", "").replace("]", "")
    if cleaned in CANONICAL_MOODS:
        return MoodTag(cleaned)
    if cleaned in MOOD_SYNONYMS:
        return MOOD_SYNONYMS[cleaned]
    return DEFAULT_MOOD


def extract_mood_tag(buffer_text: str) -> tuple[MoodTag | None, str, bool]:
    """Extract opening mood tag from buffered generation text.

    Returns:
        (detected_mood, cleaned_text, is_decided)
    """
    match = _TAG_PATTERN.match(buffer_text)
    if match:
        mood = normalize_mood(match.group(1) or match.group(2))
        cleaned = buffer_text[match.end() :]
        return mood, cleaned, True

    stripped = buffer_text.lstrip()
    prefix = stripped.lstrip("*_`")
    is_tag_candidate = prefix.startswith("[") or prefix.lower().startswith("mood")
    if is_tag_candidate:
        if len(buffer_text) < MAX_MOOD_BUFFER_LENGTH and "\n" not in buffer_text:
            return None, buffer_text, False
        return None, buffer_text, True

    return None, buffer_text, True
