import React, { useEffect, useRef, useState } from "react";
import { Button } from "@/shared/components/ui/Button";
import { useScenario } from "../../hooks/useScenario";
import { CheckpointOverrideRow } from "./CheckpointOverrideRow";
import { createCheckpointOverride, toCheckpointOverride } from "./checkpointOverride";
import { CheckpointPersonaOverride, NarratorPersonaEditorProps } from "./NarratorPersonaEditor.types";

export const NarratorPersonaEditor: React.FC<NarratorPersonaEditorProps> = ({
  scenarioId,
}) => {
  const { scenario, isLoading, updateScenario, isUpdating, updateError } =
    useScenario(scenarioId);
  const [overrides, setOverrides] = useState<CheckpointPersonaOverride[]>([]);
  const hasInitialized = useRef(false);

  useEffect(() => {
    if (scenario && !hasInitialized.current) {
      setOverrides((scenario.checkpoints ?? []).map(toCheckpointOverride));
      hasInitialized.current = true;
    }
  }, [scenario]);

  const handleAdd = (): void => {
    setOverrides([...overrides, createCheckpointOverride()]);
  };

  const handleRemove = (checkpointId: string): void => {
    setOverrides(
      overrides.filter((override) => override.checkpoint_id !== checkpointId),
    );
  };

  const handleChange = (updated: CheckpointPersonaOverride): void => {
    setOverrides(
      overrides.map((override) =>
        override.checkpoint_id === updated.checkpoint_id ? updated : override,
      ),
    );
  };

  const handleSave = (): void => {
    updateScenario({ checkpoints: overrides });
  };

  if (isLoading) {
    return (
      <p className="text-sm text-zinc-500">Loading narrator checkpoints...</p>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-zinc-100">
          Narrator Persona Overrides
        </h2>
        <div className="flex items-center gap-2">
          <Button type="button" variant="secondary" size="sm" onClick={handleAdd}>
            Add Checkpoint
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
        {overrides.map((override) => (
          <CheckpointOverrideRow
            key={override.checkpoint_id}
            override={override}
            onChange={handleChange}
            onRemove={() => handleRemove(override.checkpoint_id)}
          />
        ))}
      </div>
    </div>
  );
};
