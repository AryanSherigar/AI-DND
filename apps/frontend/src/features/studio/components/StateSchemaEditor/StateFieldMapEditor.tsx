import React from "react";
import { Button } from "@/shared/components/ui/Button";
import { StateFieldDefinition } from "../../types/scenario.types";
import {
  buildDefaultFieldDefinition,
  buildUnusedFieldKey,
  patchField,
  removeFieldKey,
  renameFieldKey,
} from "./stateFieldMap.utils";
import { StateFieldMapEditorProps } from "./StateFieldMapEditor.types";
import { StateFieldRow } from "./StateFieldRow";

export const StateFieldMapEditor: React.FC<StateFieldMapEditorProps> = ({
  value,
  onChange,
  depthLabel = "Fields",
}) => {
  const entries = Object.entries(value);

  const handleAdd = (): void => {
    const key = buildUnusedFieldKey(value);
    onChange({ ...value, [key]: buildDefaultFieldDefinition() });
  };

  const handleRename = (oldKey: string, newKey: string): void => {
    onChange(renameFieldKey(value, oldKey, newKey));
  };

  const handleFieldChange = (
    key: string,
    patch: Partial<StateFieldDefinition>,
  ): void => {
    onChange(patchField(value, key, patch));
  };

  const handleRemove = (key: string): void => {
    onChange(removeFieldKey(value, key));
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-zinc-300">{depthLabel}</span>
        <Button type="button" size="sm" variant="secondary" onClick={handleAdd}>
          Add Field
        </Button>
      </div>
      {entries.length === 0 && (
        <p className="text-xs text-zinc-600">No fields defined.</p>
      )}
      {entries.map(([key, schema]) => (
        <StateFieldRow
          key={key}
          fieldKey={key}
          schema={schema}
          onRename={handleRename}
          onFieldChange={handleFieldChange}
          onRemove={handleRemove}
        />
      ))}
    </div>
  );
};
