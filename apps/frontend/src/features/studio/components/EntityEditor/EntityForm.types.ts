import {
  AttributeFieldSchema,
  EntityCreate,
  EntityResponse,
} from "../../types/entity.types";

export interface EntityFormProps {
  scenarioId: string;
  entity: EntityResponse | null;
  onSubmit: (payload: EntityCreate) => void;
  onCancel: () => void;
  isSubmitting: boolean;
  submitError: string | null;
}

export interface EntityFormState {
  entityType: string;
  canonicalName: string;
  aliasesText: string;
  description: string;
  obtainable: boolean;
  narratorInstruction: string;
  attributesSchema: Record<string, AttributeFieldSchema>;
}
