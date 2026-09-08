// Pools/creates/recycles hazard sprites per pattern type and shape
// (orb/shard/beam), color-coded per pattern for instant readability. Plain
// PixiJS module, no React — see
// docs/specs/dodge-minigame-design.spec.md §3.4/§3.6.

import { Container, Graphics } from "pixi.js";
import type { HazardPatternType, HazardSpawn } from "../hazardPatterns";
import type { DodgeObstacleStyle } from "@/shared/types/minigame.types";

const HAZARD_COLOR_BY_PATTERN: Record<HazardPatternType, number> = {
  falling_rain: 0xffb14d, // amber
  converging_ring: 0xe64dff, // magenta
  sweeping_lines: 0xff3b3b, // red-flash
  homing_orbs: 0x9a4dff, // purple
};

const TELEGRAPH_ALPHA = 0.35;
const SOLID_ALPHA = 1;
const HOMING_TRAIL_LENGTH = 4;
const HOMING_TRAIL_ALPHA_STEP = 0.12;

export interface LiveHazard {
  spawn: HazardSpawn;
  patternType: HazardPatternType;
  graphics: Graphics;
  trail: Graphics[];
  trailHistory: { x: number; y: number }[];
  elapsedMs: number;
  isTelegraphing: boolean;
}

export interface HazardLayer {
  container: Container;
  spawn: (spawns: HazardSpawn[], patternType: HazardPatternType) => LiveHazard[];
  updatePositions: (hazards: LiveHazard[], deltaMs: number, deltaSeconds: number) => void;
  despawn: (hazard: LiveHazard) => void;
  despawnAll: (hazards: LiveHazard[]) => void;
}

export interface HazardAppearance {
  style?: DodgeObstacleStyle;
  color?: string;
}

