import { SelectOption } from "@/shared/components/ui/Select";
import { AvailableField } from "../ConditionEditor/ExpressionBuilder/ExpressionBuilder.types";
import {
  InvariantCreate,
  InvariantResponse,
} from "../../types/invariant.types";

export interface InvariantFormProps {
  invariant: InvariantResponse | null;
  availableFields: AvailableField[];
  appliesToOptions: SelectOption[];
  onSubmit: (payload: InvariantCreate) => void;
  onCancel: () => void;
  isSubmitting: boolean;
  submitError: string | null;
}
