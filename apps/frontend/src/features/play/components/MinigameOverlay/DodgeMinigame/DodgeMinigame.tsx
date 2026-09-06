import { useEffect, useRef, useState } from "react";
import { useGameLoop, type DodgeOutcome } from "./useGameLoop";
import { enterMinigameAudio } from "./dodgeAudio";
import { getDodgePreset } from "./difficultyPresets";
import { HUD } from "./HUD";
import { DodgeMinigameProps } from "./DodgeMinigame.types";

type UiPhase = "countdown" | "playing" | "resolved";

const COUNTDOWN_STEPS = ["3", "2", "1", "Go!"];
const COUNTDOWN_STEP_MS = 700;
const RESOLUTION_BEAT_MS = 500;

/**
 * Orchestrates one Ashfall Dodge encounter: countdown -> playing ->
 * resolved. Mounts useGameLoop (owns the PixiJS Application + simulation)
 * and HUD (the DOM overlay), and is the only piece of this subtree that
 * knows about the countdown/resolution-beat presentation. Entirely
 * self-contained — no network calls, no play.store.ts/SSE knowledge; the
 * parent MinigameOverlay owns turning `onComplete` into a submitted result.
 * See docs/specs/dodge-minigame-design.spec.md.
 */
export function DodgeMinigame({ dodgeConfig, onComplete }: DodgeMinigameProps) {
  const preset = getDodgePreset(dodgeConfig.difficulty);
  const [countdownIndex, setCountdownIndex] = useState(0);
  const [uiPhase, setUiPhase] = useState<UiPhase>("countdown");
  const resolvedOutcomeRef = useRef<DodgeOutcome | null>(null);

  const handleInternalComplete = (outcome: DodgeOutcome): void => {
    resolvedOutcomeRef.current = outcome;
    setUiPhase("resolved");
    window.setTimeout(() => onComplete(outcome), RESOLUTION_BEAT_MS);
  };

  const { hitPoints, maxHitPoints, timeRemainingMs, canvasContainerRef, start } = useGameLoop(
    dodgeConfig.difficulty,
    handleInternalComplete,
  );

  useEffect(() => enterMinigameAudio(), []);

  useEffect(() => {
    if (countdownIndex >= COUNTDOWN_STEPS.length) {
      setUiPhase("playing");
      start();
      return undefined;
    }
    const timeoutId = window.setTimeout(
      () => setCountdownIndex((n) => n + 1),
      COUNTDOWN_STEP_MS,
    );
    return () => window.clearTimeout(timeoutId);
  }, [countdownIndex, start]);

  const resolvedOutcome = resolvedOutcomeRef.current;

  return (
    <div className="relative flex flex-col items-center gap-3">
      <div
        ref={canvasContainerRef}
        className="relative overflow-hidden rounded-2xl shadow-[0_0_40px_rgba(126,200,255,0.25)]"
      />
      {uiPhase === "playing" && (
        <HUD
          hitPoints={hitPoints}
          maxHitPoints={maxHitPoints}
          timeRemainingMs={timeRemainingMs}
          durationMs={preset.durationMs}
        />
      )}
      {uiPhase === "countdown" && (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center text-6xl font-bold text-white drop-shadow-lg">
          {COUNTDOWN_STEPS[countdownIndex]}
        </div>
      )}
      {uiPhase === "resolved" && resolvedOutcome && (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center bg-white/20 text-5xl font-bold text-white">
          {resolvedOutcome.outcome_tag === "win" ? "Survived!" : "Defeated..."}
        </div>
      )}
    </div>
  );
}
