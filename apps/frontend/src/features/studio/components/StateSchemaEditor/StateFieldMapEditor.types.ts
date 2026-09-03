import { StateFieldDefinition } from "../../types/scenario.types";

export interface StateFieldMapEditorProps {
  value: Record<string, StateFieldDefinition>;
  onChange: (value: Record<string, StateFieldDefinition>) => void;
  depthLabel?: string;
}
