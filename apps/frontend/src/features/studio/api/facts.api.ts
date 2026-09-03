import { apiClient } from "@/shared/lib/api-client";
import {
  FactCreate,
  FactListResponse,
  FactResponse,
  FactUpdate,
} from "../types/fact.types";

export const listFacts = async (
  scenarioId: string,
): Promise<FactListResponse> => {
  const response = await apiClient.get<FactListResponse>(
    `/v1/scenarios/${scenarioId}/facts`,
  );
  return response.data;
};

export const getFact = async (
  scenarioId: string,
  factId: string,
): Promise<FactResponse> => {
  const response = await apiClient.get<FactResponse>(
    `/v1/scenarios/${scenarioId}/facts/${factId}`,
  );
  return response.data;
};

export const createFact = async (
  scenarioId: string,
  payload: FactCreate,
): Promise<FactResponse> => {
  const response = await apiClient.post<FactResponse>(
    `/v1/scenarios/${scenarioId}/facts`,
    payload,
  );
  return response.data;
};

export const updateFact = async (
  scenarioId: string,
  factId: string,
  payload: FactUpdate,
): Promise<FactResponse> => {
  const response = await apiClient.patch<FactResponse>(
    `/v1/scenarios/${scenarioId}/facts/${factId}`,
    payload,
  );
  return response.data;
};

export const deleteFact = async (
  scenarioId: string,
  factId: string,
): Promise<void> => {
  await apiClient.delete(`/v1/scenarios/${scenarioId}/facts/${factId}`);
};
