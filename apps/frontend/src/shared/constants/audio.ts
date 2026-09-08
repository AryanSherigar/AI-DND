import { ScenarioMood } from "@/shared/types/audio.types";

export const DEFAULT_MOOD_TRACK_URLS: Record<ScenarioMood, string> = {
  peaceful: "/audio/moods/peaceful.wav",
  mystery: "/audio/moods/mystery.wav",
  tension: "/audio/moods/tension.wav",
  combat: "/audio/moods/combat.wav",
  melancholy: "/audio/moods/melancholy.wav",
  triumph: "/audio/moods/triumph.wav",
};

export function resolveMoodTrackUrl(
  mood: ScenarioMood,
  overrides: Partial<Record<ScenarioMood, string | null>> | undefined,
): string {
  return overrides?.[mood] || DEFAULT_MOOD_TRACK_URLS[mood];
}
