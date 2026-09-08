import { describe, it, expect, beforeEach, vi } from "vitest";
import { AmbientSoundtrackController } from "../ambient-soundtrack";

describe("AmbientSoundtrackController", () => {
  let controller: AmbientSoundtrackController;

  beforeEach(() => {
    localStorage.clear();
    controller = new AmbientSoundtrackController();
  });

  it("initializes with default volume and unmuted state", () => {
    expect(controller.getVolume()).toBe(0.6);
    expect(controller.getIsMuted()).toBe(false);
    expect(controller.getMood()).toBeNull();
  });

  it("clamps volume values within [0.0, 1.0]", () => {
    controller.setVolume(1.5);
    expect(controller.getVolume()).toBe(1.0);

    controller.setVolume(-0.5);
    expect(controller.getVolume()).toBe(0.0);

    controller.setVolume(0.75);
    expect(controller.getVolume()).toBe(0.75);
  });

  it("toggles mute state", () => {
    expect(controller.getIsMuted()).toBe(false);
    const muted = controller.toggleMute();
    expect(muted).toBe(true);
    expect(controller.getIsMuted()).toBe(true);

    const unmuted = controller.toggleMute();
    expect(unmuted).toBe(false);
    expect(controller.getIsMuted()).toBe(false);
  });

  it("notifies isolated audio consumers when global preferences change", () => {
    const listener = vi.fn();
    const unsubscribe = controller.onAudioPreferenceChange(listener);

    controller.setVolume(0.4);
    controller.toggleMute();
    unsubscribe();
    controller.setVolume(0.8);

    expect(listener).toHaveBeenCalledTimes(2);
    expect(listener).toHaveBeenNthCalledWith(1, {
      volume: 0.4,
      isMuted: false,
    });
    expect(listener).toHaveBeenNthCalledWith(2, { volume: 0.4, isMuted: true });
  });

  it("transitions to new mood and ignores duplicate transitions", () => {
    const firstTransition = controller.transitionTo(
      "peaceful",
      undefined,
      true,
    );
    expect(firstTransition).toBe(true);
    expect(controller.getMood()).toBe("peaceful");

    const duplicateTransition = controller.transitionTo("peaceful");
    expect(duplicateTransition).toBe(false);
  });

  it("enforces cooldown for non-combat transitions but allows combat escalation", () => {
    controller.transitionTo("peaceful", undefined, true);

    // Non-combat transition immediately after should be throttled by cooldown
    const nonCombatAttempt = controller.transitionTo("mystery");
    expect(nonCombatAttempt).toBe(false);
    expect(controller.getMood()).toBe("peaceful");

    // Combat transition bypasses cooldown
    const combatAttempt = controller.transitionTo("combat");
    expect(combatAttempt).toBe(true);
    expect(controller.getMood()).toBe("combat");
  });

  it("uses a custom track URL when one is provided", () => {
    controller.transitionTo("peaceful", "https://example.com/custom.wav", true);
    expect(controller.getCurrentTrackUrl()).toBe(
      "https://example.com/custom.wav",
    );
  });

  it("falls back to the default mood track URL when none is provided", () => {
    controller.transitionTo("peaceful", undefined, true);
    expect(controller.getCurrentTrackUrl()).toBe("/audio/moods/peaceful.wav");
  });

  it("persists settings in localStorage", () => {
    controller.setVolume(0.85);
    controller.toggleMute();

    expect(localStorage.getItem("ai_dnd_audio_volume")).toBe("0.85");
    expect(localStorage.getItem("ai_dnd_audio_muted")).toBe("true");

    const freshController = new AmbientSoundtrackController();
    expect(freshController.getVolume()).toBe(0.85);
    expect(freshController.getIsMuted()).toBe(true);
  });
});
