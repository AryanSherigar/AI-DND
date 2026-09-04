# Infrastructure Architecture — Scripts & Operational Tooling

This document profiles the standalone scripts and operational automation utilities located in the `scripts/` directory and package manifests.

---

## 1. Overview

Operational scripts in AI-DND handle offline asset generation, build verification, and database maintenance without introducing external runtime overhead to production services.

---

## 2. File Profiles

### `scripts/generate_ambient_audio.py`
- **Purpose & Layer:** Standalone synthetic audio generation script. Generates mathematically pure, loopable ambient soundtrack audio files for the platform's 5 canonical mood states: `peaceful`, `mystery`, `tension`, `combat`, and `melancholy`.
- **Key Exports & Functions:**
  - `SAMPLE_RATE = 22050`, `DURATION_SECONDS = 10.0`, `MAX_AMPLITUDE = 32767 * 0.4`: Master audio format constants providing 40% headroom against clipping.
  - `generate_sine_wave(frequency: float, time_val: float) -> float`: Evaluates fundamental trigonometric sine waves at a given time point.
  - `generate_sample(mood: str, time_val: float) -> float`: Evaluates harmonic frequency stacks and modulation for each mood:
    - *peaceful*: Warm C major 9th pad (C3, E3, G3, B3, D4) with slow shimmer tremolo.
    - *mystery*: D minor / augmented eerie suspended frequencies (D3, F3, A3, Bb3) with slow detuned beating.
    - *tension*: Low rumbling sub-drone (C2) with tritone dissonance (F#2) and minor second clash (C#3) pulsing at 1.5 Hz.
    - *combat*: Driving rhythmic bass pulse (D2, A2, D3, A3) with fifths and a 2.0 Hz accented beat.
    - *melancholy*: Somber A minor gentle descending drone (A2, C3, E3, A3).
  - `create_loopable_buffer(mood: str) -> list[float]`: Synthesizes audio samples and applies a 1.0-second loop-boundary crossfade to ensure seamless end-to-beginning wrap-around playback.
  - `write_wav_file(file_path: Path, samples: list[float]) -> None`: Encodes IEEE floating-point buffer samples into 16-bit PCM mono WAV format using Python's standard `wave` and `struct` modules.
  - `main() -> None`: Generates all 5 mood tracks and outputs them directly to `apps/frontend/public/audio/moods/`.
- **Dependencies & Interactions:**
  - Python standard library only (`wave`, `math`, `struct`, `pathlib`). Zero third-party audio packages (no `numpy`, `scipy`, or `pydub` required).
  - Generates assets consumed at runtime by `apps/frontend/src/shared/lib/audio/ambient-soundtrack.ts`.
- **Architecture Rules & Invariants:**
  - Standard library only to ensure the script can run in any minimal Python environment without activating service virtual environments.
  - Headroom constraint (`MAX_AMPLITUDE = 32767 * 0.4`) ensures multi-stem audio blending in the browser will never clip or distort when stems crossfade.
