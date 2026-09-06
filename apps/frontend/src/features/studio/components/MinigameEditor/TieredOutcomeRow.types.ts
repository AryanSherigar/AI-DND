import { TieredOutcomeRange } from "../../types/minigame.types";

export interface TieredOutcomeRowProps {
  value: TieredOutcomeRange;
  onChange: (range: TieredOutcomeRange) => void;
  onRemove: () => void;
}
