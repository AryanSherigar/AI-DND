import React from "react";
import { Button } from "@/shared/components/ui/Button";
import { Card } from "@/shared/components/ui/Card";
import { Input } from "@/shared/components/ui/Input";
import { SetupArchetype } from "../../types/scenario.types";
import { ArchetypeValuesEditor } from "./ArchetypeValuesEditor";

interface ArchetypeListEditorProps {
  archetypes: SetupArchetype[];
  onChange: (archetypes: SetupArchetype[]) => void;
}

const createArchetype = (): SetupArchetype => ({
  id: crypto.randomUUID(),
  name: "",
  values: {},
});

export const ArchetypeListEditor: React.FC<ArchetypeListEditorProps> = ({
  archetypes,
  onChange,
}) => {
  const handleAdd = (): void => {
    onChange([...archetypes, createArchetype()]);
  };

  const handleRemove = (id: string): void => {
    onChange(archetypes.filter((archetype) => archetype.id !== id));
  };

  const handleRename = (id: string, name: string): void => {
    onChange(
      archetypes.map((archetype) =>
        archetype.id === id ? { ...archetype, name } : archetype,
      ),
    );
  };

  const handleValuesChange = (
    id: string,
    values: Record<string, unknown>,
  ): void => {
    onChange(
      archetypes.map((archetype) =>
        archetype.id === id ? { ...archetype, values } : archetype,
      ),
    );
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-content">Setup Archetypes</h3>
        <Button type="button" variant="secondary" size="sm" onClick={handleAdd}>
          Add Archetype
        </Button>
      </div>
      <div className="space-y-3">
        {archetypes.map((archetype) => (
          <Card key={archetype.id} className="space-y-3">
            <div className="flex items-center gap-2">
              <Input
                aria-label="Archetype name"
                placeholder="Warrior"
                value={archetype.name}
                onChange={(e) => handleRename(archetype.id, e.target.value)}
              />
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => handleRemove(archetype.id)}
              >
                Remove
              </Button>
            </div>
            <ArchetypeValuesEditor
              values={archetype.values}
              onChange={(values) => handleValuesChange(archetype.id, values)}
            />
          </Card>
        ))}
      </div>
    </div>
  );
};
