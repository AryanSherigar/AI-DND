import React, { useEffect, useRef, useState } from "react";
import { Button } from "@/shared/components/ui/Button";
import { useScenario } from "../../hooks/useScenario";
import { DistractionFreeEditor } from "../MarkdownEditor/DistractionFreeEditor";
import { OpeningSceneEditorProps } from "./OpeningSceneEditor.types";

export const OpeningSceneEditor: React.FC<OpeningSceneEditorProps> = ({
  scenarioId,
}) => {
  const { scenario, isLoading, updateScenario, isUpdating, updateError } =
    useScenario(scenarioId);
  const [openingScene, setOpeningScene] = useState("");
  const hasInitialized = useRef(false);

  useEffect(() => {
    if (scenario && !hasInitialized.current) {
      setOpeningScene(scenario.opening_scene ?? "");
      hasInitialized.current = true;
    }
  }, [scenario]);

  const handleSave = (): void => {
    updateScenario({ opening_scene: openingScene });
  };

  if (isLoading) {
    return <p className="text-sm text-zinc-500">Loading opening scene...</p>;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-zinc-100">
          Opening Scene
        </h2>
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
      <DistractionFreeEditor
        value={openingScene}
        onChange={setOpeningScene}
        placeholder="Describe the scene the player wakes into..."
      />
    </div>
  );
};
