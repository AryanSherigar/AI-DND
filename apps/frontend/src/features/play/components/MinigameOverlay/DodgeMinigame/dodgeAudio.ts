// Synthesized Web Audio oscillator SFX (hit/win/lose) — no audio asset
// files — plus a thin wrapper around ambient-soundtrack.ts's transitionTo
// API to crossfade into the "tension" mood on minigame start and restore
// the prior mood on exit. See
// docs/specs/dodge-minigame-design.spec.md §3.4.

import { ambientSoundtrack } from "@/shared/lib/audio/ambient-soundtrack";
import type { ScenarioMood } from "@/features/play/types/audio.types";

const TENSION_MOOD: ScenarioMood = "tension";
const MIN_GAIN = 0.0001;

let sharedAudioContext: AudioContext | null = null;

function getAudioContext(): AudioContext | null {
  if (typeof window === "undefined") return null;
  const AudioCtxConstructor =
    window.AudioContext ||
    (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!AudioCtxConstructor) return null;

  if (!sharedAudioContext) {
    sharedAudioContext = new AudioCtxConstructor();
  }
  if (sharedAudioContext.state === "suspended") {
    void sharedAudioContext.resume();
  }
  return sharedAudioContext;
}

function playTone(
  frequencyHz: number,
  startOffsetSeconds: number,
  durationSeconds: number,
  oscillatorType: OscillatorType,
  peakGain: number,
): void {
  const context = getAudioContext();
  if (!context) return;

  const oscillator = context.createOscillator();
  const gainNode = context.createGain();
  oscillator.type = oscillatorType;
  oscillator.frequency.value = frequencyHz;

  const startTime = context.currentTime + startOffsetSeconds;
  gainNode.gain.setValueAtTime(MIN_GAIN, startTime);
  gainNode.gain.exponentialRampToValueAtTime(peakGain, startTime + 0.02);
  gainNode.gain.exponentialRampToValueAtTime(MIN_GAIN, startTime + durationSeconds);

  oscillator.connect(gainNode);
  gainNode.connect(context.destination);
  oscillator.start(startTime);
  oscillator.stop(startTime + durationSeconds + 0.05);
}

const HIT_SFX_FREQUENCY_HZ = 90;
const HIT_SFX_DURATION_SECONDS = 0.15;
const HIT_SFX_GAIN = 0.35;

export function playHitSfx(): void {
  playTone(HIT_SFX_FREQUENCY_HZ, 0, HIT_SFX_DURATION_SECONDS, "square", HIT_SFX_GAIN);
}

const WIN_STINGER_NOTES_HZ = [523.25, 659.25, 783.99]; // C5, E5, G5 — ascending arpeggio
const WIN_STINGER_NOTE_DURATION_SECONDS = 0.14;
const WIN_STINGER_GAIN = 0.3;

export function playWinStinger(): void {
  WIN_STINGER_NOTES_HZ.forEach((frequencyHz, index) => {
    playTone(
      frequencyHz,
      index * WIN_STINGER_NOTE_DURATION_SECONDS,
      WIN_STINGER_NOTE_DURATION_SECONDS,
      "sine",
      WIN_STINGER_GAIN,
    );
  });
}

const LOSE_STINGER_START_HZ = 440;
const LOSE_STINGER_END_HZ = 110;
const LOSE_STINGER_DURATION_SECONDS = 0.5;
const LOSE_STINGER_GAIN = 0.3;

export function playLoseStinger(): void {
  const context = getAudioContext();
  if (!context) return;

  const oscillator = context.createOscillator();
  const gainNode = context.createGain();
  oscillator.type = "sawtooth";

  const startTime = context.currentTime;
  oscillator.frequency.setValueAtTime(LOSE_STINGER_START_HZ, startTime);
  oscillator.frequency.exponentialRampToValueAtTime(
    LOSE_STINGER_END_HZ,
    startTime + LOSE_STINGER_DURATION_SECONDS,
  );
  gainNode.gain.setValueAtTime(MIN_GAIN, startTime);
  gainNode.gain.exponentialRampToValueAtTime(LOSE_STINGER_GAIN, startTime + 0.02);
  gainNode.gain.exponentialRampToValueAtTime(
    MIN_GAIN,
    startTime + LOSE_STINGER_DURATION_SECONDS,
  );

  oscillator.connect(gainNode);
  gainNode.connect(context.destination);
  oscillator.start(startTime);
  oscillator.stop(startTime + LOSE_STINGER_DURATION_SECONDS + 0.05);
}

// Crossfades the existing ambient mood track to "tension" on minigame
// start, and restores the previously-active mood on exit — thin wrapper
// around ambient-soundtrack.ts's transitionTo(mood, isForce) API. This
// module does not manage mood state itself; it just remembers what to
// restore to (captured at call time via ambientSoundtrack.getMood()).
// Forces both transitions past the controller's default cooldown gate so
// the minigame's audio cue is never silently dropped or delayed.
export function enterMinigameAudio(): () => void {
  const previousMood = ambientSoundtrack.getMood();
  ambientSoundtrack.transitionTo(TENSION_MOOD, true);

  return () => {
    if (previousMood) {
      ambientSoundtrack.transitionTo(previousMood, true);
    }
  };
}
