import React from "react";
import { Button } from "@/shared/components/ui/Button";
import { EmptyState } from "@/shared/components/ui/EmptyState";
import { useScenario } from "../../hooks/useScenario";
import { useServerSyncedState } from "../../hooks/useServerSyncedState";
import { StateFieldDefinition } from "../../types/scenario.types";
import { StateFieldMapEditor } from "./StateFieldMapEditor";
import { StateSchemaEditorProps } from "./StateSchemaEditor.types";

export const StateSchemaEditor: React.FC<StateSchemaEditorProps> = ({
  scenarioId,
}) => {
  const { scenario, isLoading, updateScenario, isUpdating, updateError } =
    useScenario(scenarioId);
  const [schema, setSchema] = useServerSyncedState<
    Record<string, StateFieldDefinition>
  >(scenario ? (scenario.state_schema ?? {}) : undefined);

  const handleSave = (): void => {
    updateScenario({ state_schema: schema ?? {} });
  };

  if (isLoading || schema === undefined) {
    return <p className="text-sm text-content-faint">Loading state schema...</p>;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-content">State Schema</h2>
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
      {updateError && <p className="text-xs text-danger">{updateError}</p>}
      {Object.keys(schema).length === 0 && (
        <EmptyState
          title="No tracked values yet"
          description="Tracked values are the numbers, flags, and variables that change as the story plays out — health, gold, faction standing, and the like."
          example="Example: a number field 'gold', starting at 0."
        />
      )}
      <StateFieldMapEditor
        value={schema}
        onChange={setSchema}
        depthLabel="Top-level fields"
      />
    </div>
  );
};
