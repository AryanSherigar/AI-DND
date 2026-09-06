import { MinigameOutcomeResult } from "../MinigameOverlay.types";

export interface ReplitEmbedMinigameProps {
  replitEmbedUrl: string;
  timeoutSeconds: number;
  onComplete: (result: MinigameOutcomeResult) => void;
}
