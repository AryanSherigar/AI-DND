import React from "react";
import { Input } from "@/shared/components/ui/Input";
import { AttributesSchemaEditor } from "./AttributesSchemaEditor";
import { CustomEntityTypeFormProps } from "./CustomEntityTypeForm.types";

const slugify = (value: string): string =>
  value
    .toLowerCase()
    .replace(/[^a-z0-9_]+/g, "_")
    .replace(/^_+/, "")
    .slice(0, 30);

export const CustomEntityTypeForm: React.FC<CustomEntityTypeFormProps> = ({
  typeKey,
  displayLabel,
  attributesSchema,
  onTypeKeyChange,
  onDisplayLabelChange,
  onAttributesSchemaChange,
}) => {
  const handleDisplayLabelChange = (
    event: React.ChangeEvent<HTMLInputElement>,
  ): void => {
    onDisplayLabelChange(event.target.value);
    onTypeKeyChange(slugify(event.target.value));
  };

  return (
    <div className="space-y-3 border border-zinc-800 bg-zinc-950 p-3">
      <p className="text-xs font-medium text-zinc-400">New custom type</p>
      <Input
        aria-label="Custom type name"
        value={displayLabel}
        onChange={handleDisplayLabelChange}
        placeholder="Type name (e.g. Vehicle)"
        required
      />
      {typeKey && <p className="text-xs text-zinc-600">Stored as: {typeKey}</p>}
      <AttributesSchemaEditor
        value={attributesSchema}
        onChange={onAttributesSchemaChange}
      />
    </div>
  );
};
