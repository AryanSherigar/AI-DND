import React from "react";
import { Button } from "@/shared/components/ui/Button";
import { useScenario } from "../../hooks/useScenario";
import { useServerSyncedState } from "../../hooks/useServerSyncedState";
import { DistractionFreeEditor } from "../MarkdownEditor/DistractionFreeEditor";
import { RulesEditorProps } from "./RulesEditor.types";

export const RulesEditor: React.FC<RulesEditorProps> = ({ scenarioId }) => {
  const { scenario, isLoading, updateScenario, isUpdating, updateError } =
    useScenario(scenarioId);
  const [rulesText, setRulesText] = useServerSyncedState<string>(
    scenario ? (scenario.rules?.text ?? "") : undefined,
  );

  const handleSave = (): void => {
    updateScenario({ rules: { text: rulesText ?? "" } });
  };

  if (isLoading || rulesText === undefined) {
    return <p className="text-sm text-zinc-500">Loading house rules...</p>;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-zinc-100">House Rules</h2>
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
        value={rulesText}
        onChange={setRulesText}
        placeholder="Any hard world rules the narrator must always respect..."
      />
    </div>
  );
};
