// Synthesized Web Audio oscillator SFX (hit/win/lose) — no audio asset
// files — plus a thin wrapper around ambient-soundtrack.ts's transitionTo
// API to crossfade into the "tension" mood on minigame start and restore
// the prior mood on exit. See
// docs/specs/dodge-minigame-design.spec.md §3.4.

import { ambientSoundtrack } from "@/shared/lib/audio/ambient-soundtrack";
import type { ScenarioMood } from "@/shared/types/audio.types";
import type { DodgeAudioSettings } from "@/shared/types/minigame.types";

const TENSION_MOOD: ScenarioMood = "tension";
const MIN_GAIN = 0.0001;

let sharedAudioContext: AudioContext | null = null;
let masterGain: GainNode | null = null;
let localMuted = false;
let localVolume = 0.7;
let globalMuted = ambientSoundtrack.getIsMuted();
let globalVolume = ambientSoundtrack.getVolume();
let activeMusic: HTMLAudioElement | null = null;

function isEffectivelyMuted(): boolean {
  return localMuted || globalMuted;
}

function effectiveVolume(): number {
  return localVolume * globalVolume;
}

function applyMusicSettings(): void {
  if (!activeMusic) return;
  activeMusic.muted = isEffectivelyMuted();
  activeMusic.volume = effectiveVolume();
}

function applyAllAudioSettings(): void {
  if (masterGain)
    masterGain.gain.value = isEffectivelyMuted() ? 0 : effectiveVolume();
  applyMusicSettings();
}

function getAudioContext(): AudioContext | null {
  if (typeof window === "undefined") return null;
  const AudioCtxConstructor =
    window.AudioContext ||
    (window as unknown as { webkitAudioContext?: typeof AudioContext })
      .webkitAudioContext;
  if (!AudioCtxConstructor) return null;

  if (!sharedAudioContext) {
    sharedAudioContext = new AudioCtxConstructor();
    masterGain = sharedAudioContext.createGain();
    masterGain.gain.value = isEffectivelyMuted() ? 0 : effectiveVolume();
    masterGain.connect(sharedAudioContext.destination);
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
  gainNode.gain.exponentialRampToValueAtTime(
    MIN_GAIN,
    startTime + durationSeconds,
  );

  oscillator.connect(gainNode);
  gainNode.connect(masterGain ?? context.destination);
  oscillator.start(startTime);
  oscillator.stop(startTime + durationSeconds + 0.05);
}

const HIT_SFX_FREQUENCY_HZ = 90;
const HIT_SFX_DURATION_SECONDS = 0.15;
const HIT_SFX_GAIN = 0.35;

export function playHitSfx(): void {
  playTone(
    HIT_SFX_FREQUENCY_HZ,
    0,
    HIT_SFX_DURATION_SECONDS,
    "square",
    HIT_SFX_GAIN,
  );
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
  gainNode.gain.exponentialRampToValueAtTime(
    LOSE_STINGER_GAIN,
    startTime + 0.02,
  );
  gainNode.gain.exponentialRampToValueAtTime(
    MIN_GAIN,
    startTime + LOSE_STINGER_DURATION_SECONDS,
  );

  oscillator.connect(gainNode);
  gainNode.connect(masterGain ?? context.destination);
  oscillator.start(startTime);
  oscillator.stop(startTime + LOSE_STINGER_DURATION_SECONDS + 0.05);
}

// Crossfades the existing ambient mood track to "tension" on minigame
// start, and restores the previously-active mood/track on exit — thin
// wrapper around ambient-soundtrack.ts's transitionTo(mood, trackUrl,
// isForce) API. This module does not manage mood state itself; it just
// remembers what to restore to (captured at call time via
// ambientSoundtrack.getMood()/getCurrentTrackUrl()). Uses the built-in
// default tension track (resolved by the caller, since this module makes
// no network calls) rather than the active scenario's custom one, since
// this module has no access to per-scenario track overrides.
// Forces both transitions past the controller's default cooldown gate so
// the minigame's audio cue is never silently dropped or delayed.
export function enterMinigameAudio(
  settings?: DodgeAudioSettings,
  tensionDefaultTrackUrl?: string,
): () => void {
  globalMuted = ambientSoundtrack.getIsMuted();
  globalVolume = ambientSoundtrack.getVolume();
  const previousMood = ambientSoundtrack.getMood();
  const previousTrackUrl = ambientSoundtrack.getCurrentTrackUrl();
  ambientSoundtrack.transitionTo(TENSION_MOOD, tensionDefaultTrackUrl, true);
  if (typeof window !== "undefined" && settings?.music_asset_url) {
    const music = new Audio(settings.music_asset_url);
    music.loop = true;
    music.preload = "auto";
    activeMusic = music;
    applyMusicSettings();
    // A rejected autoplay promise is expected until the Start click; it is
    // intentionally retried by resumeDodgeMusic after that user gesture.
    void music.play().catch(() => undefined);
  }
  const unsubscribeAudioPreferences = ambientSoundtrack.onAudioPreferenceChange(
    (preferences) => {
      globalMuted = preferences.isMuted;
      globalVolume = preferences.volume;
      applyAllAudioSettings();
      // A global unmute is normally itself a user gesture. Retrying here
      // restores custom encounter music without bypassing browser policy.
      if (!isEffectivelyMuted() && activeMusic) {
        void activeMusic.play().catch(() => undefined);
      }
    },
  );

  return () => {
    unsubscribeAudioPreferences();
    if (activeMusic) {
      activeMusic.pause();
      activeMusic.removeAttribute("src");
      activeMusic.load();
      activeMusic = null;
    }
    if (previousMood && previousTrackUrl) {
      ambientSoundtrack.transitionTo(previousMood, previousTrackUrl, true);
    }
  };
}

export function setDodgeMuted(nextMuted: boolean): void {
  localMuted = nextMuted;
  applyAllAudioSettings();
}

export function setDodgeVolume(nextVolume: number): void {
  localVolume = Math.max(0, Math.min(1, nextVolume));
  applyAllAudioSettings();
}

/** Retry custom music after the explicit Start/Resume user gesture. */
export function resumeDodgeMusic(): void {
  if (activeMusic && !isEffectivelyMuted())
    void activeMusic.play().catch(() => undefined);
}
