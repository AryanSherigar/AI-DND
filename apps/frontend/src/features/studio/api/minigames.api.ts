import { apiClient } from "@/shared/lib/api-client";
import {
  MinigameCreate,
  MinigameListResponse,
  MinigameResponse,
  MinigameUpdate,
} from "../types/minigame.types";

export const listMinigames = async (
  scenarioId: string,
): Promise<MinigameListResponse> => {
  const response = await apiClient.get<MinigameListResponse>(
    `/v1/scenarios/${scenarioId}/minigames`,
  );
  return response.data;
};

export const getMinigame = async (
  scenarioId: string,
  minigameId: string,
): Promise<MinigameResponse> => {
  const response = await apiClient.get<MinigameResponse>(
    `/v1/scenarios/${scenarioId}/minigames/${minigameId}`,
  );
  return response.data;
};

export const createMinigame = async (
  scenarioId: string,
  payload: MinigameCreate,
): Promise<MinigameResponse> => {
  const response = await apiClient.post<MinigameResponse>(
    `/v1/scenarios/${scenarioId}/minigames`,
    payload,
  );
  return response.data;
};

export const updateMinigame = async (
  scenarioId: string,
  minigameId: string,
  payload: MinigameUpdate,
): Promise<MinigameResponse> => {
  const response = await apiClient.patch<MinigameResponse>(
    `/v1/scenarios/${scenarioId}/minigames/${minigameId}`,
    payload,
  );
  return response.data;
};

export const deleteMinigame = async (
  scenarioId: string,
  minigameId: string,
): Promise<void> => {
  await apiClient.delete(`/v1/scenarios/${scenarioId}/minigames/${minigameId}`);
};

export const reorderMinigames = async (
  scenarioId: string,
  orderedMinigameIds: string[],
): Promise<MinigameListResponse> => {
  const response = await apiClient.post<MinigameListResponse>(
    `/v1/scenarios/${scenarioId}/minigames/reorder`,
    { ordered_minigame_ids: orderedMinigameIds },
  );
  return response.data;
};