/** Parses the only supported creator color format without accepting arbitrary CSS. */
export function parseObstacleColor(value: string | undefined): number | null {
  if (!value || !/^#[\da-fA-F]{6}$/.test(value)) return null;
  return Number.parseInt(value.slice(1), 16);
}

// Orbs and shards are drawn centered on the hazard's own local origin;
// beams are handled separately by renderBeamOrShape since they need the
// arena dimensions to span the full width/height.
function drawOrbOrShard(graphics: Graphics, spawn: HazardSpawn, color: number, style: DodgeObstacleStyle): void {
  graphics.clear();
  if (style === "crystal") {
    graphics.poly([0, -spawn.radius * 1.3, spawn.radius, 0, 0, spawn.radius * 1.3, -spawn.radius, 0]).fill(color);
    return;
  }
  if (style === "neon") {
    // This treatment is intentionally render-only: both shapes retain the
    // same spawn.radius hitbox used by the simulation.
    if (spawn.shape === "shard") {
      graphics
        .moveTo(0, -spawn.radius * 1.4)
        .lineTo(spawn.radius * 0.7, spawn.radius * 0.4)
        .arc(0, spawn.radius * 0.4, spawn.radius * 0.7, 0, Math.PI, false)
        .lineTo(0, -spawn.radius * 1.4)
        .fill({ color, alpha: 0.35 })
        .stroke({ color: 0xffffff, width: 1.5, alpha: 0.9 });
      return;
    }
    graphics
      .circle(0, 0, spawn.radius)
      .fill({ color, alpha: 0.32 })
      .stroke({ color: 0xffffff, width: 1.5, alpha: 0.9 })
      .circle(0, 0, Math.max(1, spawn.radius * 0.35))
      .fill(color);
    return;
  }
  if (spawn.shape === "shard") {
    drawTeardrop(graphics, spawn.radius, color);
    return;
  }
  graphics.circle(0, 0, spawn.radius).fill(color);
}

function drawTeardrop(graphics: Graphics, radius: number, color: number): void {
  graphics
    .moveTo(0, -radius * 1.4)
    .lineTo(radius * 0.7, radius * 0.4)
    .arc(0, radius * 0.4, radius * 0.7, 0, Math.PI, false)
    .lineTo(0, -radius * 1.4)
    .fill(color);
}

export function buildHazardLayer(
  arenaWidth: number,
  arenaHeight: number,
  appearance: HazardAppearance = {},
): HazardLayer {
  const container = new Container();
  const style = appearance.style ?? "ash";
  const customColor = parseObstacleColor(appearance.color);

  const spawn = (spawns: HazardSpawn[], patternType: HazardPatternType): LiveHazard[] => {
    const color = customColor ?? HAZARD_COLOR_BY_PATTERN[patternType];
    return spawns.map((hazardSpawn) => {
      const graphics = new Graphics();
      renderBeamOrShape(graphics, hazardSpawn, color, arenaWidth, arenaHeight, style);
      graphics.position.set(hazardSpawn.x, hazardSpawn.y);
      graphics.alpha = hazardSpawn.telegraphMs > 0 ? TELEGRAPH_ALPHA : SOLID_ALPHA;
      container.addChild(graphics);

      const trail: Graphics[] = [];
      if (hazardSpawn.homing) {
        for (let i = 0; i < HOMING_TRAIL_LENGTH; i += 1) {
          const ghost = new Graphics().circle(0, 0, hazardSpawn.radius).fill(color);
          ghost.alpha = Math.max(0, SOLID_ALPHA - HOMING_TRAIL_ALPHA_STEP * (i + 1) * 2);
          ghost.position.set(hazardSpawn.x, hazardSpawn.y);
          container.addChildAt(ghost, 0);
          trail.push(ghost);
        }
      }

      return {
        spawn: hazardSpawn,
        patternType,
        graphics,
        trail,
        trailHistory: [],
        elapsedMs: 0,
        isTelegraphing: hazardSpawn.telegraphMs > 0,
      };
    });
  };

  const updatePositions = (hazards: LiveHazard[], deltaMs: number, deltaSeconds: number): void => {
    for (const hazard of hazards) {
      hazard.elapsedMs += deltaMs;
      if (hazard.isTelegraphing && hazard.elapsedMs >= hazard.spawn.telegraphMs) {
        hazard.isTelegraphing = false;
        hazard.graphics.alpha = SOLID_ALPHA;
      }

      hazard.spawn.x += hazard.spawn.vx * deltaSeconds;
      hazard.spawn.y += hazard.spawn.vy * deltaSeconds;
      hazard.graphics.position.set(hazard.spawn.x, hazard.spawn.y);

      if (hazard.spawn.homing) {
        updateTrail(hazard);
      }
    }
  };

  const despawn = (hazard: LiveHazard): void => {
    container.removeChild(hazard.graphics);
    hazard.graphics.destroy();
    for (const ghost of hazard.trail) {
      container.removeChild(ghost);
      ghost.destroy();
    }
  };

  const despawnAll = (hazards: LiveHazard[]): void => {
    for (const hazard of hazards) despawn(hazard);
  };

  return { container, spawn, updatePositions, despawn, despawnAll };
}

function updateTrail(hazard: LiveHazard): void {
  hazard.trailHistory.unshift({ x: hazard.spawn.x, y: hazard.spawn.y });
  if (hazard.trailHistory.length > HOMING_TRAIL_LENGTH) {
    hazard.trailHistory.length = HOMING_TRAIL_LENGTH;
  }
  hazard.trail.forEach((ghost, index) => {
    const position = hazard.trailHistory[index + 1];
    if (position) {
      ghost.position.set(position.x, position.y);
      ghost.visible = true;
    } else {
      ghost.visible = false;
    }
  });
}

function renderBeamOrShape(
  graphics: Graphics,
  spawn: HazardSpawn,
  color: number,
  arenaWidth: number,
  arenaHeight: number,
  style: DodgeObstacleStyle,
): void {
  if (spawn.shape !== "beam") {
    drawOrbOrShard(graphics, spawn, color, style);
    return;
  }
  const isHorizontal = spawn.x === arenaWidth / 2;
  graphics.clear();
  if (isHorizontal) {
    graphics.rect(-arenaWidth / 2, -spawn.radius, arenaWidth, spawn.radius * 2).fill({ color, alpha: style === "neon" ? 0.85 : 1 });
    return;
  }
  graphics.rect(-spawn.radius, -arenaHeight / 2, spawn.radius * 2, arenaHeight).fill({ color, alpha: style === "neon" ? 0.85 : 1 });
}
