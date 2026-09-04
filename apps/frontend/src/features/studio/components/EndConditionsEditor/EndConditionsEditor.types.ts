import {
  AvailableField,
  FieldExpression,
} from "../ConditionEditor/ExpressionBuilder/ExpressionBuilder.types";
import {
  EndConditionCreate,
  EndConditionResponse,
  OutcomeTag,
} from "../../types/end_condition.types";

export interface EndConditionsEditorProps {
  scenarioId: string;
}

export interface EndConditionRowProps {
  endCondition: EndConditionResponse;
  onEdit: (endCondition: EndConditionResponse) => void;
  onDelete: (endConditionId: string) => void;
}

export interface EndConditionFormState {
  outcomeTag: OutcomeTag;
  outcomeTitle: string;
  outcomeText: string;
  isSecret: boolean;
  conditionExpression: FieldExpression | null;
}

export interface EndConditionFormProps {
  availableFields: AvailableField[];
  endCondition?: EndConditionResponse | null;
  onSubmit: (payload: EndConditionCreate) => void;
  onCancel: () => void;
  isSubmitting: boolean;
  submitError: string | null;
}
