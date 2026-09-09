// Player sprite/graphics for Ashfall Dodge: a small glowing orb built from
// layered blurred circles (see DodgeMinigame's report for why this was
// chosen over the @pixi/filter-glow / pixi-filters package — no extra
// dependency, and PixiJS v8 ships BlurFilter in core). Plain PixiJS
// module, no React — see docs/specs/dodge-minigame-design.spec.md §3.4.

import { BlurFilter, Container, Graphics } from "pixi.js";
import { PLAYER_RADIUS } from "../difficultyPresets";
import type { DodgePlayerStyle } from "@/shared/types/minigame.types";

const PLAYER_CORE_COLOR = 0xe8f6ff;
const PLAYER_GLOW_COLOR = 0x7ec8ff;
const PLAYER_HIT_FLASH_COLOR = 0xff4d4d;

const OUTER_GLOW_RADIUS_MULTIPLIER = 2.4;
const OUTER_GLOW_BLUR_STRENGTH = 9;
const OUTER_GLOW_ALPHA = 0.5;
const INNER_GLOW_RADIUS_MULTIPLIER = 1.5;
const INNER_GLOW_BLUR_STRENGTH = 4;
const INNER_GLOW_ALPHA = 0.4;

const HIT_FLASH_DURATION_MS = 200;
const HIT_FLASH_PEAK_SCALE = 1.4;
const INVULNERABILITY_BLINK_HZ = 10;
const INVULNERABILITY_MIN_ALPHA = 0.25;

export interface PlayerScene {
  container: Container;
  updatePosition: (x: number, y: number) => void;
  playHitFlash: () => void;
  // Advances the flash/scale-pulse and invulnerability-blink animations.
  // Called once per ticker frame by useGameLoop with the frame's elapsed
  // ms and whether the player is currently within the post-hit
  // invulnerability window.
  advance: (deltaMs: number, isInvulnerable: boolean) => void;
}

export function buildPlayer(style: DodgePlayerStyle = "soul"): PlayerScene {
  const container = new Container();

  const outerGlow = new Graphics()
    .circle(0, 0, PLAYER_RADIUS * OUTER_GLOW_RADIUS_MULTIPLIER)
    .fill({ color: PLAYER_GLOW_COLOR, alpha: OUTER_GLOW_ALPHA });
  outerGlow.filters = [new BlurFilter({ strength: OUTER_GLOW_BLUR_STRENGTH })];

  const innerGlow = new Graphics()
    .circle(0, 0, PLAYER_RADIUS * INNER_GLOW_RADIUS_MULTIPLIER)
    .fill({ color: PLAYER_GLOW_COLOR, alpha: INNER_GLOW_ALPHA });
  innerGlow.filters = [new BlurFilter({ strength: INNER_GLOW_BLUR_STRENGTH })];

  const core = new Graphics();
  if (style === "heart") {
    // Visual only: the fixed circular PLAYER_RADIUS collision remains in the loop.
    core
      .moveTo(0, PLAYER_RADIUS * 0.8)
      .bezierCurveTo(
        -PLAYER_RADIUS * 2,
        -PLAYER_RADIUS * 0.35,
        -PLAYER_RADIUS * 0.65,
        -PLAYER_RADIUS * 1.4,
        0,
        -PLAYER_RADIUS * 0.45,
      )
      .bezierCurveTo(
        PLAYER_RADIUS * 0.65,
        -PLAYER_RADIUS * 1.4,
        PLAYER_RADIUS * 2,
        -PLAYER_RADIUS * 0.35,
        0,
        PLAYER_RADIUS * 0.8,
      )
      .fill(PLAYER_CORE_COLOR);
  } else if (style === "spark") {
    core
      .poly([
        0,
        -PLAYER_RADIUS,
        PLAYER_RADIUS * 0.38,
        -PLAYER_RADIUS * 0.3,
        PLAYER_RADIUS,
        0,
        PLAYER_RADIUS * 0.38,
        PLAYER_RADIUS * 0.3,
        0,
        PLAYER_RADIUS,
        -PLAYER_RADIUS * 0.38,
        PLAYER_RADIUS * 0.3,
        -PLAYER_RADIUS,
        0,
        -PLAYER_RADIUS * 0.38,
        -PLAYER_RADIUS * 0.3,
      ])
      .fill(PLAYER_CORE_COLOR);
  } else {
    core.circle(0, 0, PLAYER_RADIUS).fill(PLAYER_CORE_COLOR);
  }

  container.addChild(outerGlow, innerGlow, core);

  let flashElapsedMs: number | null = null;

  const updatePosition = (x: number, y: number): void => {
    container.position.set(x, y);
  };

  const playHitFlash = (): void => {
    flashElapsedMs = 0;
  };

  const applyFlashAnimation = (deltaMs: number): void => {
    if (flashElapsedMs === null) return;
    flashElapsedMs += deltaMs;
    if (flashElapsedMs >= HIT_FLASH_DURATION_MS) {
      flashElapsedMs = null;
      container.scale.set(1);
      core.tint = PLAYER_CORE_COLOR;
      return;
    }
    const progress = flashElapsedMs / HIT_FLASH_DURATION_MS;
    const pulse = Math.sin(progress * Math.PI); // 0 -> 1 -> 0
    container.scale.set(1 + pulse * (HIT_FLASH_PEAK_SCALE - 1));
    core.tint = PLAYER_HIT_FLASH_COLOR;
  };

  let invulnerabilityClockMs = 0;
  const applyInvulnerabilityBlink = (
    deltaMs: number,
    isInvulnerable: boolean,
  ): void => {
    if (!isInvulnerable) {
      invulnerabilityClockMs = 0;
      container.alpha = 1;
      return;
    }
    invulnerabilityClockMs += deltaMs;
    const cyclePosition =
      (invulnerabilityClockMs / 1000) * INVULNERABILITY_BLINK_HZ;
    const blink = (Math.sin(cyclePosition * Math.PI * 2) + 1) / 2; // 0..1
    container.alpha =
      INVULNERABILITY_MIN_ALPHA + blink * (1 - INVULNERABILITY_MIN_ALPHA);
  };

  const advance = (deltaMs: number, isInvulnerable: boolean): void => {
    applyFlashAnimation(deltaMs);
    applyInvulnerabilityBlink(deltaMs, isInvulnerable);
  };

  return { container, updatePosition, playHitFlash, advance };
}
