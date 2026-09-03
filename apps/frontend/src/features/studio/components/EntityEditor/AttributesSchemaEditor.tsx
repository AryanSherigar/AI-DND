import React from "react";
import { Button } from "@/shared/components/ui/Button";
import { AttributeFieldSchema } from "../../types/entity.types";
import { AttributeRow } from "./AttributeRow";
import { AttributesSchemaEditorProps } from "./AttributesSchemaEditor.types";

const buildUnusedKey = (
  value: Record<string, AttributeFieldSchema>,
): string => {
  let index = Object.keys(value).length + 1;
  let candidate = `attribute_${index}`;
  while (value[candidate]) {
    index += 1;
    candidate = `attribute_${index}`;
  }
  return candidate;
};

export const AttributesSchemaEditor: React.FC<AttributesSchemaEditorProps> = ({
  value,
  onChange,
}) => {
  const entries = Object.entries(value);

  const handleAdd = (): void => {
    const key = buildUnusedKey(value);
    onChange({ ...value, [key]: { type: "string", initial: "" } });
  };

  const handleRemove = (key: string): void => {
    const next = { ...value };
    delete next[key];
    onChange(next);
  };

  const handleRename = (oldKey: string, newKey: string): void => {
    if (!newKey || newKey === oldKey || value[newKey]) return;
    const next: Record<string, AttributeFieldSchema> = {};
    entries.forEach(([entryKey, schema]) => {
      next[entryKey === oldKey ? newKey : entryKey] = schema;
    });
    onChange(next);
  };

  const handleFieldChange = (
    key: string,
    patch: Partial<AttributeFieldSchema>,
  ): void => {
    onChange({ ...value, [key]: { ...value[key], ...patch } });
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-zinc-300">Attributes</span>
        <Button type="button" size="sm" variant="secondary" onClick={handleAdd}>
          Add Attribute
        </Button>
      </div>
      {entries.length === 0 && (
        <p className="text-xs text-zinc-600">No attributes defined.</p>
      )}
      {entries.map(([key, schema]) => (
        <AttributeRow
          key={key}
          attrKey={key}
          schema={schema}
          onRename={handleRename}
          onFieldChange={handleFieldChange}
          onRemove={handleRemove}
        />
      ))}
    </div>
  );
};
