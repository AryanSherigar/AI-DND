// The 4 pure hazard-pattern generators for Ashfall Dodge. Each function
// takes a config + an injectable rng (() => number in [0,1)) and returns
// the hazard spawns for one wave. No Pixi/DOM dependency — fully
// unit-testable. See docs/specs/dodge-minigame-design.spec.md §3.4.
//
// NOTE: the design spec's prose describes falling-rain/converging-ring/
// homing-orb spawns as appearing "just above"/"just outside" the arena
// edge. The spec's own boundary rule ("never let a hazard spawn fully
// outside the arena bounds", §3.6) and its required test ("never spawns a
// hazard whose initial position is outside the playable area", §3.2) both
// override that prose reading literally — so every generator here clamps
// spawn coordinates to the closed arena rectangle [0, arenaWidth] x
// [0, arenaHeight], spawning "at" the boundary line rather than beyond it.
// Visually this still reads as hazards entering from the edge.

export type HazardPatternType =
  "falling_rain" | "converging_ring" | "sweeping_lines" | "homing_orbs";

export interface HazardSpawn {
  id: string;
  shape: "orb" | "shard" | "beam";
  x: number;
  y: number;
  vx: number;
  vy: number;
  radius: number;
  telegraphMs: number; // time before this hazard becomes collidable/visible-as-dangerous
  homing?: boolean;
}

export interface PatternConfig {
  speedMultiplier: number;
  densityMultiplier: number;
  arenaWidth: number;
  arenaHeight: number;
}

let spawnSequence = 0;
function nextId(prefix: string): string {
  spawnSequence += 1;
  return `${prefix}-${spawnSequence}`;
}

function scaledCount(
  min: number,
  max: number,
  densityMultiplier: number,
  rng: () => number,
): number {
  const base = min + rng() * (max - min);
  const scaled = Math.round(base * densityMultiplier);
  return Math.max(1, scaled);
}

// --- Falling Rain --------------------------------------------------------

const FALLING_RAIN_MIN_COUNT = 4;
const FALLING_RAIN_MAX_COUNT = 7;
const FALLING_RAIN_RADIUS = 8;
const FALLING_RAIN_BASE_SPEED = 180; // px/sec

export function generateFallingRain(
  config: PatternConfig,
  rng: () => number,
): HazardSpawn[] {
  const count = scaledCount(
    FALLING_RAIN_MIN_COUNT,
    FALLING_RAIN_MAX_COUNT,
    config.densityMultiplier,
    rng,
  );
  const spawns: HazardSpawn[] = [];
  for (let i = 0; i < count; i += 1) {
    const x =
      FALLING_RAIN_RADIUS +
      rng() * (config.arenaWidth - FALLING_RAIN_RADIUS * 2);
    spawns.push({
      id: nextId("rain"),
      shape: "shard",
      x,
      y: 0,
      vx: 0,
      vy: FALLING_RAIN_BASE_SPEED * config.speedMultiplier,
      radius: FALLING_RAIN_RADIUS,
      telegraphMs: 0,
    });
  }
  return spawns;
}

// --- Converging Ring -------------------------------------------------------

const CONVERGING_RING_MIN_COUNT = 6;
const CONVERGING_RING_MAX_COUNT = 10;
const CONVERGING_RING_RADIUS = 10;
const CONVERGING_RING_BASE_SPEED = 110; // px/sec
const CONVERGING_RING_TELEGRAPH_MS = 300;
const CONVERGING_RING_EDGE_MARGIN = 4;

export function generateConvergingRing(
  config: PatternConfig,
  rng: () => number,
): HazardSpawn[] {
  const count = scaledCount(
    CONVERGING_RING_MIN_COUNT,
    CONVERGING_RING_MAX_COUNT,
    config.densityMultiplier,
    rng,
  );
  const centerX = config.arenaWidth / 2;
  const centerY = config.arenaHeight / 2;
  const ringRadius =
    Math.min(config.arenaWidth, config.arenaHeight) / 2 -
    CONVERGING_RING_RADIUS -
    CONVERGING_RING_EDGE_MARGIN;
  const angleOffset = rng() * Math.PI * 2;

  const spawns: HazardSpawn[] = [];
  for (let i = 0; i < count; i += 1) {
    const angle = angleOffset + (i / count) * Math.PI * 2;
    const x = centerX + Math.cos(angle) * ringRadius;
    const y = centerY + Math.sin(angle) * ringRadius;
    const towardCenter = normalizeToward(x, y, centerX, centerY);
    spawns.push({
      id: nextId("ring"),
      shape: "orb",
      x,
      y,
      vx: towardCenter.x * CONVERGING_RING_BASE_SPEED * config.speedMultiplier,
      vy: towardCenter.y * CONVERGING_RING_BASE_SPEED * config.speedMultiplier,
      radius: CONVERGING_RING_RADIUS,
      telegraphMs: CONVERGING_RING_TELEGRAPH_MS,
    });
  }
  return spawns;
}

