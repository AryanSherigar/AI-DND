import { describe, expect, it } from "vitest";
import {
  DODGE_DIFFICULTY_PRESETS,
  DODGE_MAX_DIFFICULTY,
  DODGE_MIN_DIFFICULTY,
  getDodgePreset,
} from "../difficultyPresets";

function presetsInOrder() {
  const tiers = Object.keys(DODGE_DIFFICULTY_PRESETS)
    .map(Number)
    .sort((a, b) => a - b);
  return tiers.map((tier) => DODGE_DIFFICULTY_PRESETS[tier]);
}

describe("DODGE_DIFFICULTY_PRESETS", () => {
  it("defines exactly tiers 1 through 5", () => {
    const tiers = Object.keys(DODGE_DIFFICULTY_PRESETS)
      .map(Number)
      .sort((a, b) => a - b);
    expect(tiers).toEqual([1, 2, 3, 4, 5]);
    expect(DODGE_MIN_DIFFICULTY).toBe(1);
    expect(DODGE_MAX_DIFFICULTY).toBe(5);
  });

  it("has non-decreasing durationMs from difficulty 1 to 5", () => {
    const presets = presetsInOrder();
    for (let i = 1; i < presets.length; i += 1) {
      expect(presets[i].durationMs).toBeGreaterThanOrEqual(
        presets[i - 1].durationMs,
      );
    }
  });

  it("has non-increasing hitPoints from difficulty 1 to 5", () => {
    const presets = presetsInOrder();
    for (let i = 1; i < presets.length; i += 1) {
      expect(presets[i].hitPoints).toBeLessThanOrEqual(
        presets[i - 1].hitPoints,
      );
    }
  });

  it("has non-decreasing hazardSpeedMultiplier from difficulty 1 to 5", () => {
    const presets = presetsInOrder();
    for (let i = 1; i < presets.length; i += 1) {
      expect(presets[i].hazardSpeedMultiplier).toBeGreaterThanOrEqual(
        presets[i - 1].hazardSpeedMultiplier,
      );
    }
  });

  it("has non-decreasing hazardDensityMultiplier from difficulty 1 to 5", () => {
    const presets = presetsInOrder();
    for (let i = 1; i < presets.length; i += 1) {
      expect(presets[i].hazardDensityMultiplier).toBeGreaterThanOrEqual(
        presets[i - 1].hazardDensityMultiplier,
      );
    }
  });

  it("is strictly harder end-to-end from difficulty 1 to difficulty 5", () => {
    const first = DODGE_DIFFICULTY_PRESETS[1];
    const last = DODGE_DIFFICULTY_PRESETS[5];
    expect(last.durationMs).toBeGreaterThan(first.durationMs);
    expect(last.hitPoints).toBeLessThan(first.hitPoints);
    expect(last.hazardSpeedMultiplier).toBeGreaterThan(
      first.hazardSpeedMultiplier,
    );
    expect(last.hazardDensityMultiplier).toBeGreaterThan(
      first.hazardDensityMultiplier,
    );
  });
});

describe("getDodgePreset", () => {
  it("returns the exact tier for an in-range integer difficulty", () => {
    expect(getDodgePreset(3)).toEqual(DODGE_DIFFICULTY_PRESETS[3]);
  });

  it("clamps below-range difficulty to tier 1", () => {
    expect(getDodgePreset(0)).toEqual(DODGE_DIFFICULTY_PRESETS[1]);
    expect(getDodgePreset(-5)).toEqual(DODGE_DIFFICULTY_PRESETS[1]);
  });

  it("clamps above-range difficulty to tier 5", () => {
    expect(getDodgePreset(9)).toEqual(DODGE_DIFFICULTY_PRESETS[5]);
  });

  it("rounds a fractional difficulty to the nearest tier", () => {
    expect(getDodgePreset(2.6)).toEqual(DODGE_DIFFICULTY_PRESETS[3]);
  });
});
