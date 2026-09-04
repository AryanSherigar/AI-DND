"""Generates loopable ambient soundtrack audio files for each mood.

Standard library only: wave, math, struct. Zero external audio dependencies.
Produces seamless 10-second WAV files for the 5 canonical moods.
"""

import math
import struct
import wave
from pathlib import Path

SAMPLE_RATE = 22050
DURATION_SECONDS = 10.0
NUM_SAMPLES = int(SAMPLE_RATE * DURATION_SECONDS)
MAX_AMPLITUDE = 32767 * 0.4  # 40% headroom to prevent clipping


def generate_sine_wave(frequency: float, time_val: float) -> float:
    return math.sin(2.0 * math.pi * frequency * time_val)


def generate_sample(mood: str, time_val: float) -> float:
    t = time_val
    if mood == "peaceful":
        # Warm C major 9th ambient pad with slow shimmer tremolo
        shimmer = 0.8 + 0.2 * math.sin(2.0 * math.pi * 0.3 * t)
        v1 = 0.30 * generate_sine_wave(130.81, t)  # C3
        v2 = 0.25 * generate_sine_wave(164.81, t)  # E3
        v3 = 0.20 * generate_sine_wave(196.00, t)  # G3
        v4 = 0.15 * generate_sine_wave(246.94, t)  # B3
        v5 = 0.10 * generate_sine_wave(293.66, t)  # D4
        return (v1 + v2 + v3 + v4 + v5) * shimmer

    if mood == "mystery":
        # D minor / augmented eerie suspended frequencies with slow detuned beating
        shimmer = 0.7 + 0.3 * math.sin(2.0 * math.pi * 0.2 * t)
        v1 = 0.35 * generate_sine_wave(146.83, t)  # D3
        v2 = 0.25 * generate_sine_wave(174.61, t)  # F3
        v3 = 0.20 * generate_sine_wave(220.00, t)  # A3
        v4 = 0.15 * generate_sine_wave(233.08, t)  # Bb3
        v5 = 0.05 * generate_sine_wave(147.83, t)  # Detuned D3 beating
        return (v1 + v2 + v3 + v4 + v5) * shimmer

    if mood == "tension":
        # Low rumbling sub-drone with tritone dissonance and rhythmic pulse
        pulse = 0.7 + 0.3 * math.sin(2.0 * math.pi * 1.5 * t)
        v1 = 0.45 * generate_sine_wave(65.41, t)  # C2
        v2 = 0.30 * generate_sine_wave(92.50, t)  # F#2 (tritone)
        v3 = 0.15 * generate_sine_wave(130.81, t)  # C3
        v4 = 0.10 * generate_sine_wave(138.59, t)  # C#3 (minor second dissonance)
        return (v1 + v2 + v3 + v4) * pulse

    if mood == "combat":
        # Driving percussive bass pulse with fifths and accented beat
        beat = (math.sin(2.0 * math.pi * 2.0 * t) ** 4) * 0.5 + 0.5
        v1 = 0.40 * generate_sine_wave(73.42, t)  # D2
        v2 = 0.30 * generate_sine_wave(110.00, t)  # A2
        v3 = 0.20 * generate_sine_wave(146.83, t)  # D3
        v4 = 0.10 * generate_sine_wave(220.00, t)  # A3
        return (v1 + v2 + v3 + v4) * beat

    if mood == "melancholy":
        # Somber A minor gentle descending drone
        shimmer = 0.75 + 0.25 * math.cos(2.0 * math.pi * 0.15 * t)
        v1 = 0.40 * generate_sine_wave(110.00, t)  # A2
        v2 = 0.25 * generate_sine_wave(130.81, t)  # C3
        v3 = 0.20 * generate_sine_wave(164.81, t)  # E3
        v4 = 0.15 * generate_sine_wave(220.00, t)  # A3
        return (v1 + v2 + v3 + v4) * shimmer

    return 0.0


def create_loopable_buffer(mood: str) -> list[float]:
    raw = [generate_sample(mood, i / SAMPLE_RATE) for i in range(NUM_SAMPLES)]
    # Apply 1.0s loop boundary crossfade to make wrap-around perfectly seamless
    fade_samples = int(SAMPLE_RATE * 1.0)
    for i in range(fade_samples):
        alpha = i / fade_samples
        # Blend end into start and start into end
        end_idx = NUM_SAMPLES - fade_samples + i
        blended = raw[i] * alpha + raw[end_idx] * (1.0 - alpha)
        raw[i] = blended
        raw[end_idx] = blended
    return raw


def write_wav_file(file_path: Path, samples: list[float]) -> None:
    with wave.open(str(file_path), "wb") as wav_out:
        wav_out.setnchannels(1)
        wav_out.setsampwidth(2)
        wav_out.setframerate(SAMPLE_RATE)
        frames = bytearray()
        for sample_val in samples:
            clamped = max(-1.0, min(1.0, sample_val))
            int_val = int(clamped * MAX_AMPLITUDE)
            frames.extend(struct.pack("<h", int_val))
        wav_out.writeframes(frames)


def main() -> None:
    out_dir = Path("apps/frontend/public/audio/moods")
    out_dir.mkdir(parents=True, exist_ok=True)
    moods = ["peaceful", "mystery", "tension", "combat", "melancholy"]
    for mood in moods:
        buffer = create_loopable_buffer(mood)
        target = out_dir / f"{mood}.wav"
        write_wav_file(target, buffer)
        print(f"Generated {target} ({target.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
