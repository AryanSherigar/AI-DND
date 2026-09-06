import React from "react";
import { Button } from "@/shared/components/ui/Button";
import { useScenario } from "../../hooks/useScenario";
import { useServerSyncedState } from "../../hooks/useServerSyncedState";
import { DistractionFreeEditor } from "../MarkdownEditor/DistractionFreeEditor";
import { OpeningSceneEditorProps } from "./OpeningSceneEditor.types";

export const OpeningSceneEditor: React.FC<OpeningSceneEditorProps> = ({
  scenarioId,
}) => {
  const { scenario, isLoading, updateScenario, isUpdating, updateError } =
    useScenario(scenarioId);
  const [openingScene, setOpeningScene] = useServerSyncedState<string>(
    scenario ? (scenario.opening_scene ?? "") : undefined,
  );

  const handleSave = (): void => {
    updateScenario({ opening_scene: openingScene ?? "" });
  };

  if (isLoading || openingScene === undefined) {
    return <p className="text-sm text-content-faint">Loading opening scene...</p>;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-content">Opening Scene</h2>
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
      <DistractionFreeEditor
        value={openingScene}
        onChange={setOpeningScene}
        placeholder="Describe the scene the player wakes into..."
      />
    </div>
  );
};
