import { EntityResponse } from "../../types/entity.types";
import { FactCreate, FactResponse } from "../../types/fact.types";

export type FactObjectType = "entity" | "literal";

export interface FactFormProps {
  entities: EntityResponse[];
  fact?: FactResponse | null;
  onSubmit: (payload: FactCreate) => void;
  onCancel: () => void;
  isSubmitting: boolean;
  submitError: string | null;
}

export interface FactFormState {
  subjectEntityId: string;
  predicate: string;
  objectType: FactObjectType;
  objectEntityId: string;
  objectLiteral: string;
  hidden: boolean;
}
