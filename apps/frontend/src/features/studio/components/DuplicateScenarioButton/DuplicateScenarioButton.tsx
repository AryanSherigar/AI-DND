import React, { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/shared/components/ui/Button";
import { useDuplicateScenario } from "../../hooks/useDuplicateScenario";
import { DuplicateScenarioButtonProps } from "./DuplicateScenarioButton.types";

export const DuplicateScenarioButton: React.FC<
  DuplicateScenarioButtonProps
> = ({ scenarioId }) => {
  const navigate = useNavigate();
  const { duplicate, duplicatedScenario, isDuplicating, duplicateError } =
    useDuplicateScenario(scenarioId);

  useEffect(() => {
    if (duplicatedScenario) {
      navigate(`/studio/${duplicatedScenario.scenario_id}/edit`);
    }
  }, [duplicatedScenario, navigate]);

  const handleDuplicate = (): void => {
    duplicate();
  };

  return (
    <div className="flex flex-col items-start gap-1">
      <Button
        variant="secondary"
        onClick={handleDuplicate}
        disabled={isDuplicating}
      >
        {isDuplicating ? "Duplicating..." : "Duplicate"}
      </Button>
      {duplicateError && (
        <p className="text-xs text-red-400">{duplicateError}</p>
      )}
    </div>
  );
};
