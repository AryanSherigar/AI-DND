import { MinigameResponse } from "../../types/minigame.types";

export interface MinigameRowProps {
  minigame: MinigameResponse;
  onEdit: (minigame: MinigameResponse) => void;
  onDelete: (minigameId: string) => void;
}
