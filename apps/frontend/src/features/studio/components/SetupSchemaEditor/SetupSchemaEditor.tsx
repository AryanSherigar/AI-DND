import React, { useEffect, useRef, useState } from "react";
import { Button } from "@/shared/components/ui/Button";
import { useScenario } from "../../hooks/useScenario";
import { SetupInputField } from "../../stores/studio.store";
import { SetupArchetype } from "../../types/scenario.types";
import { ArchetypeListEditor } from "./ArchetypeListEditor";
import { SetupFieldsEditor } from "./SetupFieldsEditor";
import { SetupSchemaEditorProps } from "./SetupSchemaEditor.types";

export const SetupSchemaEditor: React.FC<SetupSchemaEditorProps> = ({
  scenarioId,
}) => {
  const { scenario, isLoading, updateScenario, isUpdating, updateError } =
    useScenario(scenarioId);
  const [setupFields, setSetupFields] = useState<SetupInputField[]>([]);
  const [archetypes, setArchetypes] = useState<SetupArchetype[]>([]);
  const hasInitialized = useRef(false);

  useEffect(() => {
    if (scenario && !hasInitialized.current) {
      setSetupFields(scenario.setup_schema ?? []);
      setArchetypes(scenario.setup_archetypes ?? []);
      hasInitialized.current = true;
    }
  }, [scenario]);

  const handleSave = (): void => {
    updateScenario({
      setup_schema: setupFields,
      setup_archetypes: archetypes,
    });
  };

  if (isLoading) {
    return (
      <p className="text-sm text-content-faint">Loading setup settings...</p>
    );
  }

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between border-b border-border-subtle pb-4">
        <div>
          <h2 className="text-base font-semibold text-content">
            Player Setup & Archetypes
          </h2>
          <p className="text-xs text-content-faint">
            Configure interactive character setup inputs and starting presets.
          </p>
        </div>
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
      <SetupFieldsEditor fields={setupFields} onChange={setSetupFields} />
      <hr className="border-border-subtle" />
      <ArchetypeListEditor archetypes={archetypes} onChange={setArchetypes} />
    </div>
  );
};
