export type ScenarioMood =
  "peaceful" | "mystery" | "tension" | "combat" | "melancholy";

export interface AudioSettings {
  is_muted: boolean;
  volume: number;
}

export interface MoodTrackConfig {
  mood: ScenarioMood;
  src: string;
  label: string;
}
