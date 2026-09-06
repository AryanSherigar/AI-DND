import { AvailableField } from "../ConditionEditor/ExpressionBuilder/ExpressionBuilder.types";
import { MinigameCreate, MinigameResponse } from "../../types/minigame.types";

export interface MinigameFormProps {
  availableFields: AvailableField[];
  minigame?: MinigameResponse | null;
  onSubmit: (payload: MinigameCreate) => void;
  onCancel: () => void;
  isSubmitting: boolean;
  submitError: string | null;
}
