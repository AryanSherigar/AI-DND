import {
  AttributeFieldSchema,
  EntityCreate,
  EntityResponse,
  EntityType,
} from "../../types/entity.types";

export interface EntityFormProps {
  entity: EntityResponse | null;
  onSubmit: (payload: EntityCreate) => void;
  onCancel: () => void;
  isSubmitting: boolean;
  submitError: string | null;
}

export interface EntityFormState {
  entityType: EntityType;
  canonicalName: string;
  aliasesText: string;
  description: string;
  obtainable: boolean;
  narratorInstruction: string;
  attributesSchema: Record<string, AttributeFieldSchema>;
}
