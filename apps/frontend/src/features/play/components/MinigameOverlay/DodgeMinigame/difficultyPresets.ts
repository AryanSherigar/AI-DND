// Difficulty presets for Ashfall Dodge. See docs/specs/dodge-minigame-design.spec.md §3.4.
// The creator-facing knob is a single 1-5 slider (dodge_config.difficulty) —
// every other tuning value is derived from this table, never authored directly.

export interface DodgePreset {
  durationMs: number;
  hitPoints: number;
  hazardSpeedMultiplier: number;
  hazardDensityMultiplier: number;
}

// Difficulty 1 (gentlest) through 5 (hardest). Every field moves
// monotonically harder as difficulty increases — enforced by a unit test.
export const DODGE_DIFFICULTY_PRESETS: Record<number, DodgePreset> = {
  1: {
    durationMs: 10_000,
    hitPoints: 5,
    hazardSpeedMultiplier: 1.0,
    hazardDensityMultiplier: 0.7,
  },
  2: {
    durationMs: 12_000,
    hitPoints: 4,
    hazardSpeedMultiplier: 1.15,
    hazardDensityMultiplier: 0.85,
  },
  3: {
    durationMs: 15_000,
    hitPoints: 3,
    hazardSpeedMultiplier: 1.3,
    hazardDensityMultiplier: 1.0,
  },
  4: {
    durationMs: 18_000,
    hitPoints: 3,
    hazardSpeedMultiplier: 1.5,
    hazardDensityMultiplier: 1.2,
  },
  5: {
    durationMs: 20_000,
    hitPoints: 2,
    hazardSpeedMultiplier: 1.75,
    hazardDensityMultiplier: 1.4,
  },
};

export const DODGE_MIN_DIFFICULTY = 1;
export const DODGE_MAX_DIFFICULTY = 5;
export const DODGE_DEFAULT_DIFFICULTY = 3;

export const ARENA_WIDTH = 640;
export const ARENA_HEIGHT = 480;
export const PLAYER_RADIUS = 12;
export const PLAYER_MAX_SPEED = 260; // px/sec
export const POST_HIT_INVULNERABILITY_MS = 1000;
export const WAVE_INTERVAL_MS = 3500; // how often a new hazard-pattern wave begins

// NOTE: creator-facing difficulty is always an integer 1-5. A fractional or
// out-of-range value falls back to the closest valid tier rather than
// throwing mid-encounter — see getDodgePreset below.
export function getDodgePreset(difficulty: number): DodgePreset {
  const clamped = Math.min(
    DODGE_MAX_DIFFICULTY,
    Math.max(DODGE_MIN_DIFFICULTY, Math.round(difficulty)),
  );
  return (
    DODGE_DIFFICULTY_PRESETS[clamped] ??
    DODGE_DIFFICULTY_PRESETS[DODGE_DEFAULT_DIFFICULTY]
  );
}