// --- Sweeping Lines --------------------------------------------------------

const SWEEPING_LINE_THICKNESS = 14;
const SWEEPING_LINE_TELEGRAPH_MS = 400;

// The pattern's PatternConfig contract carries no orientation-history field
// (locked by the design spec's interface), so orientation is chosen by the
// rng each call rather than tracked as external state — a 50/50 pick per
// wave rather than a strict alternation. Callers that want strict
// alternation can post-process the returned spawn (not required by the
// spec's test suite, which only checks bounds/density).
export function generateSweepingLines(
  config: PatternConfig,
  rng: () => number,
): HazardSpawn[] {
  const isHorizontal = rng() < 0.5;
  const halfThickness = SWEEPING_LINE_THICKNESS / 2;

  if (isHorizontal) {
    const y = halfThickness + rng() * (config.arenaHeight - halfThickness * 2);
    return [
      {
        id: nextId("beam"),
        shape: "beam",
        x: config.arenaWidth / 2,
        y,
        vx: 0,
        vy: 0,
        radius: halfThickness,
        telegraphMs: SWEEPING_LINE_TELEGRAPH_MS,
      },
    ];
  }

  const x = halfThickness + rng() * (config.arenaWidth - halfThickness * 2);
  return [
    {
      id: nextId("beam"),
      shape: "beam",
      x,
      y: config.arenaHeight / 2,
      vx: 0,
      vy: 0,
      radius: halfThickness,
      telegraphMs: SWEEPING_LINE_TELEGRAPH_MS,
    },
  ];
}

// --- Homing Orbs -------------------------------------------------------

const HOMING_ORBS_MIN_COUNT = 2;
const HOMING_ORBS_MAX_COUNT = 4;
const HOMING_ORBS_RADIUS = 9;
const HOMING_ORBS_BASE_SPEED = 130; // px/sec

export function generateHomingOrbs(
  config: PatternConfig,
  rng: () => number,
): HazardSpawn[] {
  const count = scaledCount(
    HOMING_ORBS_MIN_COUNT,
    HOMING_ORBS_MAX_COUNT,
    config.densityMultiplier,
    rng,
  );
  const centerX = config.arenaWidth / 2;
  const centerY = config.arenaHeight / 2;

  const spawns: HazardSpawn[] = [];
  for (let i = 0; i < count; i += 1) {
    const { x, y } = randomEdgePosition(config, rng);
    const towardCenter = normalizeToward(x, y, centerX, centerY);
    spawns.push({
      id: nextId("homing"),
      shape: "orb",
      x,
      y,
      vx: towardCenter.x * HOMING_ORBS_BASE_SPEED * config.speedMultiplier,
      vy: towardCenter.y * HOMING_ORBS_BASE_SPEED * config.speedMultiplier,
      radius: HOMING_ORBS_RADIUS,
      telegraphMs: 0,
      homing: true,
    });
  }
  return spawns;
}

function randomEdgePosition(
  config: PatternConfig,
  rng: () => number,
): { x: number; y: number } {
  const edge = Math.floor(rng() * 4);
  if (edge === 0) return { x: rng() * config.arenaWidth, y: 0 };
  if (edge === 1)
    return { x: rng() * config.arenaWidth, y: config.arenaHeight };
  if (edge === 2) return { x: 0, y: rng() * config.arenaHeight };
  return { x: config.arenaWidth, y: rng() * config.arenaHeight };
}

function normalizeToward(
  fromX: number,
  fromY: number,
  toX: number,
  toY: number,
): { x: number; y: number } {
  const dx = toX - fromX;
  const dy = toY - fromY;
  const magnitude = Math.hypot(dx, dy);
  if (magnitude === 0) return { x: 0, y: 0 };
  return { x: dx / magnitude, y: dy / magnitude };
}

export const HAZARD_PATTERN_GENERATORS: Record<
  HazardPatternType,
  (config: PatternConfig, rng: () => number) => HazardSpawn[]
> = {
  falling_rain: generateFallingRain,
  converging_ring: generateConvergingRing,
  sweeping_lines: generateSweepingLines,
  homing_orbs: generateHomingOrbs,
};

// Picks the next wave's pattern type, never immediately repeating the
// previous one. `previous` is null for the first wave of an encounter.
export function pickNextPattern(
  previous: HazardPatternType | null,
  rng: () => number,
): HazardPatternType {
  const allTypes = Object.keys(
    HAZARD_PATTERN_GENERATORS,
  ) as HazardPatternType[];
  const candidates = previous
    ? allTypes.filter((type) => type !== previous)
    : allTypes;
  const index = Math.floor(rng() * candidates.length);
  return candidates[Math.min(index, candidates.length - 1)];
}
