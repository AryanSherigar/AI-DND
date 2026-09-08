// Static PixiJS scene graph for the Ashfall Dodge arena: dark background,
// radial vignette, and a glowing rounded-rect boundary that tints from
// cool blue-white toward amber/red as health drops. Plain PixiJS module,
// no React — see docs/specs/dodge-minigame-design.spec.md §3.4/§3.6.

import { BlurFilter, Container, FillGradient, Graphics, Sprite, Texture } from "pixi.js";
import { ARENA_HEIGHT, ARENA_WIDTH } from "../difficultyPresets";
import type { DodgeBackground, DodgePalette, DodgeTexture } from "@/shared/types/minigame.types";

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

export interface ArenaAppearance {
  background?: DodgeBackground;
  texture?: DodgeTexture;
  palette?: DodgePalette;
  backgroundAssetUrl?: string | null;
}

const BACKGROUND_COLORS: Record<DodgeBackground, number> = {
  void: 0x0a0a14, ember: 0x26120d, midnight: 0x08152c,
};
const PALETTE_BOUNDARY_COLORS: Record<DodgePalette, number> = {
  ashfall: BOUNDARY_FULL_HEALTH_COLOR, ember: 0xffa05c, aurora: 0x87f7d1,
};

function buildBackground(color: number): Graphics {
  return new Graphics()
    .rect(0, 0, ARENA_WIDTH, ARENA_HEIGHT)
    .fill(color);
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

function buildTexture(texture: DodgeTexture | undefined): Graphics | null {
  if (!texture || texture === "none") return null;
  const graphics = new Graphics();
  // Deterministic decoration only; it never participates in collision.
  for (let x = 12; x < ARENA_WIDTH; x += texture === "stars" ? 43 : 17) {
    for (let y = 9; y < ARENA_HEIGHT; y += texture === "stars" ? 37 : 19) {
      const size = texture === "stars" ? 1.5 : 0.7;
      graphics.circle(x + ((y / 19) % 3), y, size).fill({ color: 0xffffff, alpha: texture === "stars" ? 0.22 : 0.06 });
    }
  }
  return graphics;
}

export function buildArena(appearance: ArenaAppearance = {}): ArenaScene {
  const container = new Container();
  const backgroundColor = BACKGROUND_COLORS[appearance.background ?? "void"] ?? ARENA_BACKGROUND_COLOR;
  container.addChild(buildBackground(backgroundColor));
  if (appearance.backgroundAssetUrl) {
    const sprite = new Sprite(Texture.from(appearance.backgroundAssetUrl));
    sprite.width = ARENA_WIDTH;
    sprite.height = ARENA_HEIGHT;
    sprite.alpha = 0.5;
    container.addChild(sprite);
  }
  const texture = buildTexture(appearance.texture);
  if (texture) container.addChild(texture);
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

  const fullHealthColor = PALETTE_BOUNDARY_COLORS[appearance.palette ?? "ashfall"];
  drawBoundary(fullHealthColor);

  // hitPointsFraction: 1 = full health (cool blue-white), 0 = critical
  // (amber/red) — continuous interpolation, never a hard threshold snap.
  const updateBoundaryTint = (hitPointsFraction: number): void => {
    const clamped = Math.min(1, Math.max(0, hitPointsFraction));
    if (appearance.palette === "ashfall" || !appearance.palette) {
      drawBoundary(interpolateBoundaryColor(1 - clamped));
      return;
    }
    // Other palettes retain their authored hue and fade toward the same
    // critical warning color, keeping health feedback readable.
    const r = (fullHealthColor >> 16) & 0xff;
    const g = (fullHealthColor >> 8) & 0xff;
    const b = fullHealthColor & 0xff;
    const warningT = 1 - clamped;
    drawBoundary(
      (lerpChannel(r, 0xff, warningT) << 16) |
      (lerpChannel(g, 0x6b, warningT) << 8) |
      lerpChannel(b, 0x4a, warningT),
    );
  };

  return { container, updateBoundaryTint };
}
