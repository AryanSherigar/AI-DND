import { describe, expect, it } from "vitest";
import {
  clampToArena,
  computeVelocity,
  createPlayerControllerState,
  type PlayerControllerState,
} from "../playerController";

const MAX_SPEED = 260;
const ARENA_WIDTH = 640;
const ARENA_HEIGHT = 480;
const PLAYER_RADIUS = 12;

function stateWith(
  overrides: Partial<PlayerControllerState>,
): PlayerControllerState {
  return { ...createPlayerControllerState(), ...overrides };
}

describe("computeVelocity — keyboard input", () => {
  it("holding right produces a velocity vector pointing purely right at max speed", () => {
    const state = stateWith({ keysDown: new Set(["ArrowRight"]) });
    const { vx, vy } = computeVelocity(state, 100, 100, MAX_SPEED);
    expect(vx).toBeCloseTo(MAX_SPEED);
    expect(vy).toBeCloseTo(0);
  });

  it("holding left produces a velocity vector pointing purely left at max speed", () => {
    const state = stateWith({ keysDown: new Set(["a"]) });
    const { vx, vy } = computeVelocity(state, 100, 100, MAX_SPEED);
    expect(vx).toBeCloseTo(-MAX_SPEED);
    expect(vy).toBeCloseTo(0);
  });

  it("holding two opposing keys cancels out to zero velocity", () => {
    const state = stateWith({ keysDown: new Set(["ArrowLeft", "ArrowRight"]) });
    const { vx, vy } = computeVelocity(state, 100, 100, MAX_SPEED);
    expect(vx).toBeCloseTo(0);
    expect(vy).toBeCloseTo(0);
  });

  it("diagonal input (up + right) is normalized to max speed, not max speed on each axis", () => {
    const state = stateWith({ keysDown: new Set(["ArrowUp", "ArrowRight"]) });
    const { vx, vy } = computeVelocity(state, 100, 100, MAX_SPEED);
    const magnitude = Math.hypot(vx, vy);
    expect(magnitude).toBeCloseTo(MAX_SPEED);
  });

  it("no input produces zero velocity", () => {
    const state = stateWith({});
    const { vx, vy } = computeVelocity(state, 100, 100, MAX_SPEED);
    expect(vx).toBe(0);
    expect(vy).toBe(0);
  });
});

describe("computeVelocity — mouse input", () => {
  it("seeks the cursor target, capped at max speed", () => {
    const state = stateWith({ mouseTarget: { x: 400, y: 100 } });
    const { vx, vy } = computeVelocity(state, 100, 100, MAX_SPEED);
    expect(vy).toBeCloseTo(0);
    expect(vx).toBeCloseTo(MAX_SPEED);
  });

  it("seeks diagonally toward the target, magnitude capped at max speed", () => {
    const state = stateWith({ mouseTarget: { x: 500, y: 500 } });
    const { vx, vy } = computeVelocity(state, 100, 100, MAX_SPEED);
    const magnitude = Math.hypot(vx, vy);
    expect(magnitude).toBeCloseTo(MAX_SPEED);
    expect(vx).toBeGreaterThan(0);
    expect(vy).toBeGreaterThan(0);
  });

  it("produces zero velocity when already at the mouse target", () => {
    const state = stateWith({ mouseTarget: { x: 100, y: 100 } });
    const { vx, vy } = computeVelocity(state, 100, 100, MAX_SPEED);
    expect(vx).toBe(0);
    expect(vy).toBe(0);
  });
});

describe("computeVelocity — blended input", () => {
  it("keyboard alone remains fully sufficient when the mouse target is within the seek deadzone", () => {
    const state = stateWith({
      keysDown: new Set(["ArrowRight"]),
      mouseTarget: { x: 100, y: 100 },
    });
    const { vx, vy } = computeVelocity(state, 100, 100, MAX_SPEED);
    expect(vx).toBeCloseTo(MAX_SPEED);
    expect(vy).toBeCloseTo(0);
  });

  it("blending both inputs in the same direction does not exceed max speed", () => {
    const state = stateWith({
      keysDown: new Set(["ArrowRight"]),
      mouseTarget: { x: 400, y: 100 },
    });
    const { vx, vy } = computeVelocity(state, 100, 100, MAX_SPEED);
    const magnitude = Math.hypot(vx, vy);
    expect(magnitude).toBeCloseTo(MAX_SPEED);
    expect(vx).toBeGreaterThan(0);
  });
});

describe("clampToArena", () => {
  it("leaves an in-bounds position unchanged", () => {
    const { x, y } = clampToArena(
      300,
      200,
      PLAYER_RADIUS,
      ARENA_WIDTH,
      ARENA_HEIGHT,
    );
    expect(x).toBe(300);
    expect(y).toBe(200);
  });

  it("clamps a position past the left/top edges back into bounds", () => {
    const { x, y } = clampToArena(
      -50,
      -50,
      PLAYER_RADIUS,
      ARENA_WIDTH,
      ARENA_HEIGHT,
    );
    expect(x).toBe(PLAYER_RADIUS);
    expect(y).toBe(PLAYER_RADIUS);
  });

  it("clamps a position past the right/bottom edges back into bounds", () => {
    const { x, y } = clampToArena(
      ARENA_WIDTH + 100,
      ARENA_HEIGHT + 100,
      PLAYER_RADIUS,
      ARENA_WIDTH,
      ARENA_HEIGHT,
    );
    expect(x).toBe(ARENA_WIDTH - PLAYER_RADIUS);
    expect(y).toBe(ARENA_HEIGHT - PLAYER_RADIUS);
  });
});
