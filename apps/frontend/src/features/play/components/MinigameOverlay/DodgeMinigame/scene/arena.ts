// Static PixiJS scene graph for the Ashfall Dodge arena: dark background,
// radial vignette, and a glowing rounded-rect boundary that tints from
// cool blue-white toward amber/red as health drops. Plain PixiJS module,
// no React — see docs/specs/dodge-minigame-design.spec.md §3.4/§3.6.

import { BlurFilter, Container, FillGradient, Graphics } from "pixi.js";
import { ARENA_HEIGHT, ARENA_WIDTH } from "../difficultyPresets";

const ARENA_BACKGROUND_COLOR = 0x0a0a14;
const VIGNETTE_EDGE_COLOR = "rgba(0,0,0,0.85)";
const VIGNETTE_CENTER_COLOR = "rgba(0,0,0,0)";

const BOUNDARY_FULL_HEALTH_COLOR = 0x7ec8ff;
const BOUNDARY_LOW_HEALTH_COLOR = 0xff6b4a;
const BOUNDARY_CORNER_RADIUS = 20;
const BOUNDARY_LINE_WIDTH = 3;
const BOUNDARY_GLOW_LINE_WIDTH = 10;
const BOUNDARY_GLOW_ALPHA = 0.55;
const BOUNDARY_GLOW_BLUR_STRENGTH = 6;

export interface ArenaScene {
  container: Container;
  updateBoundaryTint: (hitPointsFraction: number) => void;
}

function buildBackground(): Graphics {
  return new Graphics()
    .rect(0, 0, ARENA_WIDTH, ARENA_HEIGHT)
    .fill(ARENA_BACKGROUND_COLOR);
}

function buildVignette(): Graphics {
  const gradient = new FillGradient({
    type: "radial",
    center: { x: 0.5, y: 0.5 },
    innerRadius: 0.2,
    outerCenter: { x: 0.5, y: 0.5 },
    outerRadius: 0.75,
    colorStops: [
      { offset: 0, color: VIGNETTE_CENTER_COLOR },
      { offset: 1, color: VIGNETTE_EDGE_COLOR },
    ],
    textureSpace: "local",
  });
  return new Graphics().rect(0, 0, ARENA_WIDTH, ARENA_HEIGHT).fill(gradient);
}

function lerpChannel(from: number, to: number, t: number): number {
  return Math.round(from + (to - from) * t);
}

function interpolateBoundaryColor(t: number): number {
  const fromR = (BOUNDARY_FULL_HEALTH_COLOR >> 16) & 0xff;
  const fromG = (BOUNDARY_FULL_HEALTH_COLOR >> 8) & 0xff;
  const fromB = BOUNDARY_FULL_HEALTH_COLOR & 0xff;
  const toR = (BOUNDARY_LOW_HEALTH_COLOR >> 16) & 0xff;
  const toG = (BOUNDARY_LOW_HEALTH_COLOR >> 8) & 0xff;
  const toB = BOUNDARY_LOW_HEALTH_COLOR & 0xff;
  const r = lerpChannel(fromR, toR, t);
  const g = lerpChannel(fromG, toG, t);
  const b = lerpChannel(fromB, toB, t);
  return (r << 16) | (g << 8) | b;
}

export function buildArena(): ArenaScene {
  const container = new Container();
  container.addChild(buildBackground());
  container.addChild(buildVignette());

  const boundaryGlow = new Graphics();
  boundaryGlow.filters = [
    new BlurFilter({ strength: BOUNDARY_GLOW_BLUR_STRENGTH }),
  ];
  container.addChild(boundaryGlow);

  const boundary = new Graphics();
  container.addChild(boundary);

  const inset = BOUNDARY_LINE_WIDTH / 2;
  const drawBoundary = (color: number): void => {
    boundary
      .clear()
      .roundRect(
        inset,
        inset,
        ARENA_WIDTH - BOUNDARY_LINE_WIDTH,
        ARENA_HEIGHT - BOUNDARY_LINE_WIDTH,
        BOUNDARY_CORNER_RADIUS,
      )
      .stroke({ width: BOUNDARY_LINE_WIDTH, color });

    boundaryGlow
      .clear()
      .roundRect(
        inset,
        inset,
        ARENA_WIDTH - BOUNDARY_LINE_WIDTH,
        ARENA_HEIGHT - BOUNDARY_LINE_WIDTH,
        BOUNDARY_CORNER_RADIUS,
      )
      .stroke({
        width: BOUNDARY_GLOW_LINE_WIDTH,
        color,
        alpha: BOUNDARY_GLOW_ALPHA,
      });
  };

  drawBoundary(BOUNDARY_FULL_HEALTH_COLOR);

  // hitPointsFraction: 1 = full health (cool blue-white), 0 = critical
  // (amber/red) — continuous interpolation, never a hard threshold snap.
  const updateBoundaryTint = (hitPointsFraction: number): void => {
    const clamped = Math.min(1, Math.max(0, hitPointsFraction));
    drawBoundary(interpolateBoundaryColor(1 - clamped));
  };

  return { container, updateBoundaryTint };
}
