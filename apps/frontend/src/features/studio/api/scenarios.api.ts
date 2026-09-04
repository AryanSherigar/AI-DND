import { apiClient } from "@/shared/lib/api-client";
import {
  ScenarioCreate,
  ScenarioListResponse,
  ScenarioResponse,
  ScenarioStatus,
  ScenarioUpdate,
} from "../types/scenario.types";

export type { ScenarioStatus, ScenarioResponse, ScenarioListResponse };
export type CreateScenarioPayload = ScenarioCreate;

export interface ListScenariosParams {
  mine?: boolean;
  sort?: string;
  limit?: number;
  offset?: number;
}

export const createScenario = async (
  payload: CreateScenarioPayload,
): Promise<ScenarioResponse> => {
  const response = await apiClient.post<ScenarioResponse>(
    "/v1/scenarios",
    payload,
  );
  return response.data;
};

export const getScenario = async (
  scenarioId: string,
): Promise<ScenarioResponse> => {
  const response = await apiClient.get<ScenarioResponse>(
    `/v1/scenarios/${scenarioId}`,
  );
  return response.data;
};

export const updateScenario = async (
  scenarioId: string,
  payload: ScenarioUpdate,
): Promise<ScenarioResponse> => {
  const response = await apiClient.patch<ScenarioResponse>(
    `/v1/scenarios/${scenarioId}`,
    payload,
  );
  return response.data;
};

export const updateScenarioContentTag = async (
  scenarioId: string,
  content_tag: string,
): Promise<ScenarioResponse> => {
  const response = await apiClient.patch<ScenarioResponse>(
    `/v1/scenarios/${scenarioId}`,
    { content_tag },
  );
  return response.data;
};

export const publishScenario = async (
  scenarioId: string,
): Promise<ScenarioResponse> => {
  const response = await apiClient.post<ScenarioResponse>(
    `/v1/scenarios/${scenarioId}/publish`,
  );
  return response.data;
};

export const listScenarios = async (
  params: ListScenariosParams,
): Promise<ScenarioListResponse> => {
  const response = await apiClient.get<ScenarioListResponse>("/v1/scenarios", {
    params,
  });
  return response.data;
};

export const deleteScenario = async (scenarioId: string): Promise<void> => {
  await apiClient.delete(`/v1/scenarios/${scenarioId}`);
};
