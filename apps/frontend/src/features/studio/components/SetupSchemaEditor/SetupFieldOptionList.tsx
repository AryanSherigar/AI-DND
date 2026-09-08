import React from "react";
import { Button } from "@/shared/components/ui/Button";
import { Input } from "@/shared/components/ui/Input";
import { SetupInputOption } from "../../stores/studio.store";

interface SetupFieldOptionListProps {
  options: SetupInputOption[];
  onChange: (options: SetupInputOption[]) => void;
}

const createOption = (count: number): SetupInputOption => ({
  id: crypto.randomUUID(),
  label: `Option ${count + 1}`,
  value: `option_${count + 1}`,
});

export const SetupFieldOptionList: React.FC<SetupFieldOptionListProps> = ({
  options,
  onChange,
}) => {
  const handleAdd = (): void => {
    onChange([...options, createOption(options.length)]);
  };

  const handleUpdate = (
    id: string,
    field: "label" | "value",
    val: string,
  ): void => {
    onChange(
      options.map((opt) => (opt.id === id ? { ...opt, [field]: val } : opt)),
    );
  };

  const handleRemove = (id: string): void => {
    onChange(options.filter((opt) => opt.id !== id));
  };

  return (
    <div className="space-y-2 pt-1">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-content-muted">
          Options
        </span>
        <Button type="button" variant="ghost" size="sm" onClick={handleAdd}>
          + Add Option
        </Button>
      </div>
      {options.map((opt) => (
        <div key={opt.id} className="flex items-center gap-2">
          <Input
            aria-label="Option label"
            placeholder="Display label"
            value={opt.label}
            onChange={(e) => handleUpdate(opt.id, "label", e.target.value)}
          />
          <Input
            aria-label="Option value"
            placeholder="Value"
            value={opt.value}
            onChange={(e) => handleUpdate(opt.id, "value", e.target.value)}
          />
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => handleRemove(opt.id)}
          >
            ×
          </Button>
        </div>
      ))}
    </div>
  );
};
