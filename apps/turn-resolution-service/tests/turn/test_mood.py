"""Unit tests for mood extraction and normalization."""

from app.turn.mood import (
    DEFAULT_MOOD,
    MAX_MOOD_BUFFER_LENGTH,
    MoodTag,
    extract_mood_tag,
    normalize_mood,
)


def test_normalize_canonical_moods() -> None:
    assert normalize_mood("peaceful") == MoodTag.PEACEFUL
    assert normalize_mood("MYSTERY") == MoodTag.MYSTERY
    assert normalize_mood("  tension  ") == MoodTag.TENSION
    assert normalize_mood("Combat") == MoodTag.COMBAT
    assert normalize_mood("melancholy") == MoodTag.MELANCHOLY


def test_normalize_synonyms() -> None:
    assert normalize_mood("eerie") == MoodTag.MYSTERY
    assert normalize_mood("battle") == MoodTag.COMBAT
    assert normalize_mood("danger") == MoodTag.TENSION
    assert normalize_mood("calm") == MoodTag.PEACEFUL
    assert normalize_mood("sorrow") == MoodTag.MELANCHOLY


def test_normalize_unknown_fallback() -> None:
    assert normalize_mood("unknown_mood") == DEFAULT_MOOD
    assert normalize_mood("funky") == DEFAULT_MOOD


def test_extract_mood_tag_exact() -> None:
    raw = "[MOOD: combat]\nThe sword clashes against the shield."
    mood, remaining, is_decided = extract_mood_tag(raw)
    assert is_decided is True
    assert mood == MoodTag.COMBAT
    assert remaining == "The sword clashes against the shield."


def test_extract_mood_tag_case_insensitive_and_whitespace() -> None:
    raw = " [mood:  mystery ] \nYou step into the fog."
    mood, remaining, is_decided = extract_mood_tag(raw)
    assert is_decided is True
    assert mood == MoodTag.MYSTERY
    assert remaining == "You step into the fog."


def test_extract_mood_tag_synonym() -> None:
    raw = "[MOOD: eerie]\nA strange chill fills the room."
    mood, remaining, is_decided = extract_mood_tag(raw)
    assert is_decided is True
    assert mood == MoodTag.MYSTERY
    assert remaining == "A strange chill fills the room."


def test_extract_mood_tag_missing_with_newline() -> None:
    raw = "The sun rises quietly over the hills.\nA new day begins."
    mood, remaining, is_decided = extract_mood_tag(raw)
    assert is_decided is True
    assert mood is None
    assert remaining == raw


def test_extract_mood_tag_short_buffer_undecided() -> None:
    raw = "[MOOD: co"
    mood, remaining, is_decided = extract_mood_tag(raw)
    assert is_decided is False
    assert mood is None
    assert remaining == raw


def test_extract_mood_tag_buffer_overflow_undecided_resolves() -> None:
    raw = "A" * MAX_MOOD_BUFFER_LENGTH
    mood, remaining, is_decided = extract_mood_tag(raw)
    assert is_decided is True
    assert mood is None
    assert remaining == raw


def test_extract_mood_tag_streaming_chunks() -> None:
    chunks = ["[MO", "OD: comb", "at]\nYou s", "wing your ax"]
    buffer = ""
    mood = None
    is_decided = False
    flushed_chunks = []

    for chunk in chunks:
        buffer += chunk
        if not is_decided:
            detected_mood, cleaned, is_decided = extract_mood_tag(buffer)
            if is_decided:
                mood = detected_mood
                buffer = cleaned
                if buffer:
                    flushed_chunks.append(buffer)
                    buffer = ""
        else:
            flushed_chunks.append(chunk)

    assert mood == MoodTag.COMBAT
    assert "".join(flushed_chunks) == "You swing your ax"


def test_extract_mood_tag_markdown() -> None:
    raw = "**[MOOD: combat]**\nThe battle starts!"
    mood, remaining, is_decided = extract_mood_tag(raw)
    assert is_decided is True
    assert mood == MoodTag.COMBAT
    assert remaining == "The battle starts!"
