import React from "react";
import { Input } from "../../../../../shared/components/ui/Input";
import { AvailableField } from "./ExpressionBuilder.types";

export interface FieldPickerProps {
  value: string;
  onChange: (path: string) => void;
  availableFields: AvailableField[];
}

const DATALIST_ID = "expression-builder-field-options";

export const FieldPicker: React.FC<FieldPickerProps> = ({
  value,
  onChange,
  availableFields,
}) => {
  const isKnownField = availableFields.some((field) => field.path === value);
  const hasUnknownField = value.length > 0 && !isKnownField;

  const handleChange = (event: React.ChangeEvent<HTMLInputElement>): void => {
    onChange(event.target.value);
  };

  return (
    <div className="w-full">
      <Input
        list={DATALIST_ID}
        value={value}
        onChange={handleChange}
        placeholder="player.health"
        error={hasUnknownField ? "This field does not exist." : undefined}
      />
      <datalist id={DATALIST_ID}>
        {availableFields.map((field) => (
          <option key={field.path} value={field.path}>
            {field.label}
          </option>
        ))}
      </datalist>
    </div>
  );
};
