// Owns the PixiJS Application lifecycle and the per-frame simulation loop
// for Ashfall Dodge: player movement, wave-based hazard spawning/movement/
// collision, hit-point tracking, and win/lose/score resolution. Only the
// derived, UI-relevant values (hitPoints/timeRemainingMs) are pushed into
// React state — everything else (positions, velocities, the live-hazard
// list) stays inside the ticker closure. See
// docs/specs/dodge-minigame-design.spec.md §2/§3.4.

import { useEffect, useRef, useState } from "react";
import { Application } from "pixi.js";
import {
  ARENA_HEIGHT,
  ARENA_WIDTH,
  PLAYER_MAX_SPEED,
  PLAYER_RADIUS,
  POST_HIT_INVULNERABILITY_MS,
  WAVE_INTERVAL_MS,
  getDodgePreset,
} from "./difficultyPresets";
import { hazardCollidesWithPlayer } from "./collision";
import {
  attachPlayerControls,
  clampToArena,
  computeVelocity,
  createPlayerControllerState,
} from "./playerController";
import {
  HAZARD_PATTERN_GENERATORS,
  type HazardPatternType,
  type HazardSpawn,
} from "./hazardPatterns";
import type { DodgeMinigameConfig } from "./DodgeMinigame.types";
import { buildArena } from "./scene/arena";
import { buildPlayer } from "./scene/player";
import { buildHazardLayer, type LiveHazard } from "./scene/hazards";
import { playHitSfx, playLoseStinger, playWinStinger } from "./dodgeAudio";

export interface DodgeOutcome {
  outcome_tag: "win" | "lose";
  score: number;
}

export interface UseGameLoopResult {
  hitPoints: number;
  maxHitPoints: number;
  timeRemainingMs: number;
  durationMs: number;
  canvasContainerRef: React.RefObject<HTMLDivElement>;
  /** Begins the simulation — call once the visual "3…2…1…Go" countdown finishes. */
  start: () => void;
  pause: () => void;
  resume: () => void;
  isHit: boolean;
  isPaused: boolean;
}

const OFFSCREEN_MARGIN_PX = 40;
const BEAM_ACTIVE_MS = 500;
const HOMING_TURN_RATE_RAD_PER_SEC = Math.PI * 0.6;
const RESOLUTION_SLOWMO_SPEED = 0.3;
const CONFIG_PATTERN_MAP: Record<string, HazardPatternType> = {
  rain: "falling_rain",
  ring: "converging_ring",
  beam: "sweeping_lines",
  homing: "homing_orbs",
  falling_rain: "falling_rain",
  converging_ring: "converging_ring",
  sweeping_lines: "sweeping_lines",
  homing_orbs: "homing_orbs",
};

function boundedFinite(
  value: unknown,
  fallback: number,
  minimum: number,
  maximum: number,
): number {
  return typeof value === "number" && Number.isFinite(value)
    ? Math.max(minimum, Math.min(maximum, value))
    : fallback;
}

function isOffscreen(spawn: HazardSpawn): boolean {
  return (
    spawn.x < -OFFSCREEN_MARGIN_PX ||
    spawn.x > ARENA_WIDTH + OFFSCREEN_MARGIN_PX ||
    spawn.y < -OFFSCREEN_MARGIN_PX ||
    spawn.y > ARENA_HEIGHT + OFFSCREEN_MARGIN_PX
  );
}

function shouldDespawn(hazard: LiveHazard): boolean {
  if (isOffscreen(hazard.spawn)) return true;
  return (
    hazard.spawn.shape === "beam" &&
    hazard.elapsedMs >= hazard.spawn.telegraphMs + BEAM_ACTIVE_MS
  );
}

// Capped turn rate so a homing orb is always out-runnable with clean
// movement — never a full snap-to-player vector. See design spec §3.4.
function steerHoming(
  spawn: HazardSpawn,
  targetX: number,
  targetY: number,
  deltaSeconds: number,
): void {
  const currentAngle = Math.atan2(spawn.vy, spawn.vx);
  const desiredAngle = Math.atan2(targetY - spawn.y, targetX - spawn.x);
  const rawDiff = desiredAngle - currentAngle;
  const diff = Math.atan2(Math.sin(rawDiff), Math.cos(rawDiff));
  const maxStep = HOMING_TURN_RATE_RAD_PER_SEC * deltaSeconds;
  const clampedDiff = Math.max(-maxStep, Math.min(maxStep, diff));
  const newAngle = currentAngle + clampedDiff;
  const speed = Math.hypot(spawn.vx, spawn.vy);
  spawn.vx = Math.cos(newAngle) * speed;
  spawn.vy = Math.sin(newAngle) * speed;
}

