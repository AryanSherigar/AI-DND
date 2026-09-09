import { useEffect, useRef, useState } from "react";
import { useGameLoop, type DodgeOutcome } from "./useGameLoop";
import {
  enterMinigameAudio,
  resumeDodgeMusic,
  setDodgeMuted,
  setDodgeVolume,
} from "./dodgeAudio";
import { HUD } from "./HUD";
import { DodgeMinigameProps } from "./DodgeMinigame.types";

type UiPhase = "instructions" | "playing" | "paused" | "resolved";
const RESOLUTION_BEAT_MS = 500;

const getPerformanceTier = (
  hitPoints: number,
  excellentHealth: number,
  surviveHealth: number,
): string => {
  if (hitPoints >= excellentHealth) return "Flawless";
  if (hitPoints >= surviveHealth) return "Steady";
  return "Narrow escape";
};

/**
 * Orchestrates one Ashfall Dodge encounter: instructions -> playing ->
 * resolved. Mounts useGameLoop (owns the PixiJS Application + simulation)
 * and HUD (the DOM overlay), and is the only piece of this subtree that
 * knows about the countdown/resolution-beat presentation. Entirely
 * self-contained — no network calls, no play.store.ts/SSE knowledge; the
 * parent MinigameOverlay owns turning `onComplete` into a submitted result.
 * See docs/specs/dodge-minigame-design.spec.md.
 */
