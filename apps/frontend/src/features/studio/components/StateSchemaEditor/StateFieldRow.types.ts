import { StateFieldDefinition } from "../../types/scenario.types";

export interface StateFieldRowProps {
  fieldKey: string;
  schema: StateFieldDefinition;
  onRename: (oldKey: string, newKey: string) => void;
  onFieldChange: (key: string, patch: Partial<StateFieldDefinition>) => void;
  onRemove: (key: string) => void;
}