export function useGameLoop(
  dodgeConfig: DodgeMinigameConfig,
  onComplete: (outcome: DodgeOutcome) => void,
): UseGameLoopResult {
  const preset = getDodgePreset(dodgeConfig.difficulty);
  const requestedDurationMs =
    dodgeConfig.duration_ms ??
    (dodgeConfig.duration_seconds
      ? dodgeConfig.duration_seconds * 1000
      : undefined);
  const durationMs = boundedFinite(
    requestedDurationMs,
    preset.durationMs,
    5_000,
    120_000,
  );
  const maxHitPoints = boundedFinite(
    dodgeConfig.hit_points ?? dodgeConfig.health,
    preset.hitPoints,
    1,
    10,
  );
  const invulnerabilityMs = boundedFinite(
    dodgeConfig.invulnerability_ms,
    POST_HIT_INVULNERABILITY_MS,
    250,
    5_000,
  );
  const configuredPatterns = (
    dodgeConfig.pattern_order ??
    dodgeConfig.enabled_patterns ??
    []
  )
    .map((pattern) => CONFIG_PATTERN_MAP[pattern])
    .filter((pattern): pattern is HazardPatternType => Boolean(pattern));
  const enabledPatterns =
    configuredPatterns.length > 0
      ? [...new Set(configuredPatterns)]
      : (Object.keys(HAZARD_PATTERN_GENERATORS) as HazardPatternType[]);
  const containerRef = useRef<HTMLDivElement>(null);
  const startRef = useRef<() => void>(() => {});
  const pauseRef = useRef<() => void>(() => {});
  const resumeRef = useRef<() => void>(() => {});
  const [hitPoints, setHitPoints] = useState(maxHitPoints);
  const [timeRemainingMs, setTimeRemainingMs] = useState(durationMs);
  const [isHit, setIsHit] = useState(false);
  const [isPaused, setIsPaused] = useState(false);

  const onCompleteRef = useRef(onComplete);
  onCompleteRef.current = onComplete;

  useEffect(() => {
    if (!containerRef.current) return undefined;
    const mountEl = containerRef.current;
    let destroyed = false;
    // PixiJS v8 installs Application-scope plugins (e.g. ResizePlugin,
    // which owns _cancelResize) only once app.init() resolves — calling
    // destroy() any earlier throws "this._cancelResize is not a function".
    // app.stage is not a reliable signal for "init finished" (it can be
    // truthy before then), so this flag is tracked explicitly to survive
    // React StrictMode's mount->cleanup->mount double-invoke in dev, where
    // cleanup can run before the async init() has resolved.
    let isInitialized = false;
    const app = new Application();
    let cleanupControls: (() => void) | null = null;

    async function setup(): Promise<void> {
      await app.init({
        width: ARENA_WIDTH,
        height: ARENA_HEIGHT,
        background: 0x0a0a14,
        antialias: true,
      });
      if (destroyed) {
        app.destroy({ removeView: true }, { children: true });
        return;
      }
      isInitialized = true;
      mountEl.appendChild(app.canvas);

      const arena = buildArena({
        background: dodgeConfig.background,
        texture: dodgeConfig.texture,
        palette: dodgeConfig.palette,
        backgroundAssetUrl: dodgeConfig.background_asset_url,
      });
      // Styles are deliberately passed only to renderers; movement and
      // collision continue to use the fixed PLAYER_RADIUS/hazard radii.
      const player = buildPlayer(dodgeConfig.player_style);
      const hazardLayer = buildHazardLayer(ARENA_WIDTH, ARENA_HEIGHT, {
        style: dodgeConfig.obstacle_style,
        color: dodgeConfig.obstacle_color,
      });
      app.stage.addChild(
        arena.container,
        hazardLayer.container,
        player.container,
      );

      const controllerState = createPlayerControllerState();
      cleanupControls = attachPlayerControls(controllerState, app.canvas, () =>
        pauseRef.current(),
      );
      app.canvas.tabIndex = 0;
      app.canvas.setAttribute(
        "aria-label",
        "Ashfall Dodge arena. Use W A S D to move.",
      );

      let playerX = ARENA_WIDTH / 2;
      let playerY = ARENA_HEIGHT / 2;
      player.updatePosition(playerX, playerY);

      let liveHazards: LiveHazard[] = [];
      let lastPattern: HazardPatternType | null = null;
      let orderedPatternIndex = 0;
      let elapsedMs = 0;
      let sinceWaveMs = WAVE_INTERVAL_MS; // first wave spawns on the first tick
      let invulnUntilMs = -Infinity;
      let currentHitPoints = maxHitPoints;
      let hasStarted = false;
      let paused = false;
      let skipResumedFrame = false;
      let resolved = false;

      startRef.current = () => {
        if (resolved) return;
        hasStarted = true;
        app.canvas.focus();
      };
      pauseRef.current = () => {
        if (!hasStarted || resolved) return;
        paused = true;
        controllerState.keysDown.clear();
        setIsPaused(true);
      };
      resumeRef.current = () => {
        if (!hasStarted || resolved) return;
        controllerState.keysDown.clear();
        paused = false;
        // Browsers can deliver a single large ticker delta after a hidden tab
        // resumes. Discard it so a pause can never consume encounter time.
        skipResumedFrame = true;
        setIsPaused(false);
        app.canvas.focus();
      };

      const spawnWave = (): void => {
        const isExplicitOrder = (dodgeConfig.pattern_order?.length ?? 0) > 0;
        const candidates = enabledPatterns.filter(
          (pattern) => pattern !== lastPattern,
        );
        const patternType = isExplicitOrder
          ? enabledPatterns[orderedPatternIndex++ % enabledPatterns.length]
          : (candidates[Math.floor(Math.random() * candidates.length)] ??
            enabledPatterns[0]);
        lastPattern = patternType;
        const spawns = HAZARD_PATTERN_GENERATORS[patternType](
          {
            speedMultiplier: preset.hazardSpeedMultiplier,
            densityMultiplier: preset.hazardDensityMultiplier,
            arenaWidth: ARENA_WIDTH,
            arenaHeight: ARENA_HEIGHT,
          },
          Math.random,
        );
        liveHazards.push(...hazardLayer.spawn(spawns, patternType));
      };

      const resolve = (outcome: DodgeOutcome): void => {
        if (resolved) return;
        resolved = true;
        app.ticker.speed = RESOLUTION_SLOWMO_SPEED;
        if (outcome.outcome_tag === "win") playWinStinger();
        else playLoseStinger();
        onCompleteRef.current(outcome);
      };

      app.ticker.add((ticker) => {
        if (resolved || !hasStarted || paused || skipResumedFrame) {
          skipResumedFrame = false;
          return;
        }
        // Clamp a background/throttled frame as a second fairness guard.
        const deltaMs = Math.min(ticker.deltaMS, 50);
        elapsedMs += deltaMs;
        sinceWaveMs += deltaMs;

        if (sinceWaveMs >= WAVE_INTERVAL_MS) {
          sinceWaveMs = 0;
          spawnWave();
        }

        const deltaSeconds = deltaMs / 1000;
        const velocity = computeVelocity(
          controllerState,
          playerX,
          playerY,
          PLAYER_MAX_SPEED,
        );
        const clamped = clampToArena(
          playerX + velocity.vx * deltaSeconds,
          playerY + velocity.vy * deltaSeconds,
          PLAYER_RADIUS,
          ARENA_WIDTH,
          ARENA_HEIGHT,
        );
        playerX = clamped.x;
        playerY = clamped.y;
        player.updatePosition(playerX, playerY);

        hazardLayer.updatePositions(liveHazards, deltaMs, deltaSeconds);
        for (const hazard of liveHazards) {
          if (hazard.spawn.homing)
            steerHoming(hazard.spawn, playerX, playerY, deltaSeconds);
        }
        liveHazards = liveHazards.filter((hazard) => {
          if (!shouldDespawn(hazard)) return true;
          hazardLayer.despawn(hazard);
          return false;
        });

        const isInvulnerable = elapsedMs < invulnUntilMs;
        setIsHit(isInvulnerable);
        player.advance(deltaMs, isInvulnerable);
        arena.updateBoundaryTint(currentHitPoints / maxHitPoints);

        if (!isInvulnerable) {
          const hit = liveHazards.find((hazard) =>
            hazardCollidesWithPlayer(
              playerX,
              playerY,
              PLAYER_RADIUS,
              {
                isTelegraphing: hazard.isTelegraphing,
                shape: hazard.spawn.shape,
                x: hazard.spawn.x,
                y: hazard.spawn.y,
                radius: hazard.spawn.radius,
              },
              ARENA_WIDTH,
            ),
          );
          if (hit) {
            currentHitPoints -= 1;
            setHitPoints(currentHitPoints);
            invulnUntilMs = elapsedMs + invulnerabilityMs;
            setIsHit(true);
            player.playHitFlash();
            playHitSfx();
          }
        }

        setTimeRemainingMs(Math.max(0, durationMs - elapsedMs));

        // Loss takes precedence on a simultaneous win/loss frame (design
        // spec §4 edge case) — checked before the duration check.
        if (currentHitPoints <= 0) {
          resolve({ outcome_tag: "lose", score: 0 });
        } else if (elapsedMs >= durationMs) {
          resolve({ outcome_tag: "win", score: currentHitPoints });
        }
      });
    }

    void setup();

    return () => {
      destroyed = true;
      cleanupControls?.();
      startRef.current = () => {};
      pauseRef.current = () => {};
      resumeRef.current = () => {};
      // If init() hasn't resolved yet, don't destroy here — setup()'s own
      // post-await `destroyed` check above handles teardown once init
      // finishes, which is the earliest point destroy() is safe to call.
      if (isInitialized) {
        app.destroy({ removeView: true }, { children: true });
      }
    };
    // difficulty is intentionally the only dependency — a reload mid-game
    // restarts the encounter fresh (design spec §4 accepted simplification),
    // and onComplete is captured via a ref so its identity never restarts
    // the effect.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dodgeConfig.difficulty]);

  const start = (): void => startRef.current();
  const pause = (): void => pauseRef.current();
  const resume = (): void => resumeRef.current();

  return {
    hitPoints,
    maxHitPoints,
    timeRemainingMs,
    durationMs,
    canvasContainerRef: containerRef,
    start,
    pause,
    resume,
    isHit,
    isPaused,
  };
}
