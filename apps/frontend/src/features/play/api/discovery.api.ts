import { apiClient } from "@/shared/lib/api-client";
import { GetScenariosParams, ScenarioListResponse } from "../types/scenario";

export const fetchScenarios = async (
  params?: GetScenariosParams,
): Promise<ScenarioListResponse> => {
  const response = await apiClient.get<ScenarioListResponse>("/v1/scenarios", {
    params,
  });
  return response.data;
};
