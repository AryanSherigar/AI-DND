import React, { useEffect, useRef, useState } from "react";
import { Button } from "@/shared/components/ui/Button";
import { Card } from "@/shared/components/ui/Card";
import { Input } from "@/shared/components/ui/Input";
import { useScenario } from "../../hooks/useScenario";
import { SetupArchetype } from "../../types/scenario.types";
import { ArchetypeValuesEditor } from "./ArchetypeValuesEditor";
import { SetupSchemaEditorProps } from "./SetupSchemaEditor.types";

const createArchetype = (): SetupArchetype => ({
  id: crypto.randomUUID(),
  name: "",
  values: {},
});

export const SetupSchemaEditor: React.FC<SetupSchemaEditorProps> = ({
  scenarioId,
}) => {
  const { scenario, isLoading, updateScenario, isUpdating, updateError } =
    useScenario(scenarioId);
  const [archetypes, setArchetypes] = useState<SetupArchetype[]>([]);
  const hasInitialized = useRef(false);

  useEffect(() => {
    if (scenario && !hasInitialized.current) {
      setArchetypes(scenario.setup_archetypes ?? []);
      hasInitialized.current = true;
    }
  }, [scenario]);

  const handleAdd = (): void => {
    setArchetypes([...archetypes, createArchetype()]);
  };

  const handleRemove = (id: string): void => {
    setArchetypes(archetypes.filter((archetype) => archetype.id !== id));
  };

  const handleRename = (id: string, name: string): void => {
    setArchetypes(
      archetypes.map((archetype) =>
        archetype.id === id ? { ...archetype, name } : archetype,
      ),
    );
  };

  const handleValuesChange = (
    id: string,
    values: Record<string, unknown>,
  ): void => {
    setArchetypes(
      archetypes.map((archetype) =>
        archetype.id === id ? { ...archetype, values } : archetype,
      ),
    );
  };

  const handleSave = (): void => {
    updateScenario({ setup_archetypes: archetypes });
  };

  if (isLoading) {
    return <p className="text-sm text-zinc-500">Loading setup archetypes...</p>;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-zinc-100">
          Setup Archetypes
        </h2>
        <div className="flex items-center gap-2">
          <Button type="button" variant="secondary" size="sm" onClick={handleAdd}>
            Add Archetype
          </Button>
          <Button
            type="button"
            variant="primary"
            size="sm"
            onClick={handleSave}
            disabled={isUpdating}
          >
            {isUpdating ? "Saving..." : "Save"}
          </Button>
        </div>
      </div>
      {updateError && <p className="text-xs text-red-400">{updateError}</p>}
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
