import { ScenarioMood } from "@/shared/types/audio.types";

/** Safety net for pre-migration playthrough snapshots that permanently
 * pinned a literal null; the backend otherwise always resolves a real URL
 * (built-in default or a creator's custom track) for every mood. */
export function getMoodTrackUrl(
  mood: ScenarioMood,
  tracks: Partial<Record<ScenarioMood, string | null>> | undefined,
): string | undefined {
  return tracks?.[mood] ?? undefined;
}
