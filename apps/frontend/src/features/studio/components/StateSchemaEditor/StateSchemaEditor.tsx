import React, { useEffect, useRef, useState } from "react";
import { Button } from "@/shared/components/ui/Button";
import { useScenario } from "../../hooks/useScenario";
import { StateFieldDefinition } from "../../types/scenario.types";
import { StateFieldMapEditor } from "./StateFieldMapEditor";
import { StateSchemaEditorProps } from "./StateSchemaEditor.types";

export const StateSchemaEditor: React.FC<StateSchemaEditorProps> = ({
  scenarioId,
}) => {
  const { scenario, isLoading, updateScenario, isUpdating, updateError } =
    useScenario(scenarioId);
  const [schema, setSchema] = useState<Record<string, StateFieldDefinition>>(
    {},
  );
  const hasInitialized = useRef(false);

  useEffect(() => {
    if (scenario && !hasInitialized.current) {
      setSchema(scenario.state_schema ?? {});
      hasInitialized.current = true;
    }
  }, [scenario]);

  const handleSave = (): void => {
    updateScenario({ state_schema: schema });
  };

  if (isLoading) {
    return <p className="text-sm text-zinc-500">Loading state schema...</p>;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-zinc-100">State Schema</h2>
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
      {updateError && <p className="text-xs text-red-400">{updateError}</p>}
      <StateFieldMapEditor
        value={schema}
        onChange={setSchema}
        depthLabel="Top-level fields"
      />
    </div>
  );
};
