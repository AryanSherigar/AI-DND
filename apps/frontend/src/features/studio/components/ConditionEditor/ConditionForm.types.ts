import { AvailableField } from "./ExpressionBuilder/ExpressionBuilder.types";
import { ConditionCreate, ConditionResponse } from "../../types/condition.types";

export interface ConditionFormProps {
  condition: ConditionResponse | null;
  availableFields: AvailableField[];
  onSubmit: (payload: ConditionCreate) => void;
  onCancel: () => void;
  isSubmitting: boolean;
  submitError: string | null;
}
