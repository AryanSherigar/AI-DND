import { DodgeConfigShape, MinigameType } from "../../types/minigame.types";

export interface MinigamePreviewOverlayProps {
  minigameType: MinigameType;
  dodgeConfig: DodgeConfigShape;
  replitEmbedUrl: string;
  onClose: () => void;
}
