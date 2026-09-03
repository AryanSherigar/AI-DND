import React, { useEffect, useRef, useState } from "react";
import { Badge } from "@/shared/components/ui/Badge";
import { Button } from "@/shared/components/ui/Button";
import { Input } from "@/shared/components/ui/Input";
import { useScenario } from "../../hooks/useScenario";
import { ActionChipsEditorProps } from "./ActionChipsEditor.types";

export const ActionChipsEditor: React.FC<ActionChipsEditorProps> = ({
  scenarioId,
}) => {
  const { scenario, isLoading, updateScenario, isUpdating, updateError } =
    useScenario(scenarioId);
  const [chips, setChips] = useState<string[]>([]);
  const [draft, setDraft] = useState("");
  const hasInitialized = useRef(false);

  useEffect(() => {
    if (scenario && !hasInitialized.current) {
      setChips(scenario.action_chips ?? []);
      hasInitialized.current = true;
    }
  }, [scenario]);

  const handleAdd = (): void => {
    const trimmed = draft.trim();
    if (!trimmed) return;
    setChips([...chips, trimmed]);
    setDraft("");
  };

  const handleRemove = (index: number): void => {
    setChips(chips.filter((_, chipIndex) => chipIndex !== index));
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>): void => {
    if (e.key === "Enter") {
      e.preventDefault();
      handleAdd();
    }
  };

  const handleSave = (): void => {
    updateScenario({ action_chips: chips });
  };

  if (isLoading) {
    return <p className="text-sm text-zinc-500">Loading action chips...</p>;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-zinc-100">
          Suggested Action Chips
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
      <div className="flex flex-wrap gap-2">
        {chips.map((chip, index) => (
          <Badge key={`${chip}-${index}`} className="gap-2">
            {chip}
            <button
              type="button"
              aria-label={`Remove ${chip}`}
              onClick={() => handleRemove(index)}
              className="text-zinc-500 hover:text-zinc-200"
            >
              x
            </button>
          </Badge>
        ))}
      </div>
      <div className="flex items-center gap-2">
        <Input
          aria-label="New action chip"
          placeholder="Search the cairn"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={handleKeyDown}
        />
        <Button type="button" variant="secondary" size="sm" onClick={handleAdd}>
          Add
        </Button>
      </div>
    </div>
  );
};
