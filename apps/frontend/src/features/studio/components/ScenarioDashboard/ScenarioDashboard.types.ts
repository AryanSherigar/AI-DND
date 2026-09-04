import { ScenarioSummaryResponse } from "../../types/scenario.types";

export interface ScenarioCardProps {
  scenario: ScenarioSummaryResponse;
  onDelete: (scenarioId: string) => void;
  isDeleting: boolean;
}
