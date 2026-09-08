"""Unit tests for music_gen_client's pure crossfade-guardrail math."""

from app.integrations import music_gen_client


def test_target_bpm_uses_mood_range_midpoint() -> None:
    assert music_gen_client._target_bpm("peaceful") == 62
    assert music_gen_client._target_bpm("combat") == 120


def test_bar_aligned_duration_rounds_to_whole_bars() -> None:
    # At 120 BPM, one bar (4 beats) is 2.0 seconds.
    assert music_gen_client._bar_aligned_duration(60, 120) == 60.0
    assert music_gen_client._bar_aligned_duration(61, 120) == 60.0
    assert music_gen_client._bar_aligned_duration(3, 120) == 4.0


def test_bar_aligned_duration_never_rounds_to_zero_bars() -> None:
    assert music_gen_client._bar_aligned_duration(1, 60) > 0


def test_build_prompt_pins_key_and_bpm() -> None:
    prompt = music_gen_client._build_prompt("a tense chase", "tension", 95)
    assert "D minor" in prompt
    assert "95 BPM" in prompt
    assert "a tense chase" in prompt
