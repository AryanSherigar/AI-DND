import { ScenarioMood } from "@/shared/types/audio.types";
import { ScenarioMusicSlot } from "../../types/music.types";

export interface MoodSlotCardProps {
  scenarioId: string;
  mood: ScenarioMood;
  label: string;
  slot: ScenarioMusicSlot | undefined;
  quotaExceeded: boolean;
}
