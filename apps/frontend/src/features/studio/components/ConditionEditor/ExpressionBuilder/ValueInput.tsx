import React from "react";
import { Input } from "../../../../../shared/components/ui/Input";
import { Select } from "../../../../../shared/components/ui/Select";
import { AvailableField } from "./ExpressionBuilder.types";

export interface ValueInputProps {
  value: string | number | boolean;
  onChange: (value: string | number | boolean) => void;
  fieldType?: AvailableField["type"];
}

const BOOLEAN_OPTIONS = [
  { value: "true", label: "true" },
  { value: "false", label: "false" },
];

export const ValueInput: React.FC<ValueInputProps> = ({
  value,
  onChange,
  fieldType,
}) => {
  if (fieldType === "boolean") {
    const handleBooleanChange = (
      event: React.ChangeEvent<HTMLSelectElement>,
    ): void => {
      onChange(event.target.value === "true");
    };

    return (
      <Select
        options={BOOLEAN_OPTIONS}
        value={String(value)}
        onChange={handleBooleanChange}
      />
    );
  }

  if (fieldType === "number") {
    const handleNumberChange = (
      event: React.ChangeEvent<HTMLInputElement>,
    ): void => {
      onChange(event.target.value === "" ? "" : Number(event.target.value));
    };

    return (
      <Input
        type="number"
        value={String(value)}
        onChange={handleNumberChange}
      />
    );
  }

  const handleTextChange = (
    event: React.ChangeEvent<HTMLInputElement>,
  ): void => {
    onChange(event.target.value);
  };

  return (
    <Input type="text" value={String(value)} onChange={handleTextChange} />
  );
};
