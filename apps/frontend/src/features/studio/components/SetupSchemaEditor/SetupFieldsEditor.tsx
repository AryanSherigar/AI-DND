import React from "react";
import { Button } from "@/shared/components/ui/Button";
import { SetupInputField } from "../../stores/studio.store";
import { SetupFieldCard } from "./SetupFieldCard";

export interface SetupFieldsEditorProps {
  fields: SetupInputField[];
  onChange: (fields: SetupInputField[]) => void;
}

const createField = (index: number): SetupInputField => {
  const id = crypto.randomUUID();
  return {
    id,
    key: `field_${index + 1}`,
    label: `Custom Field ${index + 1}`,
    type: "text",
    required: false,
    options: [],
    defaultValue: "",
    is_character_name: false,
    predicate: "",
  };
};

export const SetupFieldsEditor: React.FC<SetupFieldsEditorProps> = ({
  fields,
  onChange,
}) => {
  const handleAdd = (): void => {
    onChange([...fields, createField(fields.length)]);
  };

  const handleUpdate = (
    id: string,
    updates: Partial<SetupInputField>,
  ): void => {
    onChange(
      fields.map((field) =>
        field.id === id ? { ...field, ...updates } : field,
      ),
    );
  };

  const handleDelete = (id: string): void => {
    onChange(fields.filter((field) => field.id !== id));
  };

  const handleMove = (index: number, direction: "up" | "down"): void => {
    const target = direction === "up" ? index - 1 : index + 1;
    if (target < 0 || target >= fields.length) return;
    const reordered = [...fields];
    const temp = reordered[index];
    reordered[index] = reordered[target];
    reordered[target] = temp;
    onChange(reordered);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-content">
            Player Setup Inputs
          </h3>
          <p className="text-xs text-content-faint">
            Interactive fields players fill out before embarking. Name overrides
            the protagonist entity; choices attach as facts.
          </p>
        </div>
        <Button type="button" variant="secondary" size="sm" onClick={handleAdd}>
          Add Input Field
        </Button>
      </div>

      {fields.length === 0 ? (
        <div className="rounded-md p-6 border border-dashed border-border-subtle text-center">
          <p className="text-xs text-content-faint">
            No interactive setup fields defined. The scenario will start without
            customization prompt.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {fields.map((field, index) => (
            <SetupFieldCard
              key={field.id}
              field={field}
              index={index}
              totalCount={fields.length}
              onUpdate={(updates) => handleUpdate(field.id, updates)}
              onDelete={() => handleDelete(field.id)}
              onMove={(direction) => handleMove(index, direction)}
            />
          ))}
        </div>
      )}
    </div>
  );
};
