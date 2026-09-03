import React from "react";
import { Select } from "../../../../../shared/components/ui/Select";
import { ExpressionOperator } from "./ExpressionBuilder.types";

export interface OperatorPickerProps {
  value: ExpressionOperator;
  onChange: (op: ExpressionOperator) => void;
}

const OPERATOR_LABELS: Record<ExpressionOperator, string> = {
  "==": "equals",
  "!=": "not equals",
  "<": "less than",
  "<=": "at most",
  ">": "greater than",
  ">=": "at least",
  in: "in",
  contains: "contains",
  matches: "matches",
};

const OPERATOR_OPTIONS = (
  Object.keys(OPERATOR_LABELS) as ExpressionOperator[]
).map((operator) => ({ value: operator, label: OPERATOR_LABELS[operator] }));

export const OperatorPicker: React.FC<OperatorPickerProps> = ({
  value,
  onChange,
}) => {
  const handleChange = (event: React.ChangeEvent<HTMLSelectElement>): void => {
    onChange(event.target.value as ExpressionOperator);
  };

  return (
    <Select options={OPERATOR_OPTIONS} value={value} onChange={handleChange} />
  );
};
