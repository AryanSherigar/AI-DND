import { apiClient } from "@/shared/lib/api-client";
import { ScenarioResponse } from "../types/scenario.types";

export const duplicateScenario = async (
  scenarioId: string,
): Promise<ScenarioResponse> => {
  const response = await apiClient.post<ScenarioResponse>(
    `/v1/scenarios/${scenarioId}/duplicate`,
  );
  return response.data;
};
