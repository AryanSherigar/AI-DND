import React, { useState } from "react";
import { Button } from "@/shared/components/ui/Button";
import { Input } from "@/shared/components/ui/Input";
import { Select } from "@/shared/components/ui/Select";
import {
  StateFieldDefinition,
  StateFieldType,
} from "../../types/scenario.types";
import { StateFieldMapEditor } from "./StateFieldMapEditor";
import { StateFieldRowProps } from "./StateFieldRow.types";

const STATE_FIELD_TYPE_OPTIONS: { value: StateFieldType; label: string }[] = [
  { value: "string", label: "String" },
  { value: "number", label: "Number" },
  { value: "boolean", label: "Boolean" },
  { value: "enum", label: "Enum" },
  { value: "entity_ref", label: "Entity Reference" },
  { value: "list", label: "List" },
  { value: "object", label: "Object" },
  { value: "derived", label: "Derived" },
];

const parseInitialValue = (type: StateFieldType, rawValue: string): unknown => {
  if (type === "number") return Number(rawValue);
  if (type === "boolean") return rawValue === "true";
  if (type === "list") {
    return rawValue === ""
      ? []
      : rawValue.split(",").map((item) => item.trim());
  }
  return rawValue;
};

const formatInitialValue = (initial: unknown): string => {
  if (Array.isArray(initial)) return initial.join(", ");
  if (initial === undefined || initial === null) return "";
  return String(initial);
};

const buildTypeChangePatch = (
  nextType: StateFieldType,
): Partial<StateFieldDefinition> => ({
  type: nextType,
  min: undefined,
  max: undefined,
  entity_type: undefined,
  item_type: undefined,
  initial: undefined,
  fields: nextType === "object" ? {} : undefined,
});

export const StateFieldRow: React.FC<StateFieldRowProps> = ({
  fieldKey,
  schema,
  onRename,
  onFieldChange,
  onRemove,
}) => {
  const [keyDraft, setKeyDraft] = useState(fieldKey);
  const isNumberType = schema.type === "number";
  const isListOfEntityRef =
    schema.type === "list" && schema.item_type === "entity_ref";
  const showEntityType = schema.type === "entity_ref" || isListOfEntityRef;
  const showInitial = schema.type !== "object" && schema.type !== "derived";

  const handleKeyBlur = (): void => onRename(fieldKey, keyDraft.trim());

  const handleTypeChange = (
    event: React.ChangeEvent<HTMLSelectElement>,
  ): void => {
    const nextType = event.target.value as StateFieldType;
    onFieldChange(fieldKey, buildTypeChangePatch(nextType));
  };

  const handleInitialChange = (
    event: React.ChangeEvent<HTMLInputElement>,
  ): void => {
    onFieldChange(fieldKey, {
      initial: parseInitialValue(schema.type, event.target.value),
    });
  };

  const handleMinChange = (
    event: React.ChangeEvent<HTMLInputElement>,
  ): void => {
    const nextMin =
      event.target.value === "" ? undefined : Number(event.target.value);
    onFieldChange(fieldKey, { min: nextMin });
  };

  const handleMaxChange = (
    event: React.ChangeEvent<HTMLInputElement>,
  ): void => {
    const nextMax =
      event.target.value === "" ? undefined : Number(event.target.value);
    onFieldChange(fieldKey, { max: nextMax });
  };

  const handleItemTypeChange = (
    event: React.ChangeEvent<HTMLSelectElement>,
  ): void => {
    onFieldChange(fieldKey, {
      item_type: event.target.value as StateFieldType,
    });
  };

  const handleNestedFieldsChange = (
    fields: Record<string, StateFieldDefinition>,
  ): void => {
    onFieldChange(fieldKey, { fields });
  };

  return (
    <div className="space-y-2 border border-zinc-800 p-2">
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-6">
        <Input
          aria-label="Field key"
          value={keyDraft}
          onChange={(e) => setKeyDraft(e.target.value)}
          onBlur={handleKeyBlur}
          placeholder="key"
        />
        <Select
          aria-label="Field type"
          options={STATE_FIELD_TYPE_OPTIONS}
          value={schema.type}
          onChange={handleTypeChange}
        />
        <Input
          aria-label="Field label"
          value={schema.label ?? ""}
          onChange={(e) => onFieldChange(fieldKey, { label: e.target.value })}
          placeholder="label"
        />
        {isNumberType && (
          <Input
            aria-label="Field min"
            type="number"
            value={schema.min ?? ""}
            onChange={handleMinChange}
            placeholder="min"
          />
        )}
        {isNumberType && (
          <Input
            aria-label="Field max"
            type="number"
            value={schema.max ?? ""}
            onChange={handleMaxChange}
            placeholder="max"
          />
        )}
        {showEntityType && (
          <Input
            aria-label="Field entity type"
            value={schema.entity_type ?? ""}
            onChange={(e) =>
              onFieldChange(fieldKey, { entity_type: e.target.value })
            }
            placeholder="entity type"
          />
        )}
        {schema.type === "list" && (
          <Select
            aria-label="Field item type"
            options={STATE_FIELD_TYPE_OPTIONS}
            value={schema.item_type ?? "string"}
            onChange={handleItemTypeChange}
          />
        )}
        {showInitial && (
          <Input
            aria-label="Field initial value"
            value={formatInitialValue(schema.initial)}
            onChange={handleInitialChange}
            placeholder="initial"
          />
        )}
        {schema.type === "derived" && (
          <p
            aria-label="Field formula"
            className="flex items-center px-3 py-2 text-sm text-zinc-500"
          >
            {schema.formula || "(no formula set)"}
          </p>
        )}
        <Button
          type="button"
          variant="danger"
          size="sm"
          onClick={() => onRemove(fieldKey)}
        >
          Remove
        </Button>
      </div>
      {schema.type === "object" && (
        <div className="pl-4">
          <StateFieldMapEditor
            value={schema.fields ?? {}}
            onChange={handleNestedFieldsChange}
            depthLabel={`${fieldKey} fields`}
          />
        </div>
      )}
    </div>
  );
};
