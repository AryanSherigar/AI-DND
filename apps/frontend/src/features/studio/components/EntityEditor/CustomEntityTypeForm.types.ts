import { AttributeFieldSchema } from "../../types/entity.types";

export interface CustomEntityTypeFormProps {
  typeKey: string;
  displayLabel: string;
  attributesSchema: Record<string, AttributeFieldSchema>;
  onTypeKeyChange: (value: string) => void;
  onDisplayLabelChange: (value: string) => void;
  onAttributesSchemaChange: (
    value: Record<string, AttributeFieldSchema>,
  ) => void;
}
