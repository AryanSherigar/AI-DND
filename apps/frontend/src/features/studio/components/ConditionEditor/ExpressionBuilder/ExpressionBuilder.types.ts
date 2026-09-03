export type ExpressionOperator =
  "==" | "!=" | "<" | "<=" | ">" | ">=" | "in" | "contains" | "matches";

export interface FieldExpression {
  field: string;
  op: ExpressionOperator;
  value: string | number | boolean;
  AND?: FieldExpression;
  OR?: FieldExpression;
  NOT?: FieldExpression;
}

export interface AvailableField {
  path: string;
  label: string;
  type: "string" | "number" | "boolean" | "enum" | "entity_ref";
}

export interface ExpressionBuilderProps {
  value: FieldExpression | null;
  onChange: (expr: FieldExpression | null) => void;
  availableFields: AvailableField[];
}
