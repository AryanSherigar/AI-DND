import { describe, expect, it } from "vitest";
import {
  generateConvergingRing,
  generateFallingRain,
  generateHomingOrbs,
  generateSweepingLines,
  HAZARD_PATTERN_GENERATORS,
  pickNextPattern,
  type HazardPatternType,
  type HazardSpawn,
  type PatternConfig,
} from "../hazardPatterns";

// Deterministic seeded PRNG so pattern-generator tests are reproducible.
function mulberry32(seed: number): () => number {
  let state = seed;
  return () => {
    state |= 0;
    state = (state + 0x6d2b79f5) | 0;
    let t = Math.imul(state ^ (state >>> 15), 1 | state);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const ARENA_WIDTH = 640;
const ARENA_HEIGHT = 480;

function baseConfig(
  densityMultiplier: number,
  speedMultiplier = 1.0,
): PatternConfig {
  return {
    speedMultiplier,
    densityMultiplier,
    arenaWidth: ARENA_WIDTH,
    arenaHeight: ARENA_HEIGHT,
  };
}

function expectWithinArenaBounds(
  spawn: HazardSpawn,
  config: PatternConfig,
): void {
  expect(spawn.x).toBeGreaterThanOrEqual(0);
  expect(spawn.x).toBeLessThanOrEqual(config.arenaWidth);
  expect(spawn.y).toBeGreaterThanOrEqual(0);
  expect(spawn.y).toBeLessThanOrEqual(config.arenaHeight);
}

const PATTERN_TYPES = Object.keys(
  HAZARD_PATTERN_GENERATORS,
) as HazardPatternType[];

describe("hazard pattern generators — bounds", () => {
  it.each(PATTERN_TYPES)(
    "%s never spawns a hazard outside arena bounds",
    (patternType) => {
      const generator = HAZARD_PATTERN_GENERATORS[patternType];
      const config = baseConfig(1.0);
      for (let seed = 1; seed <= 25; seed += 1) {
        const spawns = generator(config, mulberry32(seed * 97));
        for (const spawn of spawns) {
          expectWithinArenaBounds(spawn, config);
        }
      }
    },
  );

  it.each(PATTERN_TYPES)("%s never returns an empty wave", (patternType) => {
    const generator = HAZARD_PATTERN_GENERATORS[patternType];
    const config = baseConfig(1.0);
    const spawns = generator(config, mulberry32(42));
    expect(spawns.length).toBeGreaterThan(0);
  });
});

describe("generateFallingRain", () => {
  it("respects the configured density (count scales with densityMultiplier)", () => {
    const lowDensity = generateFallingRain(baseConfig(0.7), mulberry32(1));
    const highDensity = generateFallingRain(baseConfig(1.4), mulberry32(1));
    expect(lowDensity.length).toBeGreaterThanOrEqual(3);
    expect(lowDensity.length).toBeLessThanOrEqual(5);
    expect(highDensity.length).toBeGreaterThanOrEqual(6);
    expect(highDensity.length).toBeLessThanOrEqual(10);
  });

  it("spawns shard hazards at the top edge falling straight down with no telegraph", () => {
    const spawns = generateFallingRain(baseConfig(1.0, 1.3), mulberry32(7));
    for (const spawn of spawns) {
      expect(spawn.shape).toBe("shard");
      expect(spawn.y).toBe(0);
      expect(spawn.vx).toBe(0);
      expect(spawn.vy).toBeGreaterThan(0);
      expect(spawn.telegraphMs).toBe(0);
    }
  });
});

describe("generateConvergingRing", () => {
  it("respects the configured density (6-10 hazards scaled)", () => {
    const spawns = generateConvergingRing(baseConfig(1.0), mulberry32(3));
    expect(spawns.length).toBeGreaterThanOrEqual(6);
    expect(spawns.length).toBeLessThanOrEqual(10);
  });

  it("spawns magenta-coded orb hazards moving toward the arena center with a telegraph", () => {
    const config = baseConfig(1.0, 1.0);
    const spawns = generateConvergingRing(config, mulberry32(5));
    const centerX = config.arenaWidth / 2;
    const centerY = config.arenaHeight / 2;
    for (const spawn of spawns) {
      expect(spawn.shape).toBe("orb");
      expect(spawn.telegraphMs).toBeGreaterThan(0);
      // velocity should point toward the center from the spawn point —
      // dot product of velocity and the to-center vector must be positive.
      const towardCenterX = centerX - spawn.x;
      const towardCenterY = centerY - spawn.y;
      const dot = spawn.vx * towardCenterX + spawn.vy * towardCenterY;
      expect(dot).toBeGreaterThan(0);
    }
  });
});

describe("generateSweepingLines", () => {
  it("produces exactly one telegraphed beam per wave", () => {
    const spawns = generateSweepingLines(baseConfig(1.0), mulberry32(11));
    expect(spawns.length).toBe(1);
    expect(spawns[0].shape).toBe("beam");
    expect(spawns[0].telegraphMs).toBeGreaterThan(0);
  });

  it("produces both horizontal and vertical orientations across seeds", () => {
    const config = baseConfig(1.0);
    const orientations = new Set<string>();
    for (let seed = 1; seed <= 40; seed += 1) {
      const [beam] = generateSweepingLines(config, mulberry32(seed));
      // Horizontal beams are centered on x (full-width); vertical beams
      // are centered on y (full-height) — see generateSweepingLines.
      const isHorizontal = beam.x === config.arenaWidth / 2;
      orientations.add(isHorizontal ? "horizontal" : "vertical");
    }
    expect(orientations.has("horizontal")).toBe(true);
    expect(orientations.has("vertical")).toBe(true);
  });
});

describe("generateHomingOrbs", () => {
  it("respects the configured density (2-4 hazards scaled)", () => {
    const spawns = generateHomingOrbs(baseConfig(1.0), mulberry32(13));
    expect(spawns.length).toBeGreaterThanOrEqual(2);
    expect(spawns.length).toBeLessThanOrEqual(4);
  });

  it("spawns homing orb hazards flagged for per-frame steering", () => {
    const spawns = generateHomingOrbs(baseConfig(1.0), mulberry32(21));
    for (const spawn of spawns) {
      expect(spawn.shape).toBe("orb");
      expect(spawn.homing).toBe(true);
    }
  });
});

describe("pickNextPattern", () => {
  it("never immediately repeats the previous pattern", () => {
    let previous: HazardPatternType | null = null;
    for (let seed = 1; seed <= 50; seed += 1) {
      const rng = mulberry32(seed);
      const next = pickNextPattern(previous, rng);
      if (previous !== null) {
        expect(next).not.toBe(previous);
      }
      previous = next;
    }
  });

  it("can select any of the 4 pattern types over many draws", () => {
    const seen = new Set<HazardPatternType>();
    let previous: HazardPatternType | null = null;
    for (let seed = 1; seed <= 200; seed += 1) {
      const next = pickNextPattern(previous, mulberry32(seed * 13 + 1));
      seen.add(next);
      previous = next;
    }
    expect(seen.size).toBe(4);
  });
});
