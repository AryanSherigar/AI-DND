import { apiClient } from "@/shared/lib/api-client";
import { PlaythroughResponse } from "../types/playtest.types";

export const playtestScenario = async (
  scenarioId: string,
): Promise<PlaythroughResponse> => {
  const response = await apiClient.post<PlaythroughResponse>(
    `/v1/scenarios/${scenarioId}/playtest`,
  );
  return response.data;
};
