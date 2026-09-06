import { describe, expect, it } from "vitest";
import { circlesCollide } from "../collision";

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
