import { describe, expect, it } from "vitest";
import { circleIntersectsBeam, circlesCollide, hazardCollidesWithPlayer } from "../collision";

describe("circlesCollide", () => {
  it("reports a collision when center distance is less than the sum of radii", () => {
    // distance = 9, radiusSum = 10
    expect(circlesCollide(0, 0, 4, 9, 0, 6)).toBe(true);
  });

  it("does not report a collision when center distance equals the sum of radii", () => {
    // distance = 10, radiusSum = 10 — boundary is exclusive
    expect(circlesCollide(0, 0, 4, 10, 0, 6)).toBe(false);
  });

  it("does not report a collision when circles are far apart", () => {
    expect(circlesCollide(0, 0, 4, 100, 100, 6)).toBe(false);
  });

  it("reports a collision when circles fully overlap at the same center", () => {
    expect(circlesCollide(5, 5, 3, 5, 5, 3)).toBe(true);
  });
});

describe("circleIntersectsBeam", () => {
  it("uses the beam's full horizontal span, not only its centre point", () => {
    expect(circleIntersectsBeam(30, 205, 12, 320, 200, 7, true)).toBe(true);
  });

  it("does not hit a player beyond the beam thickness and player radius", () => {
    expect(circleIntersectsBeam(320, 220, 12, 320, 200, 7, true)).toBe(false);
  });

  it("checks horizontal distance for vertical beams", () => {
    expect(circleIntersectsBeam(205, 30, 12, 200, 240, 7, false)).toBe(true);
  });
});

describe("hazardCollidesWithPlayer", () => {
  it("never damages the player while a beam is telegraphing", () => {
    expect(hazardCollidesWithPlayer(
      30, 205, 12,
      { isTelegraphing: true, shape: "beam", x: 320, y: 200, radius: 7 },
      640,
    )).toBe(false);
  });

  it("uses beam collision only after its telegraph completes", () => {
    expect(hazardCollidesWithPlayer(
      30, 205, 12,
      { isTelegraphing: false, shape: "beam", x: 320, y: 200, radius: 7 },
      640,
    )).toBe(true);
  });
});
