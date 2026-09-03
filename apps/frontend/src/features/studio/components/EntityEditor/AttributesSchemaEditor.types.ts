import { AttributeFieldSchema } from "../../types/entity.types";

export interface AttributesSchemaEditorProps {
  value: Record<string, AttributeFieldSchema>;
  onChange: (value: Record<string, AttributeFieldSchema>) => void;
}
