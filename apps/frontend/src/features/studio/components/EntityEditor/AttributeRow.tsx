import React, { useState } from "react";
import { Button } from "@/shared/components/ui/Button";
import { Input } from "@/shared/components/ui/Input";
import { Select } from "@/shared/components/ui/Select";
import { AttributeFieldType } from "../../types/entity.types";
import { AttributeRowProps } from "./AttributeRow.types";

const ATTRIBUTE_TYPE_OPTIONS = [
  { value: "string", label: "String" },
  { value: "number", label: "Number" },
  { value: "boolean", label: "Boolean" },
  { value: "enum", label: "Enum" },
];

const parseInitialValue = (
  type: AttributeFieldType,
  rawValue: string,
): unknown => {
  if (type === "number") return Number(rawValue);
  if (type === "boolean") return rawValue === "true";
  return rawValue;
};

export const AttributeRow: React.FC<AttributeRowProps> = ({
  attrKey,
  schema,
  onRename,
  onFieldChange,
  onRemove,
}) => {
  const [keyDraft, setKeyDraft] = useState(attrKey);
  const isNumberType = schema.type === "number";

  const handleKeyBlur = (): void => onRename(attrKey, keyDraft.trim());

  const handleTypeChange = (
    event: React.ChangeEvent<HTMLSelectElement>,
  ): void => {
    const nextType = event.target.value as AttributeFieldType;
    onFieldChange(attrKey, { type: nextType, min: undefined, max: undefined });
  };

  const handleInitialChange = (
    event: React.ChangeEvent<HTMLInputElement>,
  ): void => {
    onFieldChange(attrKey, {
      initial: parseInitialValue(schema.type, event.target.value),
    });
  };

  const handleMinChange = (
    event: React.ChangeEvent<HTMLInputElement>,
  ): void => {
    const nextMin =
      event.target.value === "" ? undefined : Number(event.target.value);
    onFieldChange(attrKey, { min: nextMin });
  };

  const handleMaxChange = (
    event: React.ChangeEvent<HTMLInputElement>,
  ): void => {
    const nextMax =
      event.target.value === "" ? undefined : Number(event.target.value);
    onFieldChange(attrKey, { max: nextMax });
  };

  return (
    <div className="grid grid-cols-2 gap-2 border border-zinc-800 p-2 sm:grid-cols-6">
      <Input
        aria-label="Attribute key"
        value={keyDraft}
        onChange={(e) => setKeyDraft(e.target.value)}
        onBlur={handleKeyBlur}
        placeholder="key"
      />
      <Select
        aria-label="Attribute type"
        options={ATTRIBUTE_TYPE_OPTIONS}
        value={schema.type}
        onChange={handleTypeChange}
      />
      <Input
        aria-label="Attribute label"
        value={schema.label ?? ""}
        onChange={(e) => onFieldChange(attrKey, { label: e.target.value })}
        placeholder="label"
      />
      {isNumberType && (
        <Input
          aria-label="Attribute min"
          type="number"
          value={schema.min ?? ""}
          onChange={handleMinChange}
          placeholder="min"
        />
      )}
      {isNumberType && (
        <Input
          aria-label="Attribute max"
          type="number"
          value={schema.max ?? ""}
          onChange={handleMaxChange}
          placeholder="max"
        />
      )}
      <Input
        aria-label="Attribute initial value"
        value={String(schema.initial ?? "")}
        onChange={handleInitialChange}
        placeholder="initial"
      />
      <Button
        type="button"
        variant="danger"
        size="sm"
        onClick={() => onRemove(attrKey)}
      >
        Remove
      </Button>
    </div>
  );
};
