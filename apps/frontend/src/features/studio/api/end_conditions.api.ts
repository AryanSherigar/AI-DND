import { apiClient } from "@/shared/lib/api-client";
import {
  EndConditionCreate,
  EndConditionListResponse,
  EndConditionResponse,
  EndConditionUpdate,
} from "../types/end_condition.types";

export const listEndConditions = async (
  scenarioId: string,
): Promise<EndConditionListResponse> => {
  const response = await apiClient.get<EndConditionListResponse>(
    `/v1/scenarios/${scenarioId}/end_conditions`,
  );
  return response.data;
};

export const getEndCondition = async (
  scenarioId: string,
  endConditionId: string,
): Promise<EndConditionResponse> => {
  const response = await apiClient.get<EndConditionResponse>(
    `/v1/scenarios/${scenarioId}/end_conditions/${endConditionId}`,
  );
  return response.data;
};

export const createEndCondition = async (
  scenarioId: string,
  payload: EndConditionCreate,
): Promise<EndConditionResponse> => {
  const response = await apiClient.post<EndConditionResponse>(
    `/v1/scenarios/${scenarioId}/end_conditions`,
    payload,
  );
  return response.data;
};

export const updateEndCondition = async (
  scenarioId: string,
  endConditionId: string,
  payload: EndConditionUpdate,
): Promise<EndConditionResponse> => {
  const response = await apiClient.patch<EndConditionResponse>(
    `/v1/scenarios/${scenarioId}/end_conditions/${endConditionId}`,
    payload,
  );
  return response.data;
};

export const deleteEndCondition = async (
  scenarioId: string,
  endConditionId: string,
): Promise<void> => {
  await apiClient.delete(
    `/v1/scenarios/${scenarioId}/end_conditions/${endConditionId}`,
  );
};

export const reorderEndConditions = async (
  scenarioId: string,
  orderedEndConditionIds: string[],
): Promise<EndConditionListResponse> => {
  const response = await apiClient.post<EndConditionListResponse>(
    `/v1/scenarios/${scenarioId}/end_conditions/reorder`,
    { ordered_end_condition_ids: orderedEndConditionIds },
  );
  return response.data;
};
