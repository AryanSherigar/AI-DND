import { apiClient } from "@/shared/lib/api-client";
import {
  ConditionCreate,
  ConditionListResponse,
  ConditionResponse,
  ConditionUpdate,
} from "../types/condition.types";

export const listConditions = async (
  scenarioId: string,
): Promise<ConditionListResponse> => {
  const response = await apiClient.get<ConditionListResponse>(
    `/v1/scenarios/${scenarioId}/conditions`,
  );
  return response.data;
};

export const getCondition = async (
  scenarioId: string,
  conditionId: string,
): Promise<ConditionResponse> => {
  const response = await apiClient.get<ConditionResponse>(
    `/v1/scenarios/${scenarioId}/conditions/${conditionId}`,
  );
  return response.data;
};

export const createCondition = async (
  scenarioId: string,
  payload: ConditionCreate,
): Promise<ConditionResponse> => {
  const response = await apiClient.post<ConditionResponse>(
    `/v1/scenarios/${scenarioId}/conditions`,
    payload,
  );
  return response.data;
};

export const updateCondition = async (
  scenarioId: string,
  conditionId: string,
  payload: ConditionUpdate,
): Promise<ConditionResponse> => {
  const response = await apiClient.patch<ConditionResponse>(
    `/v1/scenarios/${scenarioId}/conditions/${conditionId}`,
    payload,
  );
  return response.data;
};

export const deleteCondition = async (
  scenarioId: string,
  conditionId: string,
): Promise<void> => {
  await apiClient.delete(
    `/v1/scenarios/${scenarioId}/conditions/${conditionId}`,
  );
};
