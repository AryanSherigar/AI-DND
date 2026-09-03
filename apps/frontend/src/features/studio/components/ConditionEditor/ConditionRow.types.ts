import { ConditionResponse } from "../../types/condition.types";

export interface ConditionRowProps {
  condition: ConditionResponse;
  onEdit: (condition: ConditionResponse) => void;
  onDelete: (conditionId: string) => void;
}