export function DodgeMinigame({
  dodgeConfig,
  onComplete,
  tensionDefaultTrackUrl,
}: DodgeMinigameProps) {
  const [uiPhase, setUiPhase] = useState<UiPhase>("instructions");
  const [muted, setMuted] = useState(dodgeConfig.audio?.muted ?? false);
  const [volume, setVolume] = useState(dodgeConfig.audio?.volume ?? 0.7);
  const resolvedOutcomeRef = useRef<DodgeOutcome | null>(null);
  const completionTimeoutRef = useRef<number | null>(null);

  const handleInternalComplete = (outcome: DodgeOutcome): void => {
    resolvedOutcomeRef.current = outcome;
    setUiPhase("resolved");
    if (completionTimeoutRef.current !== null) return;
    completionTimeoutRef.current = window.setTimeout(
      () => onComplete(outcome),
      RESOLUTION_BEAT_MS,
    );
  };

  const {
    hitPoints,
    maxHitPoints,
    timeRemainingMs,
    durationMs,
    canvasContainerRef,
    start,
    resume,
    isHit,
    isPaused,
  } = useGameLoop(dodgeConfig, handleInternalComplete);

  useEffect(() => {
    setDodgeMuted(dodgeConfig.audio?.muted ?? false);
    setDodgeVolume(dodgeConfig.audio?.volume ?? 0.7);
    const restoreAudio = enterMinigameAudio(
      dodgeConfig.audio,
      tensionDefaultTrackUrl,
    );
    return () => {
      restoreAudio();
      if (completionTimeoutRef.current !== null)
        window.clearTimeout(completionTimeoutRef.current);
    };
  }, [dodgeConfig.audio, tensionDefaultTrackUrl]);

  useEffect(() => {
    if (uiPhase === "playing" && isPaused) setUiPhase("paused");
  }, [isPaused, uiPhase]);

  const begin = (): void => {
    resumeDodgeMusic();
    setUiPhase("playing");
    start();
  };
  const continueGame = (): void => {
    resumeDodgeMusic();
    resume();
    setUiPhase("playing");
  };
  const changeMuted = (): void => {
    setDodgeMuted(!muted);
    setMuted(!muted);
  };

  const resolvedOutcome = resolvedOutcomeRef.current;
  const excellentHealth =
    dodgeConfig.performance_thresholds?.excellent_min_health ?? maxHitPoints;
  const surviveHealth =
    dodgeConfig.performance_thresholds?.survive_min_health ??
    Math.ceil(maxHitPoints / 2);
  const performanceTier = getPerformanceTier(
    hitPoints,
    excellentHealth,
    surviveHealth,
  );

  return (
    <div className="relative mx-auto flex w-full max-w-[640px] flex-col items-center gap-3">
      <div
        ref={canvasContainerRef}
        className="relative aspect-[4/3] w-full overflow-hidden rounded-2xl bg-[#0a0a14] shadow-[0_0_40px_rgba(126,200,255,0.25)] [&_canvas]:h-full [&_canvas]:w-full"
      />
      {uiPhase === "playing" && (
        <HUD
          hitPoints={hitPoints}
          maxHitPoints={maxHitPoints}
          timeRemainingMs={timeRemainingMs}
          durationMs={durationMs}
        />
      )}
      <div className="absolute right-3 top-3 z-10 flex items-center gap-2 rounded-full bg-black/50 px-3 py-1.5 text-xs text-white">
        <button
          type="button"
          onClick={changeMuted}
          aria-label={muted ? "Unmute game audio" : "Mute game audio"}
          className="font-semibold hover:text-sky-200"
        >
          {muted ? "Unmute" : "Mute"}
        </button>
        <input
          aria-label="Game audio volume"
          type="range"
          min="0"
          max="1"
          step="0.05"
          value={volume}
          onChange={(event) => {
            const next = Number(event.target.value);
            setVolume(next);
            setDodgeVolume(next);
          }}
        />
      </div>
      {uiPhase === "instructions" && (
        <div className="absolute inset-0 z-20 flex items-center justify-center bg-slate-950/90 p-5 text-center text-white">
          <div className="max-w-md space-y-4">
            <p className="text-xs font-bold uppercase tracking-[0.25em] text-sky-300">
              Ashfall Dodge
            </p>
            <h2 className="text-3xl font-bold">Survive the storm.</h2>
            <p className="text-sm text-slate-200">
              {dodgeConfig.copy?.instructions ??
                dodgeConfig.instructions ??
                "Avoid falling ash, converging rings, sweeping beams, and hunting orbs until the timer ends."}
            </p>
            <div className="grid grid-cols-3 gap-2 text-xs text-slate-200">
              <span>WASD to move</span>
              <span>Health absorbs hits</span>
              <span>Beams strike after flashing</span>
            </div>
            <button
              type="button"
              onClick={begin}
              className="rounded-lg bg-sky-400 px-6 py-3 font-bold text-slate-950 transition hover:bg-sky-300 focus:outline-none focus:ring-2 focus:ring-white"
            >
              {dodgeConfig.copy?.start_text ??
                dodgeConfig.start_text ??
                "Start encounter"}
            </button>
          </div>
        </div>
      )}
      {uiPhase === "paused" && (
        <div className="absolute inset-0 z-20 flex items-center justify-center bg-slate-950/85 p-5 text-center text-white">
          <div className="space-y-3">
            <h2 className="text-3xl font-bold">Paused</h2>
            <p className="text-sm text-slate-200">
              Focus left the arena. No time passed while paused.
            </p>
            <button
              type="button"
              onClick={continueGame}
              className="rounded-lg bg-sky-400 px-6 py-3 font-bold text-slate-950"
            >
              Resume
            </button>
          </div>
        </div>
      )}
      {uiPhase === "playing" && isHit && (
        <div
          role="status"
          className="pointer-events-none absolute inset-0 animate-pulse border-4 border-rose-400"
          aria-label="Hit: temporarily invulnerable"
        />
      )}
      {uiPhase === "resolved" && resolvedOutcome && (
        <div className="pointer-events-none absolute inset-0 z-20 flex items-center justify-center bg-slate-950/85 p-6 text-center text-white">
          <div>
            <p className="text-4xl font-bold">
              {resolvedOutcome.outcome_tag === "win"
                ? (dodgeConfig.copy?.win_text ?? "Survived!")
                : (dodgeConfig.copy?.lose_text ?? "Defeated...")}
            </p>
            <p className="mt-2 text-sky-200">
              {dodgeConfig.result_copy ??
                (resolvedOutcome.outcome_tag === "win"
                  ? `Performance tier: ${performanceTier}`
                  : "Performance tier: Overwhelmed")}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
