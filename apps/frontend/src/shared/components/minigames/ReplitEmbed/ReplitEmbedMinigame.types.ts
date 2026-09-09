import { MinigameOutcomeResult } from "@/shared/types/minigame.types";

export interface ReplitEmbedMinigameProps {
  replitEmbedUrl: string;
  timeoutSeconds: number;
  onComplete: (result: MinigameOutcomeResult) => void;
}
