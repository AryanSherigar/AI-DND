import React, { useState } from "react";
import { Button } from "@/shared/components/ui/Button";
import { Input } from "@/shared/components/ui/Input";
import { formatArchetypeValue, parseArchetypeValue } from "./parseArchetypeValue";

interface ArchetypeValuesEditorProps {
  values: Record<string, unknown>;
  onChange: (values: Record<string, unknown>) => void;
}

export const ArchetypeValuesEditor: React.FC<ArchetypeValuesEditorProps> = ({
  values,
  onChange,
}) => {
  const [newKey, setNewKey] = useState("");
  const [newValue, setNewValue] = useState("");

  const handleRemove = (key: string): void => {
    const next = { ...values };
    delete next[key];
    onChange(next);
  };

  const handleAdd = (): void => {
    if (!newKey.trim()) return;
    onChange({ ...values, [newKey]: parseArchetypeValue(newValue) });
    setNewKey("");
    setNewValue("");
  };

  return (
    <div className="space-y-2">
      {Object.entries(values).map(([key, value]) => (
        <div key={key} className="flex items-center gap-2">
          <span className="flex-1 truncate font-mono text-xs text-zinc-400">
            {key}
          </span>
          <span className="flex-1 truncate font-mono text-xs text-zinc-300">
            {formatArchetypeValue(value)}
          </span>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => handleRemove(key)}
          >
            Remove
          </Button>
        </div>
      ))}
      <div className="flex items-center gap-2">
        <Input
          aria-label="Value key"
          placeholder="player.health"
          value={newKey}
          onChange={(e) => setNewKey(e.target.value)}
        />
        <Input
          aria-label="Value data"
          placeholder="100"
          value={newValue}
          onChange={(e) => setNewValue(e.target.value)}
        />
        <Button type="button" variant="secondary" size="sm" onClick={handleAdd}>
          Add
        </Button>
      </div>
    </div>
  );
};
