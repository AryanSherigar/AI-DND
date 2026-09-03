import { AttributeFieldSchema } from "../../types/entity.types";

export interface AttributeRowProps {
  attrKey: string;
  schema: AttributeFieldSchema;
  onRename: (oldKey: string, newKey: string) => void;
  onFieldChange: (key: string, patch: Partial<AttributeFieldSchema>) => void;
  onRemove: (key: string) => void;
}
